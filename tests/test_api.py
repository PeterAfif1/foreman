import pytest
from fastapi.testclient import TestClient

from foreman.api import create_app, get_extractor, get_store
from foreman.auth import AuthSettings, load_settings
from foreman.extract import Extraction
from foreman.schema import Lead
from foreman.store import Store


def fake_extract(text, received_at=None):
    if text == "boom":
        raise RuntimeError("model down")
    lead = Lead(is_lead=True, customer_name="dana", job_types=["kitchen"], budget_max=30000)
    return Extraction(
        lead=lead,
        raw_lead=lead,
        model="gpt-4o-mini",
        prompt_version="v3",
        input_tokens=100,
        output_tokens=50,
        cost_usd=0.0002,
        latency_ms=900.0,
    )


PASSWORD = "correct horse battery"


def make_client(tmp_path, auth):
    app = create_app(auth)
    store = Store(tmp_path / "test.db")
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_extractor] = lambda: fake_extract
    return TestClient(app)


@pytest.fixture
def client(tmp_path):
    return make_client(tmp_path, AuthSettings(enabled=False))


@pytest.fixture
def secured(tmp_path):
    return make_client(
        tmp_path, AuthSettings(enabled=True, password=PASSWORD, secret_key="test-key")
    )


def test_create_extracts_and_saves_pending(client):
    r = client.post(
        "/leads", json={"text": "kitchen redo under 30k - dana", "received_at": "2026-10-12"}
    )
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "pending"
    assert body["extracted"]["customer_name"] == "dana"
    assert body["received_at"] == "2026-10-12"
    assert client.get(f"/leads/{body['id']}").json()["text"] == "kitchen redo under 30k - dana"


def test_failed_extraction_still_saves_the_message(client):
    body = client.post("/leads", json={"text": "boom"}).json()
    assert body["extracted"] is None
    assert body["error"].startswith("RuntimeError")


def test_empty_text_is_rejected(client):
    assert client.post("/leads", json={"text": ""}).status_code == 422


def test_approve_unchanged_records_no_edits(client):
    lead = client.post("/leads", json={"text": "x"}).json()
    r = client.post(f"/leads/{lead['id']}/approve", json=lead["extracted"])
    assert r.json()["status"] == "approved"
    assert r.json()["edited_fields"] == []


def test_approve_with_fixes_records_edited_fields(client):
    lead = client.post("/leads", json={"text": "x"}).json()
    fixed = {**lead["extracted"], "budget_max": None, "location": "Burbank"}
    r = client.post(f"/leads/{lead['id']}/approve", json=fixed).json()
    assert sorted(r["edited_fields"]) == ["budget_max", "location"]


def test_job_type_order_is_not_an_edit(client):
    lead = client.post("/leads", json={"text": "x"}).json()
    client.post(
        f"/leads/{lead['id']}/approve", json={**lead["extracted"], "job_types": ["kitchen"]}
    )
    assert client.get(f"/leads/{lead['id']}").json()["edited_fields"] == []


def test_list_filters_by_status(client):
    a = client.post("/leads", json={"text": "a"}).json()
    client.post("/leads", json={"text": "b"})
    client.post(f"/leads/{a['id']}/approve", json=a["extracted"])
    assert [x["text"] for x in client.get("/leads?status=pending").json()] == ["b"]
    assert len(client.get("/leads").json()) == 2


def test_missing_lead_is_404(client):
    assert client.get("/leads/999").status_code == 404
    assert client.post("/leads/999/approve", json={"is_lead": False}).status_code == 404


def test_stats_report_edit_rates(client):
    for text in ["a", "b"]:
        client.post("/leads", json={"text": text})
    leads = client.get("/leads").json()
    client.post(f"/leads/{leads[0]['id']}/approve", json=leads[0]["extracted"])
    client.post(
        f"/leads/{leads[1]['id']}/approve", json={**leads[1]["extracted"], "location": "Encino"}
    )
    s = client.get("/stats").json()
    assert s["approved"] == 2
    assert s["approved_without_edits_rate"] == 0.5
    assert s["field_edit_rate"]["location"] == 0.5
    assert s["field_edit_rate"]["budget_max"] == 0.0


def test_export_matches_eval_format(client):
    lead = client.post(
        "/leads", json={"text": "kitchen - dana", "received_at": "2026-10-12"}
    ).json()
    client.post("/leads", json={"text": "still pending"})
    client.post(f"/leads/{lead['id']}/approve", json={**lead["extracted"], "location": "Encino"})
    lines = client.get("/export").text.strip().splitlines()
    assert len(lines) == 1
    row = Lead.model_validate(__import__("json").loads(lines[0])["label"])
    assert row.location == "Encino"


def test_dashboard_is_served(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "<title>Foreman</title>" in r.text


def test_everything_needs_login(secured):
    assert secured.get("/leads").status_code == 401
    assert secured.post("/leads", json={"text": "x"}).status_code == 401
    assert secured.get("/export").status_code == 401
    assert secured.get("/docs").status_code == 401
    page = secured.get("/", headers={"accept": "text/html"}, follow_redirects=False)
    assert page.status_code == 303
    assert page.headers["location"] == "/login"


def test_login_page_and_health_are_public(secured):
    assert secured.get("/login").status_code == 200
    assert secured.get("/health").status_code == 200


def test_wrong_password_is_rejected(secured):
    assert secured.post("/login", json={"password": "nope"}).status_code == 401
    assert secured.get("/leads").status_code == 401


def test_right_password_opens_everything(secured):
    assert secured.post("/login", json={"password": PASSWORD}).status_code == 200
    assert secured.get("/leads").status_code == 200
    assert secured.post("/leads", json={"text": "x"}).status_code == 201


def test_logout_ends_the_session(secured):
    secured.post("/login", json={"password": PASSWORD})
    secured.post("/logout")
    assert secured.get("/leads").status_code == 401


def test_lockout_after_too_many_wrong_passwords(secured):
    for _ in range(5):
        secured.post("/login", json={"password": "nope"})
    # Even the right password is refused while locked out.
    assert secured.post("/login", json={"password": PASSWORD}).status_code == 429


def test_startup_fails_without_a_password(monkeypatch):
    monkeypatch.setattr("foreman.auth.load_dotenv", lambda: None)  # ignore the real .env
    for var in ["FOREMAN_AUTH", "FOREMAN_PASSWORD", "FOREMAN_SECRET_KEY"]:
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(RuntimeError, match="FOREMAN_PASSWORD"):
        load_settings()


def test_short_password_is_refused(monkeypatch):
    monkeypatch.setattr("foreman.auth.load_dotenv", lambda: None)  # ignore the real .env
    monkeypatch.setenv("FOREMAN_PASSWORD", "short")
    monkeypatch.setenv("FOREMAN_SECRET_KEY", "k")
    monkeypatch.delenv("FOREMAN_AUTH", raising=False)
    with pytest.raises(RuntimeError, match="12 characters"):
        load_settings()


def test_auth_off_must_be_explicit(monkeypatch):
    monkeypatch.setattr("foreman.auth.load_dotenv", lambda: None)  # ignore the real .env
    monkeypatch.setenv("FOREMAN_AUTH", "off")
    assert load_settings().enabled is False
