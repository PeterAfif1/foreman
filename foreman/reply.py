"""Draft the first reply to a lead.

Code decides what to ask (which fields are still blank); the model only writes
the wording. The draft is never sent from here: a person edits and sends it.
"""

import json
import os
import time
from dataclasses import dataclass

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field

from foreman.extract import DEFAULT_MODEL, estimate_cost
from foreman.prompts import REPLY_PROMPT, REPLY_PROMPT_VERSION
from foreman.schema import Lead, Urgency
from foreman.tracing import traced

MAX_ASKS = 3


class Draft(BaseModel):
    message: str = Field(description="The text message to send, sign-off included.")


@dataclass
class ReplyDraft:
    text: str
    asks: list[str]
    model: str
    prompt_version: str
    cost_usd: float | None
    latency_ms: float


class NotALead(Exception):
    pass


def what_to_ask(lead: Lead) -> list[str]:
    """The most useful missing details, most important first, at most MAX_ASKS.

    Written as plain phrases, because the model tends to copy them word for word."""
    asks = []
    if not lead.job_types:
        asks.append("what they need done")
    if not lead.location:
        asks.append("where the job is")
    if lead.urgency is not Urgency.EMERGENCY:
        if lead.urgency is None and not lead.deadline:
            asks.append("when they want it done")
        if lead.budget_min is None and lead.budget_max is None:
            asks.append("a rough budget")
    if not lead.customer_name:
        asks.append("their name")
    return asks[:MAX_ASKS]


def known_facts(lead: Lead) -> dict:
    facts = {
        "name": lead.customer_name,
        "job": lead.job_types or None,
        "summary": lead.scope_summary,
        "location": lead.location,
        "emergency": lead.urgency is Urgency.EMERGENCY or None,
    }
    return {k: v for k, v in facts.items() if v}


def signature() -> str:
    return os.getenv("FOREMAN_SIGNATURE", "Thanks!")


def build_reply_input(text: str, lead: Lead) -> str:
    return json.dumps(
        {
            "customer_message": text,
            "known": known_facts(lead),
            "ask": what_to_ask(lead),
            "sign_off": signature(),
        },
        indent=2,
    )


def draft_reply(
    text: str, lead: Lead, model: str | None = None, client: OpenAI | None = None
) -> ReplyDraft:
    if not lead.is_lead:
        raise NotALead("no reply for spam or wrong numbers")
    load_dotenv()
    model = model or os.getenv("FOREMAN_MODEL", DEFAULT_MODEL)
    client = client or OpenAI()

    start = time.perf_counter()
    completion = traced(
        "reply",
        model,
        REPLY_PROMPT_VERSION,
        estimate_cost,
        lambda: client.chat.completions.parse(
            model=model,
            temperature=0.3,  # a little variety in wording; the content is fixed by the input
            messages=[
                {"role": "system", "content": REPLY_PROMPT},
                {"role": "user", "content": build_reply_input(text, lead)},
            ],
            response_format=Draft,
        ),
    )
    latency_ms = (time.perf_counter() - start) * 1000
    message = completion.choices[0].message
    if message.parsed is None:
        raise RuntimeError(message.refusal or "model returned no draft")

    usage = completion.usage
    tokens_in = usage.prompt_tokens if usage else 0
    tokens_out = usage.completion_tokens if usage else 0
    return ReplyDraft(
        text=message.parsed.message.strip(),
        asks=what_to_ask(lead),
        model=model,
        prompt_version=REPLY_PROMPT_VERSION,
        cost_usd=estimate_cost(model, tokens_in, tokens_out),
        latency_ms=latency_ms,
    )
