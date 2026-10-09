"""Run the extractor over a labeled dataset, print scores, save a results file.

uv run python -m eval.run_eval --label v0
"""

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from eval.metrics import OUTCOMES, SCORED_FIELDS, Report, aggregate, score_example
from foreman.extract import DEFAULT_MODEL, extract
from foreman.prompts import PROMPT_VERSION
from foreman.schema import Lead

ROOT = Path(__file__).parent.parent
DEFAULT_DATA = ROOT / "eval" / "data" / "synthetic.jsonl"
RESULTS_DIR = ROOT / "eval" / "results"


def git_info() -> dict:
    def run(*args):
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout

    return {
        "sha": run("rev-parse", "--short", "HEAD").strip(),
        "dirty": bool(run("status", "--porcelain")),
    }


def load_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def fmt(value: float | None, pct: bool = True) -> str:
    if value is None:
        return "n/a"
    return f"{value:.1%}" if pct else f"{value:.4f}"


def print_report(report: Report, errors: int) -> None:
    print(f"\n{'field':<15}{'accuracy':>10}" + "".join(f"{o:>15}" for o in OUTCOMES[1:]))
    for name in SCORED_FIELDS:
        c = report.field_counts[name]
        print(
            f"{name:<15}{fmt(report.field_accuracy(name)):>10}"
            + "".join(f"{c[o]:>15}" for o in OUTCOMES[1:])
        )
    print()
    print(f"examples            {report.n_examples}  (extraction errors: {errors})")
    print(f"overall accuracy    {fmt(report.overall_accuracy)}")
    print(f"hallucination rate  {fmt(report.hallucination_rate)}")
    print(f"omission rate       {fmt(report.omission_rate)}")
    print(f"is_lead precision   {fmt(report.is_lead_precision)}")
    print(f"is_lead recall      {fmt(report.is_lead_recall)}")
    print(f"avg cost / lead     ${fmt(report.avg_cost_usd, pct=False)}")
    latency = report.median_latency_ms
    print(
        f"median latency      {latency:.0f} ms"
        if latency is not None
        else "median latency      n/a"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True, help="version label, e.g. v0")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--model", default=None, help=f"defaults to {DEFAULT_MODEL}")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--no-save", action="store_true")
    args = parser.parse_args()

    rows = load_rows(args.data)[: args.limit]
    pairs, costs, latencies, examples = [], [], [], []
    model = args.model

    for row in rows:
        truth = Lead.model_validate(row["label"])
        record = {"id": row["id"], "source": row.get("source"), "truth": truth.model_dump()}
        try:
            result = extract(row["text"], model=args.model)
            pred = result.lead
            model = result.model
            costs.append(result.cost_usd)
            latencies.append(result.latency_ms)
            record.update(cost_usd=result.cost_usd, latency_ms=round(result.latency_ms))
        except Exception as e:  # noqa: BLE001 - one bad call shouldn't kill the run
            # A failed call counts as an empty prediction, so it shows up as omissions
            # instead of silently shrinking the dataset.
            pred = Lead(is_lead=False)
            record["error"] = f"{type(e).__name__}: {e}"
        record["pred"] = pred.model_dump()
        record["outcomes"] = score_example(pred, truth)
        examples.append(record)
        pairs.append((pred, truth))
        print(".", end="", flush=True)

    report = aggregate(pairs, costs, latencies)
    errors = sum(1 for e in examples if "error" in e)
    print_report(report, errors)

    if args.no_save:
        return
    now = datetime.now(UTC)
    out = {
        "label": args.label,
        "timestamp": now.isoformat(timespec="seconds"),
        "git": git_info(),
        "model": model,
        "prompt_version": PROMPT_VERSION,
        "dataset": {
            "path": str(args.data.relative_to(ROOT))
            if args.data.is_relative_to(ROOT)
            else str(args.data),
            "sha256": hashlib.sha256(args.data.read_bytes()).hexdigest()[:12],
            "n": len(rows),
        },
        "summary": {
            "overall_accuracy": report.overall_accuracy,
            "hallucination_rate": report.hallucination_rate,
            "omission_rate": report.omission_rate,
            "is_lead_precision": report.is_lead_precision,
            "is_lead_recall": report.is_lead_recall,
            "avg_cost_usd": report.avg_cost_usd,
            "median_latency_ms": report.median_latency_ms,
            "errors": errors,
        },
        "fields": {name: dict(report.field_counts[name]) for name in SCORED_FIELDS},
        "examples": examples,
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / f"{now:%Y%m%d-%H%M%S}_{args.label}.json"
    path.write_text(json.dumps(out, indent=2) + "\n")
    print(f"\nsaved {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")
    print(
        "README row: "
        f"| {args.label} | | {out['dataset']['path'].split('/')[-1].removesuffix('.jsonl')} "
        f"(n={len(rows)}) | {fmt(report.overall_accuracy)} | {fmt(report.hallucination_rate)} "
        f"| ${fmt(report.avg_cost_usd, pct=False)} | |"
    )


if __name__ == "__main__":
    main()
