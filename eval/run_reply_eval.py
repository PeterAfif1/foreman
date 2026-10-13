"""Draft a reply for every labeled lead and run the automatic checks.

    uv run python -m eval.run_reply_eval --label r1

Replies are drafted from the hand-reviewed labels, not from the extractor's
output, so this measures reply writing on its own. Extraction has its own eval.
"""

import argparse
import hashlib
import json
from collections import Counter
from datetime import UTC, datetime

from eval.reply_checks import check_reply, passed
from eval.run_eval import DEFAULT_DATA, RESULTS_DIR, ROOT, git_info, load_rows
from foreman.prompts import REPLY_PROMPT_VERSION
from foreman.reply import draft_reply, signature
from foreman.schema import Lead


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    parser.add_argument("--model", default=None)
    parser.add_argument("--no-save", action="store_true")
    args = parser.parse_args()

    rows = [r for r in load_rows(DEFAULT_DATA) if r["label"]["is_lead"]]
    failures: Counter = Counter()
    examples, costs = [], []
    for row in rows:
        lead = Lead.model_validate(row["label"])
        draft = draft_reply(row["text"], lead, model=args.model)
        result = check_reply(draft.text, row["text"], lead, draft.asks, signature())
        failures.update(k for k, v in result.items() if v)
        costs.append(draft.cost_usd or 0)
        examples.append(
            {"id": row["id"], "reply": draft.text, "asks": draft.asks, "checks": result}
        )
        print("." if passed(result) else "F", end="", flush=True)

    clean = sum(1 for e in examples if passed(e["checks"]))
    print(f"\n\n{clean}/{len(examples)} replies passed every check\n")
    for check in [
        "invented_money",
        "invented_when",
        "invented_name",
        "missed_asks",
        "redundant_asks",
        "too_long",
        "dashes",
        "no_sign_off",
    ]:
        print(f"{check:<16}{failures[check]:>3} failed")
    for e in examples:
        bad = {k: v for k, v in e["checks"].items() if v}
        if bad:
            print(f"\n{e['id']}: {bad}\n  {e['reply']!r}")

    if args.no_save:
        return
    now = datetime.now(UTC)
    out = {
        "label": args.label,
        "kind": "reply",
        "timestamp": now.isoformat(timespec="seconds"),
        "git": git_info(),
        "model": args.model or "gpt-4o-mini",
        "prompt_version": REPLY_PROMPT_VERSION,
        "dataset": {
            "path": str(DEFAULT_DATA.relative_to(ROOT)),
            "sha256": hashlib.sha256(DEFAULT_DATA.read_bytes()).hexdigest()[:12],
            "n": len(rows),
        },
        "summary": {
            "passed": clean,
            "n": len(examples),
            "failures": dict(failures),
            "avg_cost_usd": sum(costs) / len(costs) if costs else None,
        },
        "examples": examples,
    }
    path = RESULTS_DIR / f"{now:%Y%m%d-%H%M%S}_{args.label}.json"
    path.write_text(json.dumps(out, indent=2) + "\n")
    print(f"\nsaved {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
