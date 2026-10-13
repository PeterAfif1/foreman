import logging

import pytest
from fastapi.testclient import TestClient

from foreman.api import HideHealthChecks, create_app, get_extractor, get_replier, get_store
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


def fake_reply(text, lead):
    from foreman.reply import NotALead, ReplyDraft, what_to_ask

    if not lead.is_lead:
        raise NotALead("no reply for spam")
    return ReplyDraft(
        text="Hi dana! Where is the house?\nThanks!",
        asks=what_to_ask(lead),
        model="gpt-4o-mini",
        prompt_version="r2",
        cost_usd=0.0001,
        latency_ms=500.0,
    )


PASSWORD = "correct horse battery"


def make_client(tmp_path, auth):
    app = create_app(auth)
    store = Store(tmp_path / "test.db")
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_extractor] = lambda: fake_extract
    app.dependency_overrides[get_replier] = lambda: fake_reply
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
        "/api/leads", json={"text": "kitchen redo under 30k - dana", "received_at": "2026-10-12"}
    )
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "pending"
    assert body["extracted"]["customer_name"] == "dana"
    assert body["received_at"] == "2026-10-12"
    assert client.get(f"/api/leads/{body['id']}").json()["text"] == "kitchen redo under 30k - dana"


def test_failed_extraction_still_saves_the_message(client):
    body = client.post("/api/leads", json={"text": "boom"}).json()
    assert body["extracted"] is None
    assert body["error"].startswith("RuntimeError")


def test_empty_text_is_rejected(client):
    assert client.post("/api/leads", json={"text": ""}).status_code == 422


def test_approve_unchanged_records_no_edits(client):
    lead = client.post("/api/leads", json={"text": "x"}).json()
    r = client.post(f"/api/leads/{lead['id']}/approve", json=lead["extracted"])
    assert r.json()["status"] == "approved"
    assert r.json()["edited_fields"] == []


def test_approve_with_fixes_records_edited_fields(client):
    lead = client.post("/api/leads", json={"text": "x"}).json()
    fixed = {**lead["extracted"], "budget_max": None, "location": "Burbank"}
    r = client.post(f"/api/leads/{lead['id']}/approve", json=fixed).json()
    assert sorted(r["edited_fields"]) == ["budget_max", "location"]


def test_job_type_order_is_not_an_edit(client):
    lead = client.post("/api/leads", json={"text": "x"}).json()
    client.post(
        f"/api/leads/{lead['id']}/approve", json={**lead["extracted"], "job_types": ["kitchen"]}
    )
    assert client.get(f"/api/leads/{lead['id']}").json()["edited_fields"] == []


def test_list_filters_by_status(client):
    a = client.post("/api/leads", json={"text": "a"}).json()
    client.post("/api/leads", json={"text": "b"})
    client.post(f"/api/leads/{a['id']}/approve", json=a["extracted"])
    assert [x["text"] for x in client.get("/api/leads?status=pending").json()] == ["b"]
    assert len(client.get("/api/leads").json()) == 2


def test_missing_lead_is_404(client):
    assert client.get("/api/leads/999").status_code == 404
    assert client.post("/api/leads/999/approve", json={"is_lead": False}).status_code == 404


def test_stats_report_edit_rates(client):
    for text in ["a", "b"]:
        client.post("/api/leads", json={"text": text})
    leads = client.get("/api/leads").json()
    client.post(f"/api/leads/{leads[0]['id']}/approve", json=leads[0]["extracted"])
    client.post(
        f"/api/leads/{leads[1]['id']}/approve", json={**leads[1]["extracted"], "location": "Encino"}
    )
    s = client.get("/api/stats").json()
    assert s["approved"] == 2
    assert s["approved_without_edits_rate"] == 0.5
    assert s["field_edit_rate"]["location"] == 0.5
    assert s["field_edit_rate"]["budget_max"] == 0.0


def test_export_matches_eval_format(client):
    lead = client.post(
        "/api/leads", json={"text": "kitchen - dana", "received_at": "2026-10-12"}
    ).json()
    client.post("/api/leads", json={"text": "still pending"})
    client.post(
        f"/api/leads/{lead['id']}/approve", json={**lead["extracted"], "location": "Encino"}
    )
    lines = client.get("/api/export").text.strip().splitlines()
    assert len(lines) == 1
    row = Lead.model_validate(__import__("json").loads(lines[0])["label"])
    assert row.location == "Encino"


def test_board_page_is_served(client):
    assert client.get("/").status_code == 200


def test_default_stages(client):
    stages = client.get("/api/stages").json()
    assert [s["key"] for s in stages][:2] == ["new", "contacted"]
    assert {s["key"] for s in stages if s["closed"]} == {"done", "lost"}


def test_new_leads_go_on_top_of_the_first_column(client):
    a = client.post("/api/leads", json={"text": "a"}).json()
    b = client.post("/api/leads", json={"text": "b"}).json()
    assert a["stage"] == b["stage"] == "new"
    assert [x["text"] for x in client.get("/api/leads").json()] == ["b", "a"]


def test_move_between_columns_and_reorder(client):
    ids = [client.post("/api/leads", json={"text": t}).json()["id"] for t in "abc"]
    # Column "new" is now c, b, a. Move a to the top of "contacted".
    moved = client.post(f"/api/leads/{ids[0]}/move", json={"stage": "contacted", "index": 0})
    assert moved.json()["stage"] == "contacted"
    # Reorder inside "new": put c below b.
    client.post(f"/api/leads/{ids[2]}/move", json={"stage": "new", "index": 1})
    new_col = [x["text"] for x in client.get("/api/leads").json() if x["stage"] == "new"]
    assert new_col == ["b", "c"]


def test_move_is_recorded_in_history(client):
    lead = client.post("/api/leads", json={"text": "a"}).json()
    client.post(f"/api/leads/{lead['id']}/move", json={"stage": "site_visit", "index": 0})
    client.post(f"/api/leads/{lead['id']}/approve", json=lead["extracted"])
    events = client.get(f"/api/leads/{lead['id']}/events").json()
    assert [e["kind"] for e in events] == ["created", "moved", "approved"]
    assert events[1]["detail"] == {"from": "new", "to": "site_visit"}


def test_reorder_in_same_column_is_not_a_move(client):
    lead = client.post("/api/leads", json={"text": "a"}).json()
    client.post(f"/api/leads/{lead['id']}/move", json={"stage": "new", "index": 0})
    kinds = [e["kind"] for e in client.get(f"/api/leads/{lead['id']}/events").json()]
    assert kinds == ["created"]


def test_move_to_unknown_stage_is_rejected(client):
    lead = client.post("/api/leads", json={"text": "a"}).json()
    r = client.post(f"/api/leads/{lead['id']}/move", json={"stage": "nowhere", "index": 0})
    assert r.status_code == 422


def test_old_database_gets_new_columns(tmp_path):
    import sqlite3

    db = tmp_path / "old.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE leads (id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT NOT NULL, "
        "received_at TEXT NOT NULL, created_at TEXT NOT NULL, status TEXT NOT NULL "
        "DEFAULT 'pending', extracted TEXT, raw_extracted TEXT, approved TEXT, "
        "edited_fields TEXT, model TEXT, prompt_version TEXT, cost_usd REAL, "
        "latency_ms REAL, error TEXT)"
    )
    conn.execute(
        "INSERT INTO leads (text, received_at, created_at) VALUES ('old', '2026-10-12', 'x')"
    )
    conn.commit()
    conn.close()
    [record] = Store(db).list_leads()
    assert record.text == "old"
    assert record.stage == "new"


def test_everything_needs_login(secured):
    assert secured.get("/api/leads").status_code == 401
    assert secured.post("/api/leads", json={"text": "x"}).status_code == 401
    assert secured.get("/api/export").status_code == 401
    assert secured.get("/docs").status_code == 401
    page = secured.get("/", headers={"accept": "text/html"}, follow_redirects=False)
    assert page.status_code == 303
    assert page.headers["location"] == "/login"


def test_login_page_and_health_are_public(secured):
    assert secured.get("/login").status_code == 200
    assert secured.get("/health").status_code == 200


def test_wrong_password_is_rejected(secured):
    assert secured.post("/login", json={"password": "nope"}).status_code == 401
    assert secured.get("/api/leads").status_code == 401


def test_right_password_opens_everything(secured):
    assert secured.post("/login", json={"password": PASSWORD}).status_code == 200
    assert secured.get("/api/leads").status_code == 200
    assert secured.post("/api/leads", json={"text": "x"}).status_code == 201


def test_logout_ends_the_session(secured):
    secured.post("/login", json={"password": PASSWORD})
    secured.post("/logout")
    assert secured.get("/api/leads").status_code == 401


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


def access_record(path):
    # Same shape uvicorn uses: (client, method, path, http version, status)
    return logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        "",
        0,
        '%s - "%s %s HTTP/%s" %d',
        ("127.0.0.1:5000", "GET", path, "1.1", 200),
        None,
    )


def test_health_checks_are_hidden_from_the_access_log():
    f = HideHealthChecks()
    assert f.filter(access_record("/health")) is False
    assert f.filter(access_record("/api/leads")) is True


def test_notes_show_up_in_history(client):
    lead = client.post("/api/leads", json={"text": "a"}).json()
    r = client.post(f"/api/leads/{lead['id']}/notes", json={"text": "  called, left voicemail  "})
    assert r.status_code == 201
    assert r.json()["detail"] == {"text": "called, left voicemail"}
    kinds = [e["kind"] for e in client.get(f"/api/leads/{lead['id']}/events").json()]
    assert kinds == ["created", "note"]


def test_empty_note_is_rejected(client):
    lead = client.post("/api/leads", json={"text": "a"}).json()
    assert client.post(f"/api/leads/{lead['id']}/notes", json={"text": ""}).status_code == 422
    assert client.post("/api/leads/999/notes", json={"text": "x"}).status_code == 404


def test_edit_after_check_is_not_an_ai_mistake(client):
    lead = client.post("/api/leads", json={"text": "a"}).json()
    checked = client.post(f"/api/leads/{lead['id']}/approve", json=lead["extracted"]).json()
    assert checked["edited_fields"] == []
    new = {**checked["approved"], "contact": "818-555-0000"}
    updated = client.put(f"/api/leads/{lead['id']}/fields", json=new).json()
    assert updated["approved"]["contact"] == "818-555-0000"
    assert updated["edited_fields"] == []  # the AI's record is untouched
    last = client.get(f"/api/leads/{lead['id']}/events").json()[-1]
    assert last == {**last, "kind": "edited", "detail": {"fields": ["contact"]}}
    assert client.get("/api/stats").json()["approved_without_edits_rate"] == 1.0


def test_edit_before_check_is_refused(client):
    lead = client.post("/api/leads", json={"text": "a"}).json()
    r = client.put(f"/api/leads/{lead['id']}/fields", json=lead["extracted"])
    assert r.status_code == 409


def test_saving_without_changes_logs_nothing(client):
    lead = client.post("/api/leads", json={"text": "a"}).json()
    client.post(f"/api/leads/{lead['id']}/approve", json=lead["extracted"])
    client.put(f"/api/leads/{lead['id']}/fields", json=lead["extracted"])
    kinds = [e["kind"] for e in client.get(f"/api/leads/{lead['id']}/events").json()]
    assert kinds == ["created", "approved"]


def test_draft_reply_is_logged_not_sent(client):
    lead = client.post("/api/leads", json={"text": "x"}).json()
    r = client.post(f"/api/leads/{lead['id']}/reply")
    assert r.status_code == 200
    assert r.json()["text"].startswith("Hi dana")
    assert "where the job is" in r.json()["asks"]
    last = client.get(f"/api/leads/{lead['id']}/events").json()[-1]
    assert last["kind"] == "reply_drafted"


def test_no_draft_for_spam(client):
    lead = client.post("/api/leads", json={"text": "x"}).json()
    client.post(f"/api/leads/{lead['id']}/approve", json={**lead["extracted"], "is_lead": False})
    assert client.post(f"/api/leads/{lead['id']}/reply").status_code == 409


def test_marking_sent_records_edits_and_moves_new_card_to_contacted(client):
    lead = client.post("/api/leads", json={"text": "x"}).json()
    client.post(f"/api/leads/{lead['id']}/reply")
    r = client.post(
        f"/api/leads/{lead['id']}/reply/sent", json={"text": "Hi dana! Where's the house?"}
    )
    assert r.json()["stage"] == "contacted"
    sent = client.get(f"/api/leads/{lead['id']}/events").json()
    kinds = [e["kind"] for e in sent]
    assert kinds[-2:] == ["reply_sent", "moved"]
    assert sent[-2]["detail"]["edited"] is True
    stats = client.get("/api/stats").json()
    assert (stats["replies_sent"], stats["drafts_sent_unedited"]) == (1, 0)


def test_sending_the_draft_as_is_counts_as_unedited(client):
    lead = client.post("/api/leads", json={"text": "x"}).json()
    draft = client.post(f"/api/leads/{lead['id']}/reply").json()["text"]
    client.post(f"/api/leads/{lead['id']}/reply/sent", json={"text": draft})
    assert client.get("/api/stats").json()["drafts_sent_unedited"] == 1


def test_sent_does_not_move_cards_past_new(client):
    lead = client.post("/api/leads", json={"text": "x"}).json()
    client.post(f"/api/leads/{lead['id']}/move", json={"stage": "quote_sent", "index": 0})
    r = client.post(f"/api/leads/{lead['id']}/reply/sent", json={"text": "following up"})
    assert r.json()["stage"] == "quote_sent"


def test_source_is_saved(client):
    lead = client.post("/api/leads", json={"text": "x", "source": "call"}).json()
    assert lead["source"] == "call"
    assert client.post("/api/leads", json={"text": "x"}).json()["source"] is None


def test_unknown_source_is_rejected(client):
    assert client.post("/api/leads", json={"text": "x", "source": "pigeon"}).status_code == 422


def test_favicon_is_public(secured):
    r = secured.get("/favicon.svg")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/svg+xml")


def test_adding_a_column_twice_is_harmless(tmp_path):
    import sqlite3

    from foreman.store import add_column

    conn = sqlite3.connect(tmp_path / "x.db")
    conn.execute("CREATE TABLE leads (id INTEGER)")
    add_column(conn, "source", "TEXT")
    add_column(conn, "source", "TEXT")  # a second server got there first
    assert [r[1] for r in conn.execute("PRAGMA table_info(leads)")] == ["id", "source"]


def test_concurrent_first_requests_share_one_store(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor

    from foreman import api as api_module

    monkeypatch.setenv("FOREMAN_DB", str(tmp_path / "shared.db"))
    api_module._open_store.cache_clear()
    with ThreadPoolExecutor(8) as pool:
        stores = list(pool.map(lambda _: api_module.get_store(), range(8)))
    assert len({id(s) for s in stores}) == 1
    api_module._open_store.cache_clear()
