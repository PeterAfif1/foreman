import pytest

from eval.metrics import aggregate, classify, score_example
from foreman.schema import Lead


@pytest.mark.parametrize(
    "field_name, pred, truth, expected",
    [
        ("budget_max", None, None, "correct"),
        ("budget_max", 20000, None, "hallucination"),
        ("budget_max", None, 20000, "omission"),
        ("budget_max", 15000, 20000, "wrong"),
        ("budget_max", 20000, 20000, "correct"),
        ("job_types", [], [], "correct"),
        ("job_types", ["flooring", "kitchen"], ["kitchen", "flooring"], "correct"),
        ("job_types", ["kitchen"], ["kitchen", "flooring"], "wrong"),
        ("contact", "+1 (818) 555-0142", "818.555.0142", "correct"),
        ("contact", "Bob@Mail.com ", "bob@mail.com", "correct"),
        ("location", "Glendale, CA", "glendale", "correct"),
        ("location", "Burbank", "Glendale", "wrong"),
        ("location", "LA", "Lakewood", "wrong"),
        ("customer_name", "  maria  ", "Maria", "correct"),
        ("customer_name", "", None, "correct"),
        ("urgency", "soon", None, "hallucination"),
    ],
)
def test_classify(field_name, pred, truth, expected):
    assert classify(field_name, pred, truth) == expected


def test_spam_truth_scores_no_fields():
    assert score_example(Lead(is_lead=True, budget_max=5), Lead(is_lead=False)) == {}


def test_aggregate_rates_use_correct_denominators():
    truth = Lead(is_lead=True, customer_name="Maria", job_types=["kitchen"])
    # Gets name right, invents a budget, misses the job type.
    pred = Lead(is_lead=True, customer_name="Maria", budget_max=20000)
    report = aggregate([(pred, truth)])

    # 7 fields: truth filled for name + job_types (2), empty for the other 5.
    assert report.hallucination_rate == pytest.approx(1 / 5)
    assert report.omission_rate == pytest.approx(1 / 2)
    assert report.overall_accuracy == pytest.approx(5 / 7)
    assert report.field_accuracy("budget_max") == 0.0
    assert report.field_accuracy("customer_name") == 1.0


def test_is_lead_precision_recall():
    lead, spam = Lead(is_lead=True), Lead(is_lead=False)
    pairs = [
        (lead, lead),  # tp
        (lead, spam),  # fp
        (spam, lead),  # fn
        (spam, spam),  # tn
    ]
    report = aggregate(pairs)
    assert report.is_lead_precision == 0.5
    assert report.is_lead_recall == 0.5


def test_cost_and_latency_skip_unknowns():
    lead = Lead(is_lead=True)
    report = aggregate([(lead, lead), (lead, lead)], costs=[0.001, None], latencies=[100, 300])
    assert report.avg_cost_usd == 0.001
    assert report.median_latency_ms == 200


def test_empty_input():
    report = aggregate([])
    assert report.overall_accuracy is None
    assert report.is_lead_precision is None
