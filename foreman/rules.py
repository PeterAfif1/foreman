"""Deterministic checks applied after the model.

The model is good at reading messy language and bad at arithmetic and at
following "never do X" rules reliably. Anything that can be decided exactly
(how many days until a date, whether a word appears in the text) is done here
instead of in the prompt.
"""

import re
from datetime import date

from foreman.schema import Lead, Urgency

SOON_WITHIN_DAYS = 60

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z]+", text.casefold()))


def check_name(lead: Lead, text: str) -> Lead:
    """A customer_name has to actually appear in the message, outside any email
    address. Otherwise it was inferred, so it becomes a hint instead."""
    if not lead.customer_name:
        return lead
    name_words = _words(lead.customer_name)
    text_words = _words(EMAIL_RE.sub(" ", text))
    if name_words and name_words <= text_words:
        return lead
    return lead.model_copy(
        update={
            "customer_name": None,
            "name_hint": lead.name_hint or lead.customer_name.title(),
        }
    )


def check_deadline(lead: Lead, received_at: date | None) -> Lead:
    """Decide "soon" from the deadline date instead of trusting the model's math.
    Only touches soon vs. null: emergency and flexible come from the wording."""
    if not lead.deadline or received_at is None:
        return lead
    try:
        deadline = date.fromisoformat(lead.deadline)
    except ValueError:
        return lead.model_copy(update={"deadline": None})

    days = (deadline - received_at).days
    if lead.urgency in (None, Urgency.SOON):
        urgency = Urgency.SOON if 0 <= days <= SOON_WITHIN_DAYS else None
        return lead.model_copy(update={"urgency": urgency})
    return lead


def check_budget(lead: Lead) -> Lead:
    """A budget of $0 means not stated. "Under 8k" sometimes comes back as min 0,
    max 8000, and nobody says their budget starts at $0."""
    update = {f: None for f in ("budget_min", "budget_max") if getattr(lead, f) == 0}
    return lead.model_copy(update=update) if update else lead


def apply_rules(lead: Lead, text: str, received_at: date | None) -> Lead:
    if not lead.is_lead:
        return lead
    lead = check_budget(lead)
    lead = check_name(lead, text)
    return check_deadline(lead, received_at)
