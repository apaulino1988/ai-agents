from datetime import datetime, timedelta

import pytest

from app.services import booking, outbox, tasks
from app.tools import execute_tool


def _future_date() -> str:
    """Next Monday at least a week out — always an open business day."""
    d = datetime.now() + timedelta(days=8)
    while d.weekday() != 0:
        d += timedelta(days=1)
    return d.strftime("%Y-%m-%d")


def test_create_and_get_task(temp_db):
    task = tasks.create_task("secretary", "followup", "appointment_confirmation", {"x": 1})
    assert task["status"] == "pending"
    assert task["payload"] == {"x": 1}
    assert tasks.get_task(task["id"])["to_agent"] == "followup"


def test_due_filtering(temp_db):
    past = (datetime.now() - timedelta(hours=1)).isoformat(timespec="seconds")
    future = (datetime.now() + timedelta(days=2)).isoformat(timespec="seconds")
    t_past = tasks.create_task("secretary", "followup", "appointment_confirmation", {}, past)
    t_future = tasks.create_task("secretary", "followup", "appointment_confirmation", {}, future)
    t_nodue = tasks.create_task("secretary", "followup", "appointment_confirmation", {})

    due_ids = {t["id"] for t in tasks.due_tasks("followup")}
    assert t_past["id"] in due_ids
    assert t_nodue["id"] in due_ids
    assert t_future["id"] not in due_ids

    all_ids = {t["id"] for t in tasks.due_tasks("followup", include_future=True)}
    assert t_future["id"] in all_ids


def test_due_excludes_other_agents_and_done(temp_db):
    t1 = tasks.create_task("secretary", "followup", "appointment_confirmation", {})
    tasks.create_task("secretary", "someone-else", "other", {})
    tasks.complete_task(t1["id"], "done!")
    assert tasks.due_tasks("followup") == []
    assert tasks.get_task(t1["id"])["result"] == "done!"


def test_fail_task(temp_db):
    t = tasks.create_task("secretary", "followup", "appointment_confirmation", {})
    failed = tasks.fail_task(t["id"], "boom")
    assert failed["status"] == "failed"


def test_schedule_confirmation_due_24h_before(temp_db):
    appt = booking.book_appointment("cleaning", _future_date(), "10:00", "Alice", "555-0001")
    task = tasks.schedule_confirmation(appt["id"])
    starts = datetime.strptime(f"{appt['date']} 10:00", "%Y-%m-%d %H:%M")
    assert task["due_at"] == (starts - timedelta(hours=24)).isoformat(timespec="seconds")
    assert task["payload"] == {"appointment_id": appt["id"]}
    assert task["from_agent"] == "secretary"
    assert task["to_agent"] == "followup"


def test_schedule_confirmation_rejects_cancelled(temp_db):
    appt = booking.book_appointment("cleaning", _future_date(), "10:00", "Alice", "555-0001")
    booking.cancel_appointment(appt["id"])
    with pytest.raises(booking.BookingError):
        tasks.schedule_confirmation(appt["id"])


def test_secretary_tool_schedules_followup(temp_db):
    appt = booking.book_appointment("cleaning", _future_date(), "10:00", "Alice", "555-0001")
    _result, is_error = execute_tool("schedule_followup", {"appointment_id": appt["id"]})
    assert not is_error
    queued = tasks.due_tasks("followup", include_future=True)
    assert len(queued) == 1
    assert queued[0]["payload"]["appointment_id"] == appt["id"]


def test_outbox_record_and_list(temp_db):
    msg = outbox.record("555-0001", "See you Monday!", customer_name="Alice", appointment_id=1)
    assert msg["channel"] == "sms-outbox"
    listed = outbox.list_messages()
    assert len(listed) == 1
    assert listed[0]["body"] == "See you Monday!"
