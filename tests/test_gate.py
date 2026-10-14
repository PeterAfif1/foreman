import json

from eval.gate import THRESHOLDS, check


def extract(h, acc):
    return {"kind": "extract", "summary": {"hallucination_rate": h, "overall_accuracy": acc}}


def reply(passed, n):
    return {"kind": "reply", "summary": {"passed": passed, "n": n}}


def estimate(in_band, violations, uncovered_ok):
    rows = [{"uncovered": True, "decision_correct": ok} for ok in uncovered_ok]
    return {
        "kind": "estimate",
        "summary": {"model_in_band": in_band, "estimates_with_raw_violations": f"{violations}/31"},
        "results": rows,
    }


LIMITS = json.loads(THRESHOLDS.read_text())


def failed(results):
    return [(r["eval"], r["metric"]) for r in check(results, LIMITS) if not r["ok"]]


def test_todays_results_pass():
    good = [
        extract(0.014, 0.973),
        extract(0.014, 0.973),
        reply(77, 78),
        estimate(1.0, 0, [True] * 5),
    ]
    assert failed(good) == []


def test_prompt_only_extractor_fails():
    # v1's real numbers: 96.0% accuracy, 5.9% hallucination.
    results = [extract(0.059, 0.960), reply(77, 78), estimate(1.0, 0, [True] * 5)]
    assert failed(results) == [("extract", "hallucination_rate")]


def test_runs_are_averaged():
    # One noisy run over the line, the average still under it.
    results = [
        extract(0.045, 0.97),
        extract(0.020, 0.97),
        reply(77, 78),
        estimate(1.0, 0, [True] * 5),
    ]
    assert failed(results) == []


def test_one_priced_uncovered_job_fails():
    results = [
        extract(0.014, 0.973),
        reply(77, 78),
        estimate(1.0, 0, [True, True, True, True, False]),
    ]
    assert failed(results) == [("estimate", "declined_uncovered")]


def test_missing_eval_fails():
    assert ("reply", "pass_rate") in failed([extract(0.014, 0.973), estimate(1.0, 0, [True])])
