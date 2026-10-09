from types import SimpleNamespace

import pytest

from foreman.extract import ExtractionError, estimate_cost, extract
from foreman.schema import Lead


def fake_client(parsed, refusal=None):
    completion = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(parsed=parsed, refusal=refusal))],
        usage=SimpleNamespace(prompt_tokens=1000, completion_tokens=200),
    )
    completions = SimpleNamespace(parse=lambda **kwargs: completion)
    return SimpleNamespace(chat=SimpleNamespace(completions=completions))


def test_extract_returns_lead_and_cost():
    lead = Lead(is_lead=True, job_types=["roofing"])
    result = extract("roof leaking", model="gpt-4o-mini", client=fake_client(lead))
    assert result.lead == lead
    assert result.cost_usd == pytest.approx((1000 * 0.15 + 200 * 0.60) / 1_000_000)


def test_extract_raises_on_refusal():
    with pytest.raises(ExtractionError, match="nope"):
        extract("x", model="gpt-4o-mini", client=fake_client(None, refusal="nope"))


def test_unknown_model_has_no_cost():
    assert estimate_cost("some-new-model", 100, 100) is None
