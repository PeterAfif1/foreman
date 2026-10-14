"""Evaluate rough estimates (retrieval + the model's choice + the code checks).

    uv run python -m eval.run_estimate_eval --label e1

Uses the hand-reviewed lead labels as input, so this measures estimating on its
own. The answer key is the job family each case should match, and each family's
price band from scripts/generate_quotes.py. All quotes are synthetic.
"""

import argparse
import hashlib
import json
import os
import statistics
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from eval.run_eval import DEFAULT_DATA, RESULTS_DIR, ROOT, git_info, load_rows
from foreman.prompts import ESTIMATE_PROMPT_VERSION
from foreman.rag import MIN_SIMILARITY, QuoteIndex, estimate, load_quotes, openai_embedder
from foreman.schema import Lead
from scripts.generate_quotes import FAMILIES

CASES = ROOT / "eval" / "data" / "estimate_cases.jsonl"
CACHE = ROOT / "data" / "embeddings" / "quotes.json"
BANDS = {name: spec[2] for name, spec in FAMILIES.items()}  # family -> (low, high)


def case_input(case: dict, leads: dict) -> tuple[Lead, str]:
    if "lead" in case:
        row = leads[case["lead"]]
        return Lead.model_validate(row["label"]), row["text"]
    return Lead(is_lead=True, job_types=case["job_types"], scope_summary=case["text"]), case["text"]


def in_band(low: int, high: int, families: list[str]) -> bool:
    """Is the middle of the range inside one of the expected families' price bands?"""
    mid = (low + high) / 2
    return any(BANDS[f][0] <= mid <= BANDS[f][1] for f in families)


def first_relevant_rank(retrieved, families) -> int | None:
    for rank, (quote, _) in enumerate(retrieved, 1):
        if quote.family in families:
            return rank
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    parser.add_argument("--model", default=None)
    parser.add_argument("--no-save", action="store_true")
    args = parser.parse_args()
    load_dotenv()
    model = args.model or os.getenv("FOREMAN_MODEL", "gpt-4o-mini")
    client = OpenAI()
    index = QuoteIndex(load_quotes(), openai_embedder(client), cache=CACHE)

    leads = {r["id"]: r for r in load_rows(DEFAULT_DATA)}
    cases = [json.loads(line) for line in CASES.read_text().splitlines() if line.strip()]
    results = []
    for case in cases:
        lead, text = case_input(case, leads)
        est = estimate(lead, text, index, model=model, client=client)
        r = {
            "id": case["id"],
            "expect": case["expect"],
            "families": case["families"],
            "status": est.status,
            "low": est.low,
            "high": est.high,
            "cited": [q.id for q in est.cited],
            "cited_families": [q.family for q in est.cited],
            "retrieved": [(q.id, q.family, round(s, 3)) for q, s in est.retrieved],
            "top_similarity": round(est.retrieved[0][1], 3) if est.retrieved else None,
            "violations": est.violations,
            "reason": est.reason,
            "uncovered": "lead" not in case,
        }
        expected_status = "ok" if case["expect"] == "estimate" else case["expect"]
        r["decision_correct"] = est.status == expected_status
        if case["expect"] == "estimate" and est.retrieved:
            r["first_relevant_rank"] = first_relevant_rank(est.retrieved, case["families"])
            prices = [q.price_total for q, _ in est.retrieved]
            r["baseline"] = {
                "low": min(prices),
                "high": max(prices),
                "in_band": in_band(min(prices), max(prices), case["families"]),
            }
        if est.status == "ok" and case["families"]:
            r["in_band"] = in_band(est.low, est.high, case["families"])
            r["cited_precision"] = sum(f in case["families"] for f in r["cited_families"]) / len(
                r["cited_families"]
            )
        results.append(r)
        print("." if r["decision_correct"] else "F", end="", flush=True)
    print("\n")

    should = [r for r in results if r["expect"] == "estimate"]
    should_not = [r for r in results if r["expect"] != "estimate"]
    ranks = [r.get("first_relevant_rank") for r in should if "first_relevant_rank" in r]
    answered = [r for r in should if r["status"] == "ok"]
    in_band_model = [r["in_band"] for r in answered if "in_band" in r]
    in_band_base = [r["baseline"]["in_band"] for r in should if "baseline" in r]
    widths = [r["high"] - r["low"] for r in answered]
    base_widths = [r["baseline"]["high"] - r["baseline"]["low"] for r in should if "baseline" in r]
    raw_violations = [r for r in results if r["violations"]]
    declined = sum(r["decision_correct"] for r in should_not)

    def rate(xs):
        return sum(xs) / len(xs) if xs else None

    summary = {
        "retrieval_hit_at_1": rate([k == 1 for k in ranks]),
        "retrieval_hit_at_5": rate([k is not None for k in ranks]),
        "mrr": rate([1 / k if k else 0 for k in ranks]),
        "estimated_when_it_should": f"{len(answered)}/{len(should)}",
        "declined_when_it_should": f"{declined}/{len(should_not)}",
        "model_in_band": rate(in_band_model),
        "baseline_in_band": rate(in_band_base),
        "cited_precision": rate([r["cited_precision"] for r in answered if "cited_precision" in r]),
        "median_width_model": statistics.median(widths) if widths else None,
        "median_width_baseline": statistics.median(base_widths) if base_widths else None,
        "estimates_with_raw_violations": f"{len(raw_violations)}/{len(results)}",
    }
    for k, v in summary.items():
        print(f"{k:<28}{v:.1%}" if isinstance(v, float) and v <= 1 else f"{k:<28}{v}")

    # Similarity of the closest past job: covered jobs vs jobs the data has nothing on.
    sims_in = [r["top_similarity"] for r in should if r["top_similarity"] is not None]
    sims_out = [r["top_similarity"] for r in results if r["uncovered"] and r["top_similarity"]]
    median_in = statistics.median(sims_in)
    print(f"\ntop similarity, covered:   min {min(sims_in):.3f}, median {median_in:.3f}")
    if sims_out:
        print(f"top similarity, uncovered: max {max(sims_out):.3f}  (cutoff {MIN_SIMILARITY})")

    for r in results:
        if not r["decision_correct"] or r.get("in_band") is False or r["violations"]:
            print(
                f"\n{r['id']}: expected {r['expect']} {r['families']}, got {r['status']} "
                f"{r['low']}-{r['high']} cited {r['cited_families']} violations {r['violations']}\n"
                f"  retrieved {r['retrieved'][:3]}\n  reason: {r['reason']}"
            )

    if args.no_save:
        return
    now = datetime.now(UTC)
    out = {
        "label": args.label,
        "kind": "estimate",
        "timestamp": now.isoformat(timespec="seconds"),
        "git": git_info(),
        "model": model,
        "prompt_version": ESTIMATE_PROMPT_VERSION,
        "min_similarity": MIN_SIMILARITY,
        "cases": {
            "path": str(CASES.relative_to(ROOT)),
            "sha256": hashlib.sha256(CASES.read_bytes()).hexdigest()[:12],
            "n": len(cases),
        },
        "summary": summary,
        "results": results,
    }
    path = RESULTS_DIR / f"{now:%Y%m%d-%H%M%S}_{args.label}.json"
    path.write_text(json.dumps(out, indent=2) + "\n")
    print(f"\nsaved {Path(path).relative_to(ROOT)}")


if __name__ == "__main__":
    main()
