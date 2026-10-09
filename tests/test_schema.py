import pytest
from pydantic import ValidationError

from foreman.schema import JobType, Lead


def test_non_lead_defaults_to_empty():
    lead = Lead(is_lead=False)
    assert lead.customer_name is None
    assert lead.job_types == []
    assert lead.urgency is None
    assert lead.missing_info == []


def test_multiple_job_types():
    lead = Lead(is_lead=True, job_types=["kitchen", "flooring"])
    assert lead.job_types == [JobType.KITCHEN, JobType.FLOORING]


def test_rejects_unknown_enum_value():
    with pytest.raises(ValidationError):
        Lead(is_lead=True, urgency="unknown")


def test_round_trips_through_json():
    lead = Lead(is_lead=True, budget_max=20000, job_types=["roofing"])
    assert Lead.model_validate_json(lead.model_dump_json()) == lead
