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
