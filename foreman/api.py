"""HTTP API and dashboard for the approval flow.

    uv run uvicorn foreman.api:app --reload

The dashboard is at http://localhost:8000 and the API docs at /docs.
"""

import json
import os
from collections import Counter
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, Field

from foreman.extract import extract
from foreman.schema import Lead
from foreman.store import DEFAULT_DB, REVIEW_FIELDS, LeadRecord, Store

app = FastAPI(title="Foreman", description="Lead intake with human approval.")

DASHBOARD = Path(__file__).parent / "static" / "index.html"


@lru_cache
def get_store() -> Store:
    return Store(os.getenv("FOREMAN_DB", DEFAULT_DB))


def get_extractor():
    return extract


StoreDep = Annotated[Store, Depends(get_store)]
ExtractorDep = Annotated[object, Depends(get_extractor)]


class LeadIn(BaseModel):
    text: str = Field(min_length=1, description="The message exactly as it came in.")
    received_at: date | None = Field(default=None, description="Defaults to today.")


class LeadOut(BaseModel):
    id: int
    text: str
    received_at: date
    created_at: str
    status: str
    extracted: Lead | None
    approved: Lead | None
    edited_fields: list[str] | None
    model: str | None
    prompt_version: str | None
    cost_usd: float | None
    latency_ms: float | None
    error: str | None

    @classmethod
    def from_record(cls, r: LeadRecord) -> "LeadOut":
        return cls(**{name: getattr(r, name) for name in cls.model_fields})


@app.get("/", include_in_schema=False)
def dashboard():
    return FileResponse(DASHBOARD)


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/leads", response_model=LeadOut, status_code=201)
def create_lead(body: LeadIn, store: StoreDep, run: ExtractorDep):
    received_at = body.received_at or date.today()
    try:
        result = run(body.text, received_at=received_at)
    except Exception as e:  # noqa: BLE001 - keep the lead even if the model call fails
        # The message is still saved, so nothing a customer sent gets lost. The
        # reviewer fills it in by hand.
        record = store.add(body.text, received_at, error=f"{type(e).__name__}: {e}")
        return LeadOut.from_record(record)
    record = store.add(
        body.text,
        received_at,
        extracted=result.lead,
        raw_extracted=result.raw_lead,
        model=result.model,
        prompt_version=result.prompt_version,
        cost_usd=result.cost_usd,
        latency_ms=result.latency_ms,
    )
    return LeadOut.from_record(record)


@app.get("/leads", response_model=list[LeadOut])
def list_leads(store: StoreDep, status: str | None = None):
    return [LeadOut.from_record(r) for r in store.list(status)]


@app.get("/leads/{lead_id}", response_model=LeadOut)
def get_lead(lead_id: int, store: StoreDep):
    record = store.get(lead_id)
    if record is None:
        raise HTTPException(404, "lead not found")
    return LeadOut.from_record(record)


@app.post("/leads/{lead_id}/approve", response_model=LeadOut)
def approve_lead(lead_id: int, lead: Lead, store: StoreDep):
    """Send the lead as it should be. Any field that differs from the extraction
    is recorded as an edit; sending it back unchanged means the model got it right."""
    record = store.approve(lead_id, lead)
    if record is None:
        raise HTTPException(404, "lead not found")
    return LeadOut.from_record(record)


@app.get("/stats")
def stats(store: StoreDep):
    records = store.list()
    approved = [r for r in records if r.status == "approved"]
    edits = Counter(f for r in approved for f in (r.edited_fields or []))
    untouched = sum(1 for r in approved if not r.edited_fields)
    costs = [r.cost_usd for r in records if r.cost_usd is not None]
    return {
        "total": len(records),
        "pending": len(records) - len(approved),
        "approved": len(approved),
        "extraction_errors": sum(1 for r in records if r.error),
        "approved_without_edits": untouched,
        "approved_without_edits_rate": untouched / len(approved) if approved else None,
        # Share of approved leads where the reviewer had to fix each field: the live
        # error rate on real messages.
        "field_edit_rate": {
            f: edits[f] / len(approved) if approved else None for f in REVIEW_FIELDS
        },
        "avg_cost_usd": sum(costs) / len(costs) if costs else None,
    }


@app.get("/export", response_class=PlainTextResponse)
def export(store: StoreDep):
    """Approved leads in the eval dataset format, one JSON object per line. Save
    to eval/data/real.jsonl (gitignored) and run the eval on it with --data."""
    lines = []
    for r in reversed(store.list("approved")):
        row = {
            "id": f"real-{r.id:04d}",
            "source": "dashboard",
            "labeled_by": "peter",
            "received_at": r.received_at.isoformat(),
            "text": r.text,
            "label": r.approved.model_dump(mode="json"),
        }
        lines.append(json.dumps(row))
    return "\n".join(lines) + ("\n" if lines else "")
