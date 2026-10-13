"""HTTP API and job board.

    uv run uvicorn foreman.api:create_app --factory --reload

The board is at http://localhost:8000 (built from web/), the API under /api,
and the API docs at /docs. Login settings come from the environment (see auth.py).
"""

import json
import logging
import os
import threading
from collections import Counter
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
)
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.sessions import SessionMiddleware

from foreman.auth import (
    PUBLIC_PATHS,
    SESSION_DAYS,
    AuthSettings,
    LoginLimiter,
    load_settings,
    password_matches,
)
from foreman.extract import extract
from foreman.reply import NotALead, draft_reply
from foreman.schema import Lead
from foreman.store import DEFAULT_DB, REVIEW_FIELDS, LeadRecord, Store

STATIC = Path(__file__).parent / "static"
# The React build (web/ -> npm run build) lands here. Gitignored.
BOARD = STATIC / "app"

router = APIRouter()  # pages, login, health
api = APIRouter(prefix="/api")  # data


_store_lock = threading.Lock()


@lru_cache
def _open_store(path: str) -> Store:
    return Store(path)


def get_store() -> Store:
    # The board's first page load sends several requests at once. Only one of
    # them should set up (and upgrade) the database.
    with _store_lock:
        return _open_store(str(os.getenv("FOREMAN_DB", DEFAULT_DB)))


def get_extractor():
    return extract


def get_replier():
    return draft_reply


StoreDep = Annotated[Store, Depends(get_store)]
ExtractorDep = Annotated[object, Depends(get_extractor)]
ReplierDep = Annotated[object, Depends(get_replier)]


Source = Literal["text", "email", "call", "in_person", "other"]


class LeadIn(BaseModel):
    text: str = Field(min_length=1, max_length=20000, description="The message as it came in.")
    received_at: date | None = Field(default=None, description="Defaults to today.")
    source: Source | None = Field(default=None, description="How the customer reached out.")


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
    stage: str
    position: float
    stage_changed_at: str | None
    source: str | None

    @classmethod
    def from_record(cls, r: LeadRecord) -> "LeadOut":
        return cls(**{name: getattr(r, name) for name in cls.model_fields})


@router.get("/", include_in_schema=False)
def board():
    index = BOARD / "index.html"
    if not index.exists():
        return HTMLResponse("Board not built yet. Run: cd web && npm install && npm run build")
    return FileResponse(index)


class LoginIn(BaseModel):
    password: str


@router.get("/login", include_in_schema=False)
def login_page():
    return FileResponse(STATIC / "login.html")


@router.post("/login", include_in_schema=False)
def login(body: LoginIn, request: Request):
    settings: AuthSettings = request.app.state.auth
    limiter: LoginLimiter = request.app.state.limiter
    who = request.client.host if request.client else "unknown"
    if limiter.locked(who):
        raise HTTPException(429, "too many attempts")
    if not settings.enabled or password_matches(body.password, settings.password):
        limiter.reset(who)
        request.session["user"] = "reviewer"
        return {"ok": True}
    limiter.fail(who)
    raise HTTPException(401, "wrong password")


@router.post("/logout", include_in_schema=False)
def logout(request: Request):
    request.session.clear()
    return {"ok": True}


@router.get("/favicon.svg", include_in_schema=False)
def favicon():
    return FileResponse(STATIC / "favicon.svg", media_type="image/svg+xml")


@router.get("/health")
def health():
    return {"ok": True}


@api.post("/leads", response_model=LeadOut, status_code=201)
def create_lead(body: LeadIn, store: StoreDep, run: ExtractorDep):
    received_at = body.received_at or date.today()
    try:
        result = run(body.text, received_at=received_at)
    except Exception as e:  # noqa: BLE001 - keep the lead even if the model call fails
        # The message is still saved, so nothing a customer sent gets lost. The
        # reviewer fills it in by hand.
        record = store.add(
            body.text, received_at, error=f"{type(e).__name__}: {e}", source=body.source
        )
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
        source=body.source,
    )
    return LeadOut.from_record(record)


@api.get("/leads", response_model=list[LeadOut])
def list_leads(store: StoreDep, status: str | None = None):
    return [LeadOut.from_record(r) for r in store.list_leads(status)]


@api.get("/leads/{lead_id}", response_model=LeadOut)
def get_lead(lead_id: int, store: StoreDep):
    record = store.get(lead_id)
    if record is None:
        raise HTTPException(404, "lead not found")
    return LeadOut.from_record(record)


@api.post("/leads/{lead_id}/approve", response_model=LeadOut)
def approve_lead(lead_id: int, lead: Lead, store: StoreDep):
    """Send the lead as it should be. Any field that differs from the extraction
    is recorded as an edit; sending it back unchanged means the model got it right."""
    record = store.approve(lead_id, lead)
    if record is None:
        raise HTTPException(404, "lead not found")
    return LeadOut.from_record(record)


class StageOut(BaseModel):
    key: str
    name: str
    position: int
    closed: bool


class MoveIn(BaseModel):
    stage: str
    index: int = Field(ge=0, description="Position in the column, 0 = top.")


class EventOut(BaseModel):
    at: str
    kind: str
    detail: dict


@api.get("/stages", response_model=list[StageOut])
def list_stages(store: StoreDep):
    return [StageOut(**vars(s)) for s in store.stages()]


@api.post("/leads/{lead_id}/move", response_model=LeadOut)
def move_lead(lead_id: int, body: MoveIn, store: StoreDep):
    try:
        record = store.move(lead_id, body.stage, body.index)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    if record is None:
        raise HTTPException(404, "lead not found")
    return LeadOut.from_record(record)


class NoteIn(BaseModel):
    text: str = Field(min_length=1, max_length=5000)


@api.post("/leads/{lead_id}/notes", response_model=EventOut, status_code=201)
def add_note(lead_id: int, body: NoteIn, store: StoreDep):
    event = store.add_note(lead_id, body.text.strip())
    if event is None:
        raise HTTPException(404, "lead not found")
    return EventOut(**vars(event))


@api.put("/leads/{lead_id}/fields", response_model=LeadOut)
def update_fields(lead_id: int, lead: Lead, store: StoreDep):
    """Update a checked card. Logged as an edit, not counted as an AI mistake."""
    try:
        record = store.update_fields(lead_id, lead)
    except ValueError as e:
        raise HTTPException(409, str(e)) from e
    if record is None:
        raise HTTPException(404, "lead not found")
    return LeadOut.from_record(record)


class DraftOut(BaseModel):
    text: str
    asks: list[str]
    prompt_version: str
    cost_usd: float | None


class SentIn(BaseModel):
    text: str = Field(min_length=1, max_length=5000)


@api.post("/leads/{lead_id}/reply", response_model=DraftOut)
def draft(lead_id: int, store: StoreDep, write: ReplierDep):
    """Draft a reply from the card's current details. Nothing is sent."""
    record = store.get(lead_id)
    if record is None:
        raise HTTPException(404, "lead not found")
    fields = record.approved or record.extracted
    if fields is None:
        raise HTTPException(409, "fill in the card first")
    try:
        d = write(record.text, fields)
    except NotALead as e:
        raise HTTPException(409, str(e)) from e
    store.log_draft(lead_id, d.text, d.prompt_version)
    return DraftOut(text=d.text, asks=d.asks, prompt_version=d.prompt_version, cost_usd=d.cost_usd)


@api.post("/leads/{lead_id}/reply/sent", response_model=LeadOut)
def reply_sent(lead_id: int, body: SentIn, store: StoreDep):
    """The person sent the reply themselves (text or email). Record what they sent."""
    record = store.mark_sent(lead_id, body.text.strip())
    if record is None:
        raise HTTPException(404, "lead not found")
    return LeadOut.from_record(record)


@api.get("/leads/{lead_id}/events", response_model=list[EventOut])
def lead_events(lead_id: int, store: StoreDep):
    if store.get(lead_id) is None:
        raise HTTPException(404, "lead not found")
    return [EventOut(**vars(e)) for e in store.events(lead_id)]


@api.get("/stats")
def stats(store: StoreDep):
    records = store.list_leads()
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
        **store.reply_stats(),
    }


@api.get("/export", response_class=PlainTextResponse)
def export(store: StoreDep):
    """Approved leads in the eval dataset format, one JSON object per line. Save
    to eval/data/real.jsonl (gitignored) and run the eval on it with --data."""
    lines = []
    for r in reversed(store.list_leads("approved")):
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


class HideHealthChecks(logging.Filter):
    """Docker calls /health every 30 seconds; those lines bury the real requests."""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        return not (isinstance(args, tuple) and len(args) >= 3 and args[2] == "/health")


def create_app(auth: AuthSettings | None = None) -> FastAPI:
    auth = auth or load_settings()
    access_log = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, HideHealthChecks) for f in access_log.filters):
        access_log.addFilter(HideHealthChecks())
    app = FastAPI(title="Foreman", description="Lead intake with human approval.")
    app.state.auth = auth
    app.state.limiter = LoginLimiter()
    app.include_router(router)
    app.include_router(api)
    if (BOARD / "assets").exists():
        app.mount("/assets", StaticFiles(directory=BOARD / "assets"), name="assets")

    @app.middleware("http")
    async def require_login(request: Request, call_next):
        if not auth.enabled or request.url.path in PUBLIC_PATHS or request.session.get("user"):
            return await call_next(request)
        if request.method == "GET" and "text/html" in request.headers.get("accept", ""):
            return RedirectResponse("/login", status_code=303)
        return JSONResponse({"detail": "login required"}, status_code=401)

    # Added last so it runs first and request.session is ready for require_login.
    # Signed cookie, unreadable by page scripts, not sent on cross-site requests.
    app.add_middleware(
        SessionMiddleware,
        secret_key=auth.secret_key,
        max_age=SESSION_DAYS * 24 * 3600,
        same_site="lax",
        https_only=auth.secure_cookies,
    )
    return app
