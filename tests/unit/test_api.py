from fastapi.testclient import TestClient

from app.main import app


def test_health(temp_db):
    client = TestClient(app)
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_chat_page_served(temp_db):
    client = TestClient(app)
    res = client.get("/")
    assert res.status_code == 200
    assert "AI Secretary" in res.text


def test_chat_rejects_empty_message(temp_db):
    client = TestClient(app)
    res = client.post("/chat", json={"message": "   "})
    assert res.status_code == 400


def test_followup_run_with_empty_queue(temp_db):
    client = TestClient(app)
    res = client.post("/agents/followup/run")
    assert res.status_code == 200
    assert res.json() == {"processed": 0, "results": []}


def test_tasks_and_outbox_endpoints(temp_db):
    client = TestClient(app)
    assert client.get("/agents/tasks").json() == []
    assert client.get("/outbox").json() == []


def test_sms_webhook_replies_twiml(temp_db, monkeypatch):
    from app import main as main_module

    monkeypatch.setattr(
        main_module.agent, "run_turn", lambda history, msg: ("Got it <ok>!", [])
    )
    client = TestClient(app)
    res = client.post("/webhooks/sms", data={"From": "+15551112222", "Body": "CONFIRM"})
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("application/xml")
    assert "<Message>Got it &lt;ok&gt;!</Message>" in res.text


def test_sms_webhook_requires_from_and_body(temp_db):
    client = TestClient(app)
    assert client.post("/webhooks/sms", data={"From": "+15551112222"}).status_code == 400
    assert client.post("/webhooks/sms", data={"Body": "hello"}).status_code == 400


def test_sms_webhook_rejects_bad_signature(temp_db, monkeypatch):
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "secret-token")
    monkeypatch.setenv("TWILIO_VALIDATE", "true")
    client = TestClient(app)
    res = client.post(
        "/webhooks/sms",
        data={"From": "+15551112222", "Body": "hi"},
        headers={"X-Twilio-Signature": "forged"},
    )
    assert res.status_code == 403
