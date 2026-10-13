"""Customer chat agent: collects a job request over a few turns, using tools.

The model decides what to say and when to call a tool. Code decides everything
that has to be exact:
  - what's still missing (the same rules as reply drafts)
  - whether the lead can be submitted (needs a job and a way to reach them)
  - the turn limit
  - that no message mentions a price or a date the customer didn't
The agent only collects details. It never quotes, schedules or promises.
"""

import json
import os
from dataclasses import dataclass, field

from dotenv import load_dotenv
from openai import OpenAI, pydantic_function_tool
from pydantic import BaseModel, Field, ValidationError

from foreman.extract import DEFAULT_MODEL, estimate_cost
from foreman.guards import plain_punctuation, strip_unstated_names, violations
from foreman.prompts import AGENT_PROMPT, AGENT_PROMPT_VERSION
from foreman.schema import JobType, Lead, Urgency

MAX_CUSTOMER_TURNS = 8
MAX_TOOL_STEPS = 4  # model calls per customer message, so one turn can't loop forever
MAX_MESSAGE_CHARS = 1500

FALLBACK = "Sorry, could you say that another way?"
CLOSED = "Thanks for reaching out. This chat is closed now."
SUBMITTED = "Thanks! I've passed this to the team, and someone will be in touch soon."
ENDED = "Thanks for reaching out. Take care!"

# Asked at least once before the chat can be submitted, if the first message didn't
# already say them. The customer can still answer "not sure".
ASK_BEFORE_FINISHING = ["where the job is", "their name"]


# Tools the model can call. Their arguments are validated like any other input.


class SaveDetails(BaseModel):
    """Record details the customer just gave. Only include what they actually said."""

    customer_name: str | None = Field(
        default=None,
        description="Only a name they wrote in the chat. A name inside an email address "
        "doesn't count: ask them instead.",
    )
    contact: str | None = Field(default=None, description="Phone number or email they gave.")
    job_types: list[JobType] | None = None
    location: str | None = Field(
        default=None,
        description="City, neighborhood or address. A landmark or a street where they saw "
        "us is not a location: ask where the job is.",
    )
    budget_min: int | None = Field(
        default=None,
        description="Whole dollars. 'About 15k' or 'maybe 15k' sets both min and max to 15000. "
        "'At least 10k' sets only min.",
    )
    budget_max: int | None = Field(
        default=None, description="Whole dollars. 'Under 20k' sets only max to 20000."
    )
    deadline: str | None = Field(default=None, description="YYYY-MM-DD, from today's date.")
    urgency: Urgency | None = Field(
        default=None,
        description="emergency: active damage or a safety problem right now (leak, no heat, "
        "storm damage). soon: they want it within weeks or have a near deadline, including "
        "'ASAP' without damage. flexible: they said timing is open ('no rush'). Leave empty "
        "if they're not sure.",
    )
    scope_summary: str | None = Field(default=None, description="1 to 2 sentences on the job.")


class Finish(BaseModel):
    """Submit the request to the team once the job and a way to reach the customer are
    known, or when the customer wants to stop."""

    reason: str = Field(description="Short note, e.g. 'have everything' or 'customer had to go'.")


class EndChat(BaseModel):
    """End the chat without submitting: spam, sales pitches, abuse, or nothing to do
    with construction work."""

    reason: str


TOOLS = [
    pydantic_function_tool(SaveDetails),
    pydantic_function_tool(Finish),
    pydantic_function_tool(EndChat),
]


@dataclass
class ChatState:
    """Everything about one conversation. Stored as JSON between messages."""

    messages: list[dict] = field(default_factory=list)  # OpenAI-format history, no system
    details: dict = field(default_factory=dict)  # merged SaveDetails
    status: str = "open"  # open | submitted | ended
    end_reason: str | None = None
    customer_turns: int = 0
    guard_rewrites: int = 0  # replies rewritten because they broke a rule
    guard_fallbacks: int = 0  # replies replaced by the fallback
    cost_usd: float = 0.0
    prompt_version: str = AGENT_PROMPT_VERSION

    def to_json(self) -> str:
        return json.dumps(self.__dict__)

    @classmethod
    def from_json(cls, raw: str) -> "ChatState":
        return cls(**json.loads(raw))

    def lead(self) -> Lead:
        return Lead(is_lead=True, **self.details)

    def customer_text(self) -> str:
        return "\n".join(m["content"] for m in self.messages if m["role"] == "user")

    def transcript(self) -> str:
        lines = []
        for m in self.messages:
            if m["role"] == "user":
                lines.append(f"Customer: {m['content']}")
            elif m["role"] == "assistant" and m.get("content"):
                lines.append(f"Foreman: {m['content']}")
        return "\n".join(lines)


@dataclass
class Turn:
    reply: str
    done: bool
    submitted: bool = False


def missing(lead: Lead) -> list[str]:
    """What to ask next in a chat, most important first. Unlike a text reply, a web
    chat has no phone number attached, so contact details come first after the job."""
    asks = []
    if not lead.job_types:
        asks.append("what they need done")
    if not lead.contact:
        asks.append("a phone number or email to reach them")
    if not lead.location:
        asks.append("where the job is")
    if not lead.customer_name:
        asks.append("their name")
    if lead.urgency is not Urgency.EMERGENCY:
        if lead.urgency is None and not lead.deadline:
            asks.append("when they want it done")
        if lead.budget_min is None and lead.budget_max is None:
            asks.append("a rough budget")
    return asks


def can_submit(lead: Lead) -> list[str]:
    """What's blocking submission. Empty means it can go to the board."""
    blocking = []
    if not lead.job_types:
        blocking.append("what they need done")
    if not lead.contact:
        blocking.append("a phone number or email")
    return blocking


def _run_tool(state: ChatState, name: str, raw_args: str) -> dict:
    try:
        args = json.loads(raw_args or "{}")
        if name == "SaveDetails":
            new = SaveDetails.model_validate(args).model_dump(exclude_none=True)
            state.details.update(new)
            state.lead()  # make sure the merged details are still a valid Lead
            return {"saved": sorted(new), "still_missing": missing(state.lead())}
        if name == "Finish":
            lead = state.lead()
            blocking = can_submit(lead)
            if blocking and state.customer_turns < MAX_CUSTOMER_TURNS:
                return {"ok": False, "need_first": blocking}
            unasked = [a for a in ASK_BEFORE_FINISHING if a in missing(lead)]
            if unasked and state.customer_turns == 1:
                return {"ok": False, "ask_first": unasked}
            state.status = "submitted"
            state.end_reason = Finish.model_validate(args).reason
            return {"ok": True}
        if name == "EndChat":
            if state.details.get("job_types"):
                # A real job was described: never throw the lead away.
                return {"ok": False, "error": "This is a real job request. Use Finish."}
            state.status = "ended"
            state.end_reason = EndChat.model_validate(args).reason
            return {"ok": True}
    except (ValidationError, ValueError) as e:
        return {"error": f"invalid arguments: {e}"}
    return {"error": f"unknown tool {name}"}


def _system(today: str) -> dict:
    return {"role": "system", "content": AGENT_PROMPT.format(today=today)}


def respond(
    state: ChatState,
    message: str,
    today: str,
    model: str | None = None,
    client: OpenAI | None = None,
) -> Turn:
    """Handle one customer message: let the model call tools, then reply."""
    if state.status != "open":
        return Turn(reply=CLOSED, done=True)
    load_dotenv()
    model = model or os.getenv("FOREMAN_MODEL", DEFAULT_MODEL)
    client = client or OpenAI()

    state.customer_turns += 1
    state.messages.append({"role": "user", "content": message[:MAX_MESSAGE_CHARS]})
    if state.customer_turns >= MAX_CUSTOMER_TURNS:
        # Last turn: tell the model, so it wraps up instead of asking more.
        state.messages.append(
            {
                "role": "system",
                "content": "This is the last message. Save details, then finish or end.",
            }
        )

    def call(extra: list[dict] | None = None, tools: bool = True):
        completion = client.chat.completions.create(
            model=model,
            temperature=0.3,
            messages=[_system(today), *state.messages, *(extra or [])],
            tools=TOOLS,
            tool_choice="auto" if tools else "none",
        )
        usage = completion.usage
        if usage:
            state.cost_usd += (
                estimate_cost(model, usage.prompt_tokens, usage.completion_tokens) or 0
            )
        return completion.choices[0].message

    reply = None
    for _ in range(MAX_TOOL_STEPS):
        msg = call()
        if not msg.tool_calls:
            reply = (msg.content or "").strip()
            break
        state.messages.append(
            {
                "role": "assistant",
                "content": msg.content,
                "tool_calls": [
                    {
                        "id": t.id,
                        "type": "function",
                        "function": {"name": t.function.name, "arguments": t.function.arguments},
                    }
                    for t in msg.tool_calls
                ],
            }
        )
        for t in msg.tool_calls:
            result = _run_tool(state, t.function.name, t.function.arguments)
            state.messages.append(
                {"role": "tool", "tool_call_id": t.id, "content": json.dumps(result)}
            )

    reply = plain_punctuation(reply) if reply else FALLBACK

    # Guardrail: nothing the customer didn't say about money or dates.
    broken = violations(reply, state.customer_text())
    if broken:
        state.guard_rewrites += 1
        note = {
            "role": "system",
            "content": f"Your reply mentioned {', '.join(broken)}, which the customer never said. "
            "Rewrite it without prices, dates, days or times. Reply with the message only.",
        }
        retry = call([{"role": "assistant", "content": reply}, note], tools=False)
        reply = plain_punctuation((retry.content or "").strip())
        if not reply or violations(reply, state.customer_text()):
            state.guard_fallbacks += 1
            reply = FALLBACK

    # Names they never wrote come out ("Thanks, Carlos!" from carlos@... -> "Thanks!").
    reply = strip_unstated_names(reply, state.customer_text())

    if state.status == "open" and state.customer_turns >= MAX_CUSTOMER_TURNS:
        # Out of turns and the model didn't close it: submit what we have if we can.
        state.status = "submitted" if not can_submit(state.lead()) else "ended"
        state.end_reason = "turn limit"

    # A closed chat can't take answers, so its last message can't ask anything.
    if state.status != "open" and "?" in reply:
        reply = SUBMITTED if state.status == "submitted" else ENDED

    state.messages.append({"role": "assistant", "content": reply})
    return Turn(reply=reply, done=state.status != "open", submitted=state.status == "submitted")
