"""SQLite storage for leads and the job board they move through.

Plain sqlite3, no ORM: a few tables, a handful of queries. The database file
holds real customer messages, so it lives in data/ and is gitignored.

A lead has two separate states:
  status  pending | approved   whether a person has checked the AI's extraction
  stage   new, contacted, ...  where the job is in the pipeline (the board column)
"""

import json
import secrets
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from foreman.schema import Lead

DEFAULT_DB = Path(__file__).parent.parent / "data" / "foreman.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    received_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending | approved
    extracted TEXT,         -- Lead JSON after rules
    raw_extracted TEXT,     -- Lead JSON exactly as the model returned it
    approved TEXT,          -- Lead JSON after human review
    edited_fields TEXT,     -- JSON list of fields the reviewer changed
    model TEXT,
    prompt_version TEXT,
    cost_usd REAL,
    latency_ms REAL,
    error TEXT,
    stage TEXT NOT NULL DEFAULT 'new',
    position REAL NOT NULL DEFAULT 0,  -- order within the column, lowest first
    stage_changed_at TEXT,
    source TEXT  -- how the customer reached out: text | email | call | in_person | other
);

CREATE TABLE IF NOT EXISTS stages (
    key TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    position INTEGER NOT NULL,
    closed INTEGER NOT NULL DEFAULT 0  -- done or lost: no follow-up nudges
);

-- Public chat conversations. The state is the agent's JSON (messages, details).
CREATE TABLE IF NOT EXISTS chats (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    state TEXT NOT NULL,
    lead_id INTEGER REFERENCES leads(id)
);

-- Every change to a card, oldest first. Card history and "no answer in 6 days"
-- nudges both read from here.
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id INTEGER NOT NULL REFERENCES leads(id),
    at TEXT NOT NULL,
    kind TEXT NOT NULL,  -- created | approved | moved | note | edited | reply_drafted | reply_sent
    detail TEXT          -- JSON
);
"""

# A standard contractor pipeline. Stored in the database so it can be changed to
# match how a business actually works.
DEFAULT_STAGES = [
    ("new", "New lead", False),
    ("contacted", "Contacted", False),
    ("site_visit", "Site visit", False),
    ("quote_sent", "Quote sent", False),
    ("won", "Won", False),
    ("in_progress", "In progress", False),
    ("done", "Done", True),
    ("lost", "Lost", True),
]

# Columns added after the first version of the leads table. Older databases get
# them on startup.
ADDED_COLUMNS = {
    "stage": "TEXT NOT NULL DEFAULT 'new'",
    "position": "REAL NOT NULL DEFAULT 0",
    "stage_changed_at": "TEXT",
    "source": "TEXT",
}

# Fields compared when deciding what the reviewer changed. Same set the eval scores,
# plus the hint and the free-text fields, since edits to those are useful signal too.
REVIEW_FIELDS = [
    "is_lead",
    "customer_name",
    "name_hint",
    "contact",
    "job_types",
    "location",
    "budget_min",
    "budget_max",
    "deadline",
    "urgency",
    "scope_summary",
    "missing_info",
]


@dataclass
class LeadRecord:
    id: int
    text: str
    received_at: date
    created_at: str
    status: str
    extracted: Lead | None
    raw_extracted: Lead | None
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


@dataclass
class Stage:
    key: str
    name: str
    position: int
    closed: bool


@dataclass
class Event:
    at: str
    kind: str
    detail: dict


def add_column(conn: sqlite3.Connection, name: str, ddl: str) -> None:
    """Add a column to leads, fine if another process just added it. Two servers
    (or two first requests) can both see the column missing and both try."""
    try:
        conn.execute(f"ALTER TABLE leads ADD COLUMN {name} {ddl}")
    except sqlite3.OperationalError as e:
        if "duplicate column name" not in str(e):
            raise


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _lead(value: str | None) -> Lead | None:
    return Lead.model_validate_json(value) if value else None


def changed_fields(before: Lead, after: Lead) -> list[str]:
    b, a = before.model_dump(mode="json"), after.model_dump(mode="json")
    changed = []
    for name in REVIEW_FIELDS:
        old, new = b[name], a[name]
        if name == "job_types":
            old, new = sorted(old), sorted(new)
        if old != new:
            changed.append(name)
    return changed


class Store:
    def __init__(self, path: Path | str = DEFAULT_DB):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            existing = {r["name"] for r in conn.execute("PRAGMA table_info(leads)")}
            if existing:
                for name, ddl in ADDED_COLUMNS.items():
                    if name not in existing:
                        add_column(conn, name, ddl)
            conn.executescript(SCHEMA)
            if not conn.execute("SELECT 1 FROM stages LIMIT 1").fetchone():
                conn.executemany(
                    "INSERT INTO stages (key, name, position, closed) VALUES (?, ?, ?, ?)",
                    [(k, n, i, int(c)) for i, (k, n, c) in enumerate(DEFAULT_STAGES)],
                )

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _record(self, row: sqlite3.Row) -> LeadRecord:
        return LeadRecord(
            id=row["id"],
            text=row["text"],
            received_at=date.fromisoformat(row["received_at"]),
            created_at=row["created_at"],
            status=row["status"],
            extracted=_lead(row["extracted"]),
            raw_extracted=_lead(row["raw_extracted"]),
            approved=_lead(row["approved"]),
            edited_fields=json.loads(row["edited_fields"]) if row["edited_fields"] else None,
            model=row["model"],
            prompt_version=row["prompt_version"],
            cost_usd=row["cost_usd"],
            latency_ms=row["latency_ms"],
            error=row["error"],
            stage=row["stage"],
            position=row["position"],
            stage_changed_at=row["stage_changed_at"],
            source=row["source"],
        )

    def _log(self, conn, lead_id: int, kind: str, detail: dict | None = None) -> None:
        conn.execute(
            "INSERT INTO events (lead_id, at, kind, detail) VALUES (?, ?, ?, ?)",
            (lead_id, _now(), kind, json.dumps(detail or {})),
        )

    def add(
        self,
        text: str,
        received_at: date,
        extracted: Lead | None = None,
        raw_extracted: Lead | None = None,
        model: str | None = None,
        prompt_version: str | None = None,
        cost_usd: float | None = None,
        latency_ms: float | None = None,
        error: str | None = None,
        source: str | None = None,
    ) -> LeadRecord:
        now = _now()
        with self._conn() as conn:
            # New cards go on top of the first column.
            top = conn.execute("SELECT MIN(position) FROM leads WHERE stage = 'new'").fetchone()[0]
            cur = conn.execute(
                """INSERT INTO leads (text, received_at, created_at, extracted, raw_extracted,
                   model, prompt_version, cost_usd, latency_ms, error,
                   stage, position, stage_changed_at, source)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', ?, ?, ?)""",
                (
                    text,
                    received_at.isoformat(),
                    now,
                    extracted.model_dump_json() if extracted else None,
                    raw_extracted.model_dump_json() if raw_extracted else None,
                    model,
                    prompt_version,
                    cost_usd,
                    latency_ms,
                    error,
                    (top - 1) if top is not None else 0,
                    now,
                    source,
                ),
            )
            lead_id = cur.lastrowid
            self._log(conn, lead_id, "created")
        return self.get(lead_id)

    def get(self, lead_id: int) -> LeadRecord | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
        return self._record(row) if row else None

    def list_leads(self, status: str | None = None) -> list[LeadRecord]:
        query, params = "SELECT * FROM leads", ()
        if status:
            query, params = query + " WHERE status = ?", (status,)
        with self._conn() as conn:
            rows = conn.execute(query + " ORDER BY position, id DESC", params).fetchall()
        return [self._record(r) for r in rows]

    def approve(self, lead_id: int, lead: Lead) -> LeadRecord | None:
        record = self.get(lead_id)
        if record is None:
            return None
        # A lead whose extraction failed has nothing to compare against: every
        # field the reviewer filled in counts as an edit.
        baseline = record.extracted or Lead(is_lead=False)
        edited = changed_fields(baseline, lead)
        with self._conn() as conn:
            conn.execute(
                "UPDATE leads SET status = 'approved', approved = ?, edited_fields = ? "
                "WHERE id = ?",
                (lead.model_dump_json(), json.dumps(edited), lead_id),
            )
            self._log(conn, lead_id, "approved", {"edited_fields": edited})
        return self.get(lead_id)

    def add_note(self, lead_id: int, text: str) -> Event | None:
        if self.get(lead_id) is None:
            return None
        with self._conn() as conn:
            self._log(conn, lead_id, "note", {"text": text})
        return self.events(lead_id)[-1]

    def log_draft(self, lead_id: int, text: str, prompt_version: str) -> None:
        with self._conn() as conn:
            self._log(conn, lead_id, "reply_drafted", {"text": text, "prompt": prompt_version})

    def mark_sent(self, lead_id: int, text: str) -> LeadRecord | None:
        """Record the reply as the person actually sent it. Comparing it with the
        last draft shows how much drafts get edited. A card still in New lead moves
        to Contacted, since the customer has now been contacted."""
        record = self.get(lead_id)
        if record is None:
            return None
        drafts = [e for e in self.events(lead_id) if e.kind == "reply_drafted"]
        draft = drafts[-1].detail["text"] if drafts else None
        with self._conn() as conn:
            self._log(
                conn,
                lead_id,
                "reply_sent",
                {"text": text, "from_draft": draft is not None, "edited": text != draft},
            )
        if record.stage == "new":
            self.move(lead_id, "contacted", 0)
        return self.get(lead_id)

    def reply_stats(self) -> dict:
        with self._conn() as conn:
            rows = conn.execute("SELECT detail FROM events WHERE kind = 'reply_sent'").fetchall()
        sent = [json.loads(r["detail"]) for r in rows]
        from_draft = [s for s in sent if s.get("from_draft")]
        return {
            "replies_sent": len(sent),
            "replies_from_draft": len(from_draft),
            "drafts_sent_unedited": sum(1 for s in from_draft if not s["edited"]),
        }

    def update_fields(self, lead_id: int, lead: Lead) -> LeadRecord | None:
        """Change a card that was already checked, e.g. a new phone number.

        Kept apart from approve(): these are updates to the job, not mistakes the
        AI made, so edited_fields (the AI's error record) stays as it was."""
        record = self.get(lead_id)
        if record is None:
            return None
        if record.approved is None:
            raise ValueError("check the AI's version first")
        changed = changed_fields(record.approved, lead)
        if not changed:
            return record
        with self._conn() as conn:
            conn.execute(
                "UPDATE leads SET approved = ? WHERE id = ?", (lead.model_dump_json(), lead_id)
            )
            self._log(conn, lead_id, "edited", {"fields": changed})
        return self.get(lead_id)

    def new_chat(self, state_json: str) -> str:
        chat_id = secrets.token_urlsafe(16)  # unguessable, so one visitor can't read another's chat
        now = _now()
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO chats (id, created_at, updated_at, state) VALUES (?, ?, ?, ?)",
                (chat_id, now, now, state_json),
            )
        return chat_id

    def get_chat(self, chat_id: str) -> str | None:
        with self._conn() as conn:
            row = conn.execute("SELECT state FROM chats WHERE id = ?", (chat_id,)).fetchone()
        return row["state"] if row else None

    def save_chat(self, chat_id: str, state_json: str, lead_id: int | None = None) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE chats SET state = ?, updated_at = ?, lead_id = COALESCE(?, lead_id) "
                "WHERE id = ?",
                (state_json, _now(), lead_id, chat_id),
            )

    def stages(self) -> list[Stage]:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM stages ORDER BY position").fetchall()
        return [Stage(r["key"], r["name"], r["position"], bool(r["closed"])) for r in rows]

    def move(self, lead_id: int, stage: str, index: int) -> LeadRecord | None:
        """Put a card at `index` in the `stage` column and renumber that column."""
        if stage not in {s.key for s in self.stages()}:
            raise ValueError(f"unknown stage: {stage}")
        record = self.get(lead_id)
        if record is None:
            return None
        with self._conn() as conn:
            others = [
                r["id"]
                for r in conn.execute(
                    "SELECT id FROM leads WHERE stage = ? AND id != ? ORDER BY position, id DESC",
                    (stage, lead_id),
                )
            ]
            index = max(0, min(index, len(others)))
            ordered = others[:index] + [lead_id] + others[index:]
            conn.executemany(
                "UPDATE leads SET position = ? WHERE id = ?",
                [(i, card) for i, card in enumerate(ordered)],
            )
            if stage != record.stage:
                conn.execute(
                    "UPDATE leads SET stage = ?, stage_changed_at = ? WHERE id = ?",
                    (stage, _now(), lead_id),
                )
                self._log(conn, lead_id, "moved", {"from": record.stage, "to": stage})
        return self.get(lead_id)

    def events(self, lead_id: int) -> list[Event]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT at, kind, detail FROM events WHERE lead_id = ? ORDER BY id", (lead_id,)
            ).fetchall()
        return [Event(r["at"], r["kind"], json.loads(r["detail"] or "{}")) for r in rows]
