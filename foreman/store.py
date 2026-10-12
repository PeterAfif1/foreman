"""SQLite storage for leads going through the approval flow.

Plain sqlite3, no ORM: one table, a handful of queries. The database file holds
real customer messages, so it lives in data/ and is gitignored.
"""

import json
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
    error TEXT
)
"""

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
            conn.execute(SCHEMA)

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
    ) -> LeadRecord:
        with self._conn() as conn:
            cur = conn.execute(
                """INSERT INTO leads (text, received_at, created_at, extracted, raw_extracted,
                   model, prompt_version, cost_usd, latency_ms, error)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    text,
                    received_at.isoformat(),
                    datetime.now(UTC).isoformat(timespec="seconds"),
                    extracted.model_dump_json() if extracted else None,
                    raw_extracted.model_dump_json() if raw_extracted else None,
                    model,
                    prompt_version,
                    cost_usd,
                    latency_ms,
                    error,
                ),
            )
            lead_id = cur.lastrowid
        return self.get(lead_id)

    def get(self, lead_id: int) -> LeadRecord | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
        return self._record(row) if row else None

    def list(self, status: str | None = None) -> list[LeadRecord]:
        query, params = "SELECT * FROM leads", ()
        if status:
            query, params = query + " WHERE status = ?", (status,)
        with self._conn() as conn:
            rows = conn.execute(query + " ORDER BY id DESC", params).fetchall()
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
        return self.get(lead_id)
