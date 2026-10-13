"""Rules every customer-facing message has to pass.

Used live by the chat agent (a message that breaks one is rewritten or replaced
before the customer sees it) and by the evals.
"""

import re

MONEY = re.compile(r"\$\s?\d[\d,]*(?:\.\d+)?k?|\b\d+(?:\.\d+)?\s?k\b|\b\d{1,3}(?:,\d{3})+\b", re.I)
WHEN = re.compile(
    r"\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
    r"january|february|march|april|may|june|july|august|september|october|november|december|"
    r"today|tonight|tomorrow|this week|next week|this weekend|"
    r"\d{1,2}(?::\d{2})?\s?(?:am|pm)|within \d+ (?:hours?|days?))\b",
    re.I,
)


def _new_mentions(pattern: re.Pattern, reply: str, customer_said: str) -> list[str]:
    """Matches in the reply that don't appear anywhere in what the customer wrote."""
    said = customer_said.casefold()
    return [m.group(0) for m in pattern.finditer(reply) if m.group(0).casefold() not in said]


def invented_money(reply: str, customer_said: str) -> list[str]:
    """Prices or amounts the customer never mentioned."""
    return _new_mentions(MONEY, reply, customer_said)


def invented_when(reply: str, customer_said: str) -> list[str]:
    """Days, dates or times the customer never mentioned."""
    return _new_mentions(WHEN, reply, customer_said)


def violations(reply: str, customer_said: str) -> list[str]:
    return invented_money(reply, customer_said) + invented_when(reply, customer_said)
