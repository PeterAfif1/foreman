"""Scoring a predicted Lead against a hand-labeled one.

Every scored field lands in exactly one bucket:
  correct       both empty, or both filled and matching
  hallucination predicted filled, truth empty   (the failure we care most about)
  omission      predicted empty, truth filled
  wrong         both filled, not matching

scope_summary and missing_info are free text and are not scored here yet.
"""

import re
import statistics
from collections import Counter
from dataclasses import dataclass, field

from foreman.schema import Lead

SCORED_FIELDS = [
    "customer_name",
    "contact",
    "job_types",
    "location",
    "budget_min",
    "budget_max",
    "urgency",
]

OUTCOMES = ("correct", "hallucination", "omission", "wrong")


def _norm_text(value: str) -> str:
    value = re.sub(r"[^\w\s@.]", " ", value.casefold())
    return " ".join(value.split())


def _is_empty(value) -> bool:
    return value is None or value == [] or (isinstance(value, str) and not value.strip())


def _contact_key(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if len(digits) >= 7:
        return digits[-10:]  # ignore country code and formatting
    return value.strip().casefold()


def values_match(field_name: str, pred, truth) -> bool:
    if field_name == "job_types":
        return set(pred) == set(truth)
    if field_name == "contact":
        return _contact_key(pred) == _contact_key(truth)
    if field_name == "location":
        # Lenient on purpose: "Glendale" vs "Glendale, CA" is the same answer.
        # Token subset, not substring, so "LA" doesn't match "Lakewood".
        p, t = set(_norm_text(pred).split()), set(_norm_text(truth).split())
        return bool(p and t) and (p <= t or t <= p)
    if field_name == "customer_name":
        return _norm_text(pred) == _norm_text(truth)
    return pred == truth


def classify(field_name: str, pred, truth) -> str:
    pred_empty, truth_empty = _is_empty(pred), _is_empty(truth)
    if pred_empty and truth_empty:
        return "correct"
    if truth_empty:
        return "hallucination"
    if pred_empty:
        return "omission"
    return "correct" if values_match(field_name, pred, truth) else "wrong"


def score_example(pred: Lead, truth: Lead) -> dict[str, str]:
    """Field outcomes for one example. Fields are only scored when the truth is a
    real lead; for spam, is_lead is the only thing that matters."""
    if not truth.is_lead:
        return {}
    return {f: classify(f, getattr(pred, f), getattr(truth, f)) for f in SCORED_FIELDS}


@dataclass
class Report:
    n_examples: int
    field_counts: dict[str, Counter] = field(default_factory=dict)
    is_lead_precision: float | None = None
    is_lead_recall: float | None = None
    overall_accuracy: float | None = None
    hallucination_rate: float | None = None
    omission_rate: float | None = None
    avg_cost_usd: float | None = None
    median_latency_ms: float | None = None

    def field_accuracy(self, name: str) -> float | None:
        c = self.field_counts[name]
        total = sum(c.values())
        return c["correct"] / total if total else None


def _ratio(num: int, den: int) -> float | None:
    return num / den if den else None


def aggregate(
    pairs: list[tuple[Lead, Lead]],
    costs: list[float | None] | None = None,
    latencies: list[float] | None = None,
) -> Report:
    """pairs is a list of (predicted, truth)."""
    report = Report(n_examples=len(pairs))
    report.field_counts = {f: Counter() for f in SCORED_FIELDS}
    truth_empty = truth_filled = 0

    for pred, truth in pairs:
        for name, outcome in score_example(pred, truth).items():
            report.field_counts[name][outcome] += 1
            if _is_empty(getattr(truth, name)):
                truth_empty += 1
            else:
                truth_filled += 1

    totals = Counter()
    for c in report.field_counts.values():
        totals.update(c)
    report.overall_accuracy = _ratio(totals["correct"], sum(totals.values()))
    # Rates use the right denominator: you can only hallucinate where the truth is
    # empty, and only omit where it is filled.
    report.hallucination_rate = _ratio(totals["hallucination"], truth_empty)
    report.omission_rate = _ratio(totals["omission"], truth_filled)

    tp = sum(1 for p, t in pairs if p.is_lead and t.is_lead)
    fp = sum(1 for p, t in pairs if p.is_lead and not t.is_lead)
    fn = sum(1 for p, t in pairs if not p.is_lead and t.is_lead)
    report.is_lead_precision = _ratio(tp, tp + fp)
    report.is_lead_recall = _ratio(tp, tp + fn)

    known_costs = [c for c in (costs or []) if c is not None]
    report.avg_cost_usd = statistics.fmean(known_costs) if known_costs else None
    report.median_latency_ms = statistics.median(latencies) if latencies else None
    return report
