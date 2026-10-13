import json
from types import SimpleNamespace

from foreman.agent import (
    CLOSED,
    FALLBACK,
    MAX_CUSTOMER_TURNS,
    MAX_MESSAGE_CHARS,
    MAX_TOOL_STEPS,
    ChatState,
    missing,
    respond,
)
from foreman.schema import Lead

TODAY = "2026-10-13"


def say(text):
    return SimpleNamespace(content=text, tool_calls=None)


def tool(name, **args):
    call = SimpleNamespace(
        id=f"call_{name}", function=SimpleNamespace(name=name, arguments=json.dumps(args))
    )
    return SimpleNamespace(content=None, tool_calls=[call])


class Script:
    """A fake model that returns the given messages in order and records each call."""

    def __init__(self, *messages):
        self.queue = list(messages)
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.calls.append(kwargs)
        msg = self.queue.pop(0) if self.queue else say("ok")
        usage = SimpleNamespace(prompt_tokens=100, completion_tokens=20)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)], usage=usage)


def run(state, text, *script):
    client = Script(*script)
    return respond(state, text, TODAY, model="gpt-4o-mini", client=client), client


def test_saves_details_and_reports_what_is_missing():
    state = ChatState()
    turn, client = run(
        state,
        "need my roof fixed in Burbank",
        tool("SaveDetails", job_types=["roofing"], location="Burbank"),
        say("Got it! What's the best number to reach you?"),
    )
    assert turn.reply.startswith("Got it")
    assert not turn.done
    assert state.details == {"job_types": ["roofing"], "location": "Burbank"}
    tool_result = json.loads(state.messages[2]["content"])
    assert tool_result["still_missing"][0] == "a phone number or email to reach them"
    assert len(client.calls) == 2


def test_finish_is_refused_without_contact():
    state = ChatState(details={"job_types": ["roofing"]})
    run(state, "that's all", tool("Finish", reason="done"), say("Before I go, a number?"))
    assert state.status == "open"
    assert json.loads(state.messages[2]["content"]) == {
        "ok": False,
        "need_first": ["a phone number or email"],
    }


def test_finish_with_job_and_contact_submits():
    state = ChatState(details={"job_types": ["roofing"]})
    turn, _ = run(
        state,
        "818-555-0101",
        tool("SaveDetails", contact="818-555-0101"),
        tool("Finish", reason="have everything"),
        say("Thanks! Someone will be in touch."),
    )
    assert turn.done and turn.submitted
    assert state.lead().contact == "818-555-0101"


def test_end_chat_for_spam():
    state = ChatState()
    turn, _ = run(state, "buy SEO", tool("EndChat", reason="sales pitch"), say("No thanks, bye!"))
    assert turn.done and not turn.submitted
    assert state.end_reason == "sales pitch"


def test_closed_chat_does_not_call_the_model():
    state = ChatState(status="submitted")
    turn, client = run(state, "one more thing")
    assert turn.reply == CLOSED
    assert client.calls == []


def test_price_in_reply_gets_rewritten():
    state = ChatState()
    turn, client = run(
        state,
        "how much for a new roof?",
        say("Usually around $12,000 for a roof."),
        say("The team will go over pricing with you. Where is the house?"),
    )
    assert "$" not in turn.reply
    assert state.guard_rewrites == 1
    assert client.calls[-1]["tool_choice"] == "none"


def test_reply_falls_back_if_rewrite_still_breaks_rules():
    state = ChatState()
    turn, _ = run(
        state, "when can you come?", say("We can come Thursday."), say("How about Friday?")
    )
    assert turn.reply == FALLBACK
    assert state.guard_fallbacks == 1


def test_dates_the_customer_said_are_fine():
    state = ChatState()
    turn, _ = run(state, "need it done before Thursday", say("Got it, before Thursday."))
    assert turn.reply == "Got it, before Thursday."
    assert state.guard_rewrites == 0


def test_bad_tool_arguments_do_not_crash():
    state = ChatState()
    run(
        state, "pool please", tool("SaveDetails", job_types=["swimming pool"]), say("Tell me more?")
    )
    assert "error" in json.loads(state.messages[2]["content"])
    assert state.details == {}


def test_tool_loop_is_bounded():
    state = ChatState()
    calls = [tool("SaveDetails", location="Encino")] * (MAX_TOOL_STEPS + 3)
    turn, client = run(state, "hi", *calls)
    assert len(client.calls) == MAX_TOOL_STEPS
    assert turn.reply == FALLBACK


def test_turn_limit_submits_what_it_has():
    state = ChatState(
        details={"job_types": ["kitchen"], "contact": "a@b.com"},
        customer_turns=MAX_CUSTOMER_TURNS - 1,
    )
    turn, client = run(state, "still here", say("Anything else?"))
    assert turn.done and turn.submitted
    assert state.end_reason == "turn limit"
    sent = client.calls[0]["messages"]
    assert any("last message" in m["content"] for m in sent if m["role"] == "system")


def test_turn_limit_without_contact_ends():
    state = ChatState(customer_turns=MAX_CUSTOMER_TURNS - 1)
    turn, _ = run(state, "bye", say("Bye!"))
    assert turn.done and not turn.submitted


def test_long_messages_are_cut():
    state = ChatState()
    run(state, "x" * (MAX_MESSAGE_CHARS + 500), say("ok"))
    assert len(state.messages[0]["content"]) == MAX_MESSAGE_CHARS


def test_state_survives_json():
    state = ChatState(details={"location": "Encino"}, customer_turns=2)
    assert ChatState.from_json(state.to_json()) == state


def test_contact_is_asked_right_after_the_job():
    assert missing(Lead(is_lead=True))[:2] == [
        "what they need done",
        "a phone number or email to reach them",
    ]


def test_dashes_are_replaced_before_sending():
    state = ChatState()
    turn, _ = run(state, "hi", say("Got it\u2014what's the address?"))
    assert turn.reply == "Got it, what's the address?"


def test_casual_today_is_not_a_promise():
    from foreman.guards import invented_when

    said = "am I talking to a real person?"
    assert invented_when("I'm an assistant. How can I help you today?", said) == []
    assert invented_when("We can come out today to look.", said) == ["today"]
    assert invented_when("Someone can be there this week.", said) == ["this week"]
    assert invented_when("We could do Thursday.", said) == ["Thursday"]


def test_zero_budget_is_not_stated():
    from datetime import date

    from foreman.rules import apply_rules

    lead = Lead(is_lead=True, budget_min=0, budget_max=8000)
    out = apply_rules(lead, "under 8k", date(2026, 10, 12))
    assert (out.budget_min, out.budget_max) == (None, 8000)
