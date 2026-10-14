"""Fail CI if an eval result crosses a threshold in eval/thresholds.json.

    uv run python -m eval.gate --label ci-abc123

Reads the results files saved under that label (several runs of the same eval
are averaged, so one noisy run doesn't decide) and exits 1 on any failure.
"""

import argparse
import json
import statistics
import sys

from eval.run_eval import RESULTS_DIR, ROOT

THRESHOLDS = ROOT / "eval" / "thresholds.json"


def metrics_for(result: dict) -> tuple[str, dict]:
    """Which eval a results file came from, and the numbers the gate looks at."""
    kind = result.get("kind", "extract")
    s = result["summary"]
    if kind == "extract":
        return kind, {
            "hallucination_rate": s["hallucination_rate"],
            "overall_accuracy": s["overall_accuracy"],
        }
    if kind == "reply":
        return kind, {"pass_rate": s["passed"] / s["n"]}
    if kind == "estimate":
        uncovered = [r for r in result["results"] if r.get("uncovered")]
        return kind, {
            "model_in_band": s["model_in_band"],
            "declined_uncovered": sum(r["decision_correct"] for r in uncovered) / len(uncovered),
            "raw_violations": int(s["estimates_with_raw_violations"].split("/")[0]),
        }
    return kind, {}


def check(results: list[dict], thresholds: dict) -> list[dict]:
    by_kind: dict[str, list[dict]] = {}
    for r in results:
        kind, m = metrics_for(r)
        by_kind.setdefault(kind, []).append(m)

    rows = []
    for kind, limits in thresholds.items():
        if kind.startswith("_"):
            continue
        runs = by_kind.get(kind, [])
        for name, rule in limits.items():
            values = [m[name] for m in runs if m.get(name) is not None]
            if not values:
                rows.append(
                    {"eval": kind, "metric": name, "value": None, "rule": rule, "ok": False}
                )
                continue
            value = statistics.fmean(values)
            ok = ("max" not in rule or value <= rule["max"]) and (
                "min" not in rule or value >= rule["min"]
            )
            rows.append(
                {
                    "eval": kind,
                    "metric": name,
                    "value": value,
                    "runs": len(values),
                    "rule": rule,
                    "ok": ok,
                }
            )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True, help="results files whose label starts with this")
    args = parser.parse_args()

    files = sorted(p for p in RESULTS_DIR.glob("*.json") if f"_{args.label}" in p.name)
    results = [json.loads(p.read_text()) for p in files]
    rows = check(results, json.loads(THRESHOLDS.read_text()))

    for r in rows:
        bound = f"<= {r['rule']['max']}" if "max" in r["rule"] else f">= {r['rule']['min']}"
        value = "missing" if r["value"] is None else f"{r['value']:.3f}"
        print(
            f"{'PASS' if r['ok'] else 'FAIL'}  {r['eval']:<9}{r['metric']:<22}{value:>9}  {bound}"
        )
    failed = [r for r in rows if not r["ok"]]
    print(f"\n{len(rows) - len(failed)}/{len(rows)} checks passed ({len(files)} results files)")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
