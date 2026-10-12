import json
import sys

from eval import run_eval
from foreman.extract import Extraction
from foreman.schema import Lead


def test_run_eval_end_to_end(tmp_path, monkeypatch):
    data = tmp_path / "tiny.jsonl"
    rows = [
        {
            "id": "a",
            "source": "handwritten",
            "labeled_by": "t",
            "text": "roof leak",
            "label": {"is_lead": True, "job_types": ["roofing"], "urgency": "emergency"},
        },
        {
            "id": "b",
            "source": "handwritten",
            "labeled_by": "t",
            "text": "buy SEO",
            "label": {"is_lead": False},
        },
    ]
    data.write_text("\n".join(json.dumps(r) for r in rows))

    def fake_extract(text, model=None, received_at=None):
        if text == "buy SEO":
            raise RuntimeError("boom")
        lead = Lead(is_lead=True, job_types=["roofing"], budget_max=9000)
        return Extraction(lead, "gpt-4o-mini", "v0", 100, 50, 0.0001, 120.0)

    monkeypatch.setattr(run_eval, "extract", fake_extract)
    monkeypatch.setattr(run_eval, "RESULTS_DIR", tmp_path / "results")
    monkeypatch.setattr(sys, "argv", ["run_eval", "--label", "test", "--data", str(data)])
    run_eval.main()

    [out_file] = (tmp_path / "results").glob("*_test.json")
    out = json.loads(out_file.read_text())
    assert out["dataset"]["n"] == 2
    assert out["summary"]["errors"] == 1
    assert out["fields"]["budget_max"] == {"hallucination": 1}
    assert out["fields"]["urgency"] == {"omission": 1}
    assert out["examples"][1]["error"].startswith("RuntimeError")
