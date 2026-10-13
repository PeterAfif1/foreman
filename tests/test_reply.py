import json
from types import SimpleNamespace

import pytest

from eval.reply_checks import (
    check_reply,
    invented_money,
    invented_name,
    invented_when,
    missed_asks,
    passed,
    redundant_asks,
)
from foreman.reply import NotALead, build_reply_input, draft_reply, what_to_ask
from foreman.schema import Lead


def lead(**kw):
    return Lead(is_lead=True, **kw)


# What to ask (decided in code)


def test_asks_for_missing_details_in_order():
    assert what_to_ask(lead(job_types=["kitchen"])) == [
        "where the job is",
        "when they want it done",
        "a rough budget",
    ]


def test_unknown_job_is_asked_first():
    assert what_to_ask(lead())[0] == "what they need done"


def test_never_asks_for_what_we_know():
    full = lead(
        customer_name="Dana",
        job_types=["kitchen"],
        location="Burbank",
        budget_max=30000,
        urgency="soon",
    )
    assert what_to_ask(full) == []


def test_emergency_skips_budget_and_timing():
    asks = what_to_ask(lead(job_types=["repair"], urgency="emergency"))
    assert asks == ["where the job is", "their name"]


def test_name_hint_is_not_sent_as_a_known_name():
    data = json.loads(
        build_reply_input("x", lead(name_hint="Carlos Reyes", job_types=["bathroom"]))
    )
    assert "name" not in data["known"]
    assert "Carlos" not in json.dumps(data)


def test_no_reply_for_spam():
    with pytest.raises(NotALead):
        draft_reply("buy SEO", Lead(is_lead=False), client=object())


def test_draft_reply_uses_the_model_output():
    completion = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(parsed=SimpleNamespace(message=" Hi! \n"), refusal=None)
            )
        ],
        usage=SimpleNamespace(prompt_tokens=300, completion_tokens=60),
    )
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(parse=lambda **kw: completion))
    )
    d = draft_reply("roof leak", lead(job_types=["roofing"]), model="gpt-4o-mini", client=client)
    assert d.text == "Hi!"
    assert d.prompt_version == "r2"
    assert d.cost_usd > 0


# The checks themselves


def test_money_the_customer_said_is_fine():
    assert invented_money("Got it, under 30k works.", "budget under 30k") == []
    assert invented_money("Usually around $8,000.", "redo my shower") == ["$8,000"]
    assert invented_money("That's about 15k.", "redo my shower") == ["15k"]


def test_days_and_times_must_come_from_the_customer():
    assert invented_when("We can come Thursday at 3pm.", "fix my roof") == ["Thursday", "3pm"]
    assert invented_when("We'll get someone out today.", "need someone today!!") == []


def test_greeting_name_must_be_written_by_the_customer():
    email_only = "quote please. carlos.reyes88@gmail.com"
    assert invented_name("Hi Carlos, thanks!", email_only, lead()) == "Carlos"
    assert invented_name("Hi there, thanks!", email_only, lead()) is None
    assert invented_name("Hi Sam, thanks!", "this is Sam", lead(customer_name="Sam")) is None
    assert invented_name("Thanks for reaching out!", email_only, lead()) is None


def test_missed_and_redundant_asks():
    asks = ["where the job is", "a rough budget"]
    assert missed_asks("Where is the house?", asks) == ["a rough budget"]
    assert redundant_asks("What's your budget?", lead(budget_max=5000)) == ["budget"]
    assert redundant_asks("We noted your budget.", lead(budget_max=5000)) == []


def test_clean_reply_passes():
    reply = (
        "Hi Dana, thanks for reaching out about the kitchen! "
        "Where is the house, and what budget do you have in mind?\nThanks!"
    )
    result = check_reply(
        reply,
        "kitchen redo - dana",
        lead(customer_name="dana"),
        ["where the job is", "a rough budget"],
        "Thanks!",
    )
    assert passed(result), result


def test_dashes_are_flagged():
    result = check_reply("Hi\u2014thanks!\nThanks!", "x", lead(), [], "Thanks!")
    assert result["dashes"] is True
