import json
import re
from types import SimpleNamespace

from foreman.rag import (
    EstimateDraft,
    QuoteIndex,
    check,
    estimate,
    load_quotes,
)
from foreman.schema import Lead

WORDS = {}


def fake_embed(texts):
    """Bag of words: texts that share words end up close together."""
    vectors = []
    for t in texts:
        v = [0.0] * 512
        for w in re.findall(r"[a-z]+", t.lower()):
            v[WORDS.setdefault(w, len(WORDS) % 512)] += 1.0
        vectors.append(v)
    return vectors


def index(tmp_path=None, embed=fake_embed):
    return QuoteIndex(load_quotes(), embed, cache=(tmp_path / "e.json") if tmp_path else None)


def lead(**kw):
    return Lead(is_lead=True, **kw)


def fake_client(draft: EstimateDraft):
    calls = []

    def parse(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(parsed=draft))],
            usage=SimpleNamespace(prompt_tokens=800, completion_tokens=60),
        )

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(parse=parse)))
    return client, calls


def test_quotes_are_all_marked_synthetic():
    quotes = load_quotes()
    assert len(quotes) == 71
    raw = (
        __import__("pathlib")
        .Path("foreman/knowledge/quotes_synthetic.jsonl")
        .read_text()
        .splitlines()
    )
    assert all(json.loads(line)["synthetic"] for line in raw)


def test_search_finds_the_same_kind_of_job():
    hits = index().search("repair: replace leaking water heater in garage", ["repair"])
    assert hits[0][0].family == "water_heater"
    assert len(hits) == 5


def test_embeddings_are_cached(tmp_path):
    count = []

    def counting(texts):
        count.append(len(texts))
        return fake_embed(texts)

    index(tmp_path, counting)
    index(tmp_path, counting)
    assert count == [71]  # the second index read the cache


def test_cited_quotes_must_have_been_retrieved():
    retrieved = index().search("water heater replace", ["repair"])
    ok_id = retrieved[0][0].id
    price = retrieved[0][0].price_total
    out = check(
        EstimateDraft(
            enough_data=True, comparable_ids=[ok_id, "Q-999"], low=price, high=price, reason="x"
        ),
        retrieved,
    )
    assert out.status == "ok" and [q.id for q in out.cited] == [ok_id]
    assert "cited_unknown_quote" in out.violations


def test_range_outside_cited_prices_is_replaced():
    retrieved = index().search("water heater replace", ["repair"])
    q = retrieved[0][0]
    out = check(
        EstimateDraft(
            enough_data=True,
            comparable_ids=[q.id],
            low=q.price_total - 500,
            high=q.price_total + 2000,
            reason="x",
        ),
        retrieved,
    )
    assert (out.low, out.high) == (q.price_total, q.price_total)
    assert out.violations == ["range_outside_cited"]


def test_backwards_range_is_fixed():
    retrieved = index().search("water heater replace", ["repair"])
    ids = [q.id for q, _ in retrieved[:2]]
    prices = [q.price_total for q, _ in retrieved[:2]]
    out = check(
        EstimateDraft(
            enough_data=True, comparable_ids=ids, low=max(prices), high=min(prices), reason="x"
        ),
        retrieved,
    )
    assert (out.low, out.high) == (min(prices), max(prices))
    assert "missing_or_backwards_range" in out.violations


def test_model_saying_not_enough_means_no_estimate():
    retrieved = index().search("water heater", ["repair"])
    out = check(
        EstimateDraft(enough_data=False, comparable_ids=[], low=None, high=None, reason="none"),
        retrieved,
    )
    assert out.status == "not_enough" and out.low is None


def test_multiple_jobs_and_non_leads_get_no_estimate():
    idx = index()
    assert estimate(lead(job_types=["kitchen", "flooring"]), "x", idx, client=object()).status == (
        "multiple_jobs"
    )
    assert estimate(Lead(is_lead=False), "x", idx, client=object()).status == "not_a_lead"


def test_nothing_similar_skips_the_model():
    client, calls = fake_client(
        EstimateDraft(enough_data=True, comparable_ids=[], low=1, high=2, reason="")
    )
    out = estimate(
        lead(job_types=["other"]),
        "install a swimming pool with a spa",
        index(),
        model="gpt-4o-mini",
        client=client,
    )
    assert out.status == "not_enough"
    assert calls == []


def test_happy_path():
    idx = index()
    retrieved = idx.search("repair: Swap leaking water heater in garage", ["repair"])
    top = [q for q, _ in retrieved if q.family == "water_heater"][:2]
    prices = sorted(q.price_total for q in top)
    client, calls = fake_client(
        EstimateDraft(
            enough_data=True,
            comparable_ids=[q.id for q in top],
            low=prices[0],
            high=prices[-1],
            reason="Same water heater swaps.",
        )
    )
    out = estimate(
        lead(job_types=["repair"], scope_summary="Swap leaking water heater"),
        "water heater leaking in garage",
        idx,
        model="gpt-4o-mini",
        client=client,
    )
    assert out.status == "ok" and out.violations == []
    assert (out.low, out.high) == (prices[0], prices[-1])
    sent = json.loads(calls[0]["messages"][1]["content"])
    assert "family" not in json.dumps(sent)  # the answer key never reaches the model
