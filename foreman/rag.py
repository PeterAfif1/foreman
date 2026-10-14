"""Rough estimates from similar past jobs (retrieval-augmented generation).

1. Retrieve: embed the job and find the most similar past quotes.
2. Choose: the model picks which of those are really comparable and gives a range.
3. Check (code): every cited quote must have been retrieved, and the range must sit
   inside the cited quotes' prices. If not, or if nothing similar exists, there is
   no estimate. It never guesses.

For the person running the business only. Customers never see a price.
"""

import hashlib
import json
import math
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field

from foreman.extract import DEFAULT_MODEL, estimate_cost
from foreman.prompts import ESTIMATE_PROMPT, ESTIMATE_PROMPT_VERSION
from foreman.schema import Lead
from foreman.tracing import traced

QUOTES = Path(__file__).parent / "knowledge" / "quotes_synthetic.jsonl"
EMBED_MODEL = "text-embedding-3-small"
TOP_K = 5
# Below this, the closest past job isn't really the same kind of work.
MIN_SIMILARITY = 0.45
JOB_TYPE_BONUS = 0.05


@dataclass(frozen=True)
class Quote:
    id: str
    date: str
    job_types: tuple[str, ...]
    location: str
    description: str
    price_total: int
    family: str  # answer key for the eval only, never shown to the model

    def text(self) -> str:
        return f"{', '.join(self.job_types)}: {self.description}"


def load_quotes(path: Path = QUOTES) -> list[Quote]:
    quotes = []
    for line in path.read_text().splitlines():
        if line.strip():
            q = json.loads(line)
            quotes.append(
                Quote(
                    id=q["id"],
                    date=q["date"],
                    job_types=tuple(q["job_types"]),
                    location=q["location"],
                    description=q["description"],
                    price_total=q["price_total"],
                    family=q["family"],
                )
            )
    return quotes


class Embedder(Protocol):
    def __call__(self, texts: list[str]) -> list[list[float]]: ...


def openai_embedder(client: OpenAI, model: str = EMBED_MODEL) -> Embedder:
    def embed(texts: list[str]) -> list[list[float]]:
        response = traced(
            "embed",
            model,
            None,
            estimate_cost,
            lambda: client.embeddings.create(model=model, input=texts),
            lambda r: {"texts": len(texts)},
        )
        return [d.embedding for d in response.data]

    return embed


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


class QuoteIndex:
    """Past quotes with their embeddings. Small enough to search by brute force:
    71 quotes don't need a vector database."""

    def __init__(self, quotes: list[Quote], embed: Embedder, cache: Path | None = None):
        self.quotes = quotes
        self.embed = embed
        self.vectors = self._load_or_embed(cache)

    def _load_or_embed(self, cache: Path | None) -> list[list[float]]:
        texts = [q.text() for q in self.quotes]
        key = hashlib.sha256(json.dumps(texts).encode()).hexdigest()
        if cache and cache.exists():
            saved = json.loads(cache.read_text())
            if saved.get("key") == key:
                return saved["vectors"]
        vectors = self.embed(texts)
        if cache:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps({"key": key, "vectors": vectors}))
        return vectors

    def search(self, query: str, job_types: list[str], k: int = TOP_K) -> list[tuple[Quote, float]]:
        [qv] = self.embed([query])
        scored = []
        for quote, vector in zip(self.quotes, self.vectors, strict=True):
            score = cosine(qv, vector)
            if set(job_types) & set(quote.job_types):
                score += JOB_TYPE_BONUS
            scored.append((quote, score))
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[:k]


class EstimateDraft(BaseModel):
    enough_data: bool = Field(description="False if none of the past jobs is really comparable.")
    comparable_ids: list[str] = Field(description="IDs of the past quotes that are comparable.")
    low: int | None = Field(description="Low end in whole dollars, from the comparable quotes.")
    high: int | None = Field(description="High end in whole dollars, from the comparable quotes.")
    reason: str = Field(description="1 to 2 sentences: why these jobs are comparable.")


@dataclass
class Estimate:
    status: str  # ok | not_enough | multiple_jobs | not_a_lead
    low: int | None = None
    high: int | None = None
    cited: list[Quote] = field(default_factory=list)
    reason: str = ""
    retrieved: list[tuple[Quote, float]] = field(default_factory=list)
    # What the model did wrong before code fixed it (for the eval).
    violations: list[str] = field(default_factory=list)
    raw: dict | None = None
    prompt_version: str = ESTIMATE_PROMPT_VERSION


def query_text(lead: Lead, text: str) -> str:
    return f"{', '.join(lead.job_types)}: {lead.scope_summary or ''} {text}".strip()


def check(draft: EstimateDraft, retrieved: list[tuple[Quote, float]]) -> Estimate:
    """The code rules. A range must come from quotes we actually showed the model."""
    by_id = {q.id: q for q, _ in retrieved}
    violations = []
    cited = [by_id[i] for i in draft.comparable_ids if i in by_id]
    if len(cited) < len(draft.comparable_ids):
        violations.append("cited_unknown_quote")
    if not draft.enough_data or not cited:
        return Estimate(
            "not_enough",
            reason=draft.reason,
            retrieved=retrieved,
            violations=violations,
            raw=draft.model_dump(),
        )

    prices = [q.price_total for q in cited]
    low, high = draft.low, draft.high
    if low is None or high is None or low > high:
        violations.append("missing_or_backwards_range")
        low, high = min(prices), max(prices)
    if low < min(prices) or high > max(prices):
        # Outside the cited prices means a number came from somewhere else. Use the
        # cited prices themselves instead.
        violations.append("range_outside_cited")
        low, high = min(prices), max(prices)
    return Estimate("ok", low, high, cited, draft.reason, retrieved, violations, draft.model_dump())


def estimate(
    lead: Lead,
    text: str,
    index: QuoteIndex,
    model: str | None = None,
    client: OpenAI | None = None,
) -> Estimate:
    if not lead.is_lead:
        return Estimate("not_a_lead")
    if len(lead.job_types) > 1:
        # One range for two different jobs would hide which part costs what.
        return Estimate("multiple_jobs")
    if not lead.job_types:
        return Estimate("not_enough")

    retrieved = index.search(query_text(lead, text), [str(j) for j in lead.job_types])
    if not retrieved or retrieved[0][1] < MIN_SIMILARITY:
        return Estimate("not_enough", retrieved=retrieved)

    load_dotenv()
    model = model or os.getenv("FOREMAN_MODEL", DEFAULT_MODEL)
    client = client or OpenAI()
    past = [
        {"id": q.id, "job": q.description, "price": q.price_total, "date": q.date}
        for q, _ in retrieved
    ]
    job = {"summary": lead.scope_summary, "message": text, "job_types": lead.job_types}
    completion = traced(
        "estimate",
        model,
        ESTIMATE_PROMPT_VERSION,
        estimate_cost,
        lambda: client.chat.completions.parse(
            model=model,
            temperature=0,
            messages=[
                {"role": "system", "content": ESTIMATE_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps({"job": job, "past_quotes": past}, indent=2),
                },
            ],
            response_format=EstimateDraft,
        ),
    )
    draft = completion.choices[0].message.parsed
    if draft is None:
        return Estimate("not_enough", retrieved=retrieved)
    return check(draft, retrieved)
