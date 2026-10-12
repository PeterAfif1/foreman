"""The structured shape of an inbound lead.

Convention: when the message doesn't say something, the field is null (or an
empty list). There is no "unknown" enum value anywhere. A wrong guess is worse
than a blank, because a blank gets asked about and a guess gets trusted.
"""

from enum import StrEnum

from pydantic import BaseModel, Field


class JobType(StrEnum):
    KITCHEN = "kitchen"
    BATHROOM = "bathroom"
    ROOFING = "roofing"
    FLOORING = "flooring"
    ADDITION = "addition"
    REPAIR = "repair"
    OTHER = "other"


class Urgency(StrEnum):
    EMERGENCY = "emergency"  # active damage: leak, no heat, unsafe
    SOON = "soon"  # wants it in the next few weeks, or names a near date
    FLEXIBLE = "flexible"  # says timing is open, "sometime this year"


class Lead(BaseModel):
    is_lead: bool = Field(
        description="True if a person wants work done. False for spam, wrong numbers, "
        "vendor or marketing pitches."
    )
    customer_name: str | None = Field(
        default=None,
        description="Name exactly as the person wrote it. Never taken from an email "
        "address or handle. Null if not given.",
    )
    name_hint: str | None = Field(
        default=None,
        description="A name suggested by an email address or handle, only when it adds "
        "to customer_name (a name when none was given, or a fuller one). Shown to the "
        "contractor as a guess. Null otherwise.",
    )
    contact: str | None = Field(
        default=None, description="Phone number or email written in the message. Null if none."
    )
    job_types: list[JobType] = Field(
        default_factory=list,
        description="Every distinct job requested. Empty if none can be identified.",
    )
    location: str | None = Field(
        default=None, description="City or neighborhood as written. Null if not stated."
    )
    budget_min: int | None = Field(
        default=None, description="Lower budget bound in dollars, only if stated. Never guess."
    )
    budget_max: int | None = Field(
        default=None, description="Upper budget bound in dollars, only if stated. Never guess."
    )
    deadline: str | None = Field(
        default=None,
        description="Date of a deadline they mention, as YYYY-MM-DD, worked out from the "
        "received date. Use the first of the month if only a month is given. Null if none.",
    )
    urgency: Urgency | None = Field(
        default=None, description="Null unless the message signals timing."
    )
    scope_summary: str | None = Field(
        default=None, description="One or two sentences on the work. Null if not a lead."
    )
    missing_info: list[str] = Field(
        default_factory=list,
        description="Short questions to ask the customer next, for info needed to quote.",
    )
