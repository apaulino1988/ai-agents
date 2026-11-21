from app.services import knowledge


def test_profile_loads():
    profile = knowledge.get_profile()
    assert profile["name"]
    assert profile["services"]
    assert profile["hours"]


def test_get_service_by_id():
    service = knowledge.get_service("cleaning")
    assert service is not None
    assert service["duration_minutes"] == 60
    assert service["price_usd"] == 120


def test_get_service_unknown_returns_none():
    assert knowledge.get_service("not-a-service") is None


def test_hours_for_day():
    assert knowledge.hours_for_day("Monday") == ("09:00", "17:00")
    assert knowledge.hours_for_day("sunday") is None


def test_prompt_text_contains_key_facts():
    text = knowledge.profile_as_prompt_text()
    assert "Dental Cleaning & Exam" in text
    assert "$120" in text
    assert "Sunday: Closed" in text
    assert "Cancellations require 24 hours notice" in text
