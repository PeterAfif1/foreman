from types import SimpleNamespace

import pytest

from foreman.extract import ExtractionError, build_user_message, estimate_cost, extract
from foreman.schema import Lead


def fake_client(parsed, refusal=None):
    completion = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(parsed=parsed, refusal=refusal))],
        usage=SimpleNamespace(prompt_tokens=1000, completion_tokens=200),
    )
    completions = SimpleNamespace(parse=lambda **kwargs: completion)
    return SimpleNamespace(chat=SimpleNamespace(completions=completions))


def test_extract_returns_lead_and_cost():
    lead = Lead(is_lead=True, job_types=["roofing"])
    result = extract("roof leaking", model="gpt-4o-mini", client=fake_client(lead))
    assert result.lead == lead
    assert result.cost_usd == pytest.approx((1000 * 0.15 + 200 * 0.60) / 1_000_000)


def test_extract_raises_on_refusal():
    with pytest.raises(ExtractionError, match="nope"):
        extract("x", model="gpt-4o-mini", client=fake_client(None, refusal="nope"))


def test_unknown_model_has_no_cost():
    assert estimate_cost("some-new-model", 100, 100) is None


def test_received_date_is_put_in_front_of_the_message():
    assert build_user_message("roof leak", "2026-10-12") == (
        "Received: Monday, October 12, 2026\n\nroof leak"
    )
    assert build_user_message("roof leak") == "roof leak"


def test_extract_sends_received_date():
    client = fake_client(Lead(is_lead=True))
    sent = {}
    parse = client.chat.completions.parse
    client.chat.completions.parse = lambda **kwargs: sent.update(kwargs) or parse(**kwargs)
    extract("roof leak", model="gpt-4o-mini", client=client, received_at="2026-10-12")
    assert sent["messages"][1]["content"].startswith("Received: Monday, October 12, 2026")
