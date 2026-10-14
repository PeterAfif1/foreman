"""Lead text in, validated Lead out."""

import os
import time
from dataclasses import dataclass
from datetime import date

from dotenv import load_dotenv
from openai import OpenAI

from foreman.prompts import PROMPT_VERSION, SYSTEM_PROMPT
from foreman.rules import apply_rules
from foreman.schema import Lead
from foreman.tracing import traced

DEFAULT_MODEL = "gpt-4o-mini"

# USD per 1M tokens (input, output). Hardcoded so cost per lead is reproducible
# in old results even after list prices change.
PRICING = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "text-embedding-3-small": (0.02, 0.0),
}


@dataclass
class Extraction:
    lead: Lead  # after the rules in rules.py
    raw_lead: Lead  # exactly what the model returned
    model: str
    prompt_version: str
    input_tokens: int
    output_tokens: int
    cost_usd: float | None
    latency_ms: float


class ExtractionError(Exception):
    pass


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float | None:
    if model not in PRICING:
        return None
    price_in, price_out = PRICING[model]
    return (input_tokens * price_in + output_tokens * price_out) / 1_000_000


def build_user_message(text: str, received_at: date | str | None = None) -> str:
    """The model can't judge "soon" without knowing when the message arrived."""
    if received_at is None:
        return text
    if isinstance(received_at, str):
        received_at = date.fromisoformat(received_at)
    return f"Received: {received_at:%A, %B %-d, %Y}\n\n{text}"


def extract(
    text: str,
    model: str | None = None,
    client: OpenAI | None = None,
    received_at: date | str | None = None,
) -> Extraction:
    load_dotenv()
    model = model or os.getenv("FOREMAN_MODEL", DEFAULT_MODEL)
    client = client or OpenAI()

    start = time.perf_counter()
    # Structured outputs: the API constrains decoding to the Lead JSON schema,
    # so the response either parses into a Lead or comes back as a refusal.
    completion = traced(
        "extract",
        model,
        PROMPT_VERSION,
        estimate_cost,
        lambda: client.chat.completions.parse(
            model=model,
            temperature=0,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_message(text, received_at)},
            ],
            response_format=Lead,
        ),
        lambda c: {"refused": c.choices[0].message.parsed is None},
    )
    latency_ms = (time.perf_counter() - start) * 1000

    message = completion.choices[0].message
    if message.parsed is None:
        raise ExtractionError(message.refusal or "model returned no parsed output")

    if isinstance(received_at, str):
        received_at = date.fromisoformat(received_at)
    raw_lead = message.parsed
    lead = apply_rules(raw_lead, text, received_at)

    usage = completion.usage
    input_tokens = usage.prompt_tokens if usage else 0
    output_tokens = usage.completion_tokens if usage else 0
    return Extraction(
        lead=lead,
        raw_lead=raw_lead,
        model=model,
        prompt_version=PROMPT_VERSION,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=estimate_cost(model, input_tokens, output_tokens),
        latency_ms=latency_ms,
    )


if __name__ == "__main__":
    import sys

    result = extract(sys.stdin.read(), received_at=date.today())
    print(result.lead.model_dump_json(indent=2))
    print(
        f"\n{result.model} {result.prompt_version}  {result.latency_ms:.0f} ms  ${result.cost_usd}"
    )
