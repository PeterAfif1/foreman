"""Automatic checks for reply drafts.

Each check is a plain rule a person would agree with, so a failure is easy to
read: "it mentioned Thursday and the customer never did". No model grades the
model here.
"""

import re

from foreman.schema import Lead

MAX_LENGTH = 500

MONEY = re.compile(r"\$\s?\d[\d,]*(?:\.\d+)?k?|\b\d+(?:\.\d+)?\s?k\b|\b\d{1,3}(?:,\d{3})+\b", re.I)
WHEN = re.compile(
    r"\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
    r"january|february|march|april|may|june|july|august|september|october|november|december|"
    r"today|tonight|tomorrow|this week|next week|this weekend|"
    r"\d{1,2}(?::\d{2})?\s?(?:am|pm)|within \d+ (?:hours?|days?))\b",
    re.I,
)
GREETING = re.compile(r"^\s*(?i:hi|hello|hey)\s+([A-Z][a-z]+)", re.M)

# Words that show a question about each thing we need to ask.
ASK_WORDS = {
    "what they need done": [
        "what work",
        "what kind",
        "what you need",
        "more about",
        "details",
        "describe",
        "what can we help",
        "what's going on",
        "what you're looking",
    ],
    "where the job is": ["address", "where", "location", "neighborhood", "area", "located"],
    "when they want it done": ["when", "timeline", "timing", "timeframe", "time frame", "how soon"],
    "a rough budget": ["budget", "spend", "price range", "ballpark"],
    "their name": ["name", "who am i", "who i'm"],
}


def _new_mentions(pattern: re.Pattern, reply: str, message: str) -> list[str]:
    """Matches in the reply that don't appear anywhere in the customer's message."""
    said = message.casefold()
    return [m.group(0) for m in pattern.finditer(reply) if m.group(0).casefold() not in said]


def invented_money(reply: str, message: str) -> list[str]:
    return _new_mentions(MONEY, reply, message)


def invented_when(reply: str, message: str) -> list[str]:
    return _new_mentions(WHEN, reply, message)


def invented_name(reply: str, message: str, lead: Lead) -> str | None:
    """A greeting with a name the customer never wrote, e.g. "Hi Carlos" when the
    name only appears inside their email address."""
    m = GREETING.search(reply)
    if not m or m.group(1).casefold() == "there":
        return None
    name = m.group(1)
    if lead.customer_name and name.casefold() in lead.customer_name.casefold():
        return None
    without_emails = re.sub(r"\S+@\S+", " ", message)
    return None if re.search(rf"\b{re.escape(name)}\b", without_emails, re.I) else name


def missed_asks(reply: str, asks: list[str]) -> list[str]:
    text = reply.casefold()
    return [a for a in asks if not any(w in text for w in ASK_WORDS.get(a, []))]


def redundant_asks(reply: str, lead: Lead) -> list[str]:
    """Questions about things the customer already told us."""
    questions = " ".join(s for s in re.split(r"(?<=[.?!])\s+", reply) if s.endswith("?")).casefold()
    found = []
    if (lead.budget_min is not None or lead.budget_max is not None) and "budget" in questions:
        found.append("budget")
    if lead.customer_name and "your name" in questions:
        found.append("name")
    return found


def check_reply(reply: str, message: str, lead: Lead, asks: list[str], sign_off: str) -> dict:
    return {
        "invented_money": invented_money(reply, message),
        "invented_when": invented_when(reply, message),
        "invented_name": invented_name(reply, message, lead),
        "missed_asks": missed_asks(reply, asks),
        "redundant_asks": redundant_asks(reply, lead),
        "too_long": len(reply) > MAX_LENGTH,
        "dashes": "\u2014" in reply or "\u2013" in reply,
        "no_sign_off": sign_off.casefold() not in reply.casefold(),
    }


def passed(result: dict) -> bool:
    return not any(result.values())
