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
