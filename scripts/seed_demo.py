"""Fill a demo board from the synthetic leads, using the real extractor.

    uv run python -m scripts.seed_demo            # data/demo.db
    FOREMAN_DB=data/demo.db uv run uvicorn foreman.api:create_app --factory

No customer data: every message is from eval/data/synthetic.jsonl. About half
the cards are marked as checked with the hand-reviewed labels, so the board's
"AI right on X%" number is a real comparison, not a made-up one.
"""

import argparse
import json
from datetime import date
from pathlib import Path

from eval.metrics import ALL_FIELDS
from foreman.extract import extract
from foreman.schema import Lead
from foreman.store import Store

ROOT = Path(__file__).parent.parent
DATA = ROOT / "eval" / "data" / "synthetic.jsonl"

# Where each demo card ends up, in file order. Spam goes to Lost.
SPREAD = ["new", "new", "contacted", "site_visit", "quote_sent", "won", "in_progress", "done"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "demo.db")
    parser.add_argument("--keep", action="store_true", help="add to an existing demo db")
    args = parser.parse_args()

    if args.db.exists() and not args.keep:
        args.db.unlink()
    store = Store(args.db)

    rows = [json.loads(line) for line in DATA.read_text().splitlines() if line.strip()]
    for i, row in enumerate(rows):
        received = date.fromisoformat(row["received_at"])
        try:
            result = extract(row["text"], received_at=received)
        except Exception as e:  # noqa: BLE001
            record = store.add(row["text"], received, error=f"{type(e).__name__}: {e}")
            print(f"{row['id']}: extraction failed, saved for manual entry")
            continue
        record = store.add(
            row["text"],
            received,
            extracted=result.lead,
            raw_extracted=result.raw_lead,
            model=result.model,
            prompt_version=result.prompt_version,
            cost_usd=result.cost_usd,
            latency_ms=result.latency_ms,
        )
        # Labels only cover the scored fields. The summary, questions and deadline
        # aren't labeled, so the model's versions stand in for what a reviewer
        # would leave alone. Otherwise every card would count as "fixed".
        truth = Lead.model_validate(row["label"])
        label = result.lead.model_copy(
            update={"is_lead": truth.is_lead, **{f: getattr(truth, f) for f in ALL_FIELDS}}
        )
        stage = "lost" if not label.is_lead else SPREAD[i % len(SPREAD)]
        if stage != "new":
            store.move(record.id, stage, 0)
        # Cards past the first column have been looked at, so mark them checked
        # with the reviewed label. Cards in "new" stay for the reviewer.
        if stage != "new":
            store.approve(record.id, label)
        print(f"{row['id']}: {stage}")

    print(f"\n{len(rows)} cards in {args.db}")


if __name__ == "__main__":
    main()
