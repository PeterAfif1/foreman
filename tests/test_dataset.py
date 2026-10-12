"""Checks the hand-written labels so a typo in the data doesn't look like a
model failure."""

import json
from datetime import date
from pathlib import Path

import pytest

from foreman.schema import Lead

DATA_DIR = Path(__file__).parent.parent / "eval" / "data"
FILES = sorted(p for p in DATA_DIR.glob("*.jsonl") if not p.name.startswith("real"))
ROWS = [
    (path.name, line_no, json.loads(line))
    for path in FILES
    for line_no, line in enumerate(path.read_text().splitlines(), 1)
    if line.strip()
]


def row_id(row):
    name, line_no, _ = row
    return f"{name}:{line_no}"


@pytest.mark.skipif(not ROWS, reason="no labeled data yet")
def test_ids_are_unique():
    ids = [data["id"] for _, _, data in ROWS]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("row", ROWS, ids=[row_id(r) for r in ROWS])
def test_row_is_valid(row):
    _, _, data = row
    assert {"id", "source", "labeled_by", "received_at", "text", "label"} <= data.keys()
    date.fromisoformat(data["received_at"])
    assert data["text"].strip()
    label = Lead.model_validate(data["label"])

    if not label.is_lead:
        filled = {k: v for k, v in label.model_dump().items() if k != "is_lead" and v}
        assert not filled, f"non-lead has fields filled: {filled}"

    if label.budget_min is not None and label.budget_max is not None:
        assert label.budget_min <= label.budget_max
