"""Agent task queue — the handoff protocol between agents.

An agent delegates work by creating a task addressed to another agent; the
receiving agent processes it independently. Plain service layer: any agent
(Secretary, Follow-up, future roles) uses the same queue.
"""

import json
from datetime import datetime, timedelta

from app import db
from app.services import booking

CONFIRMATION_LEAD_HOURS = 24


def create_task(
    from_agent: str,
    to_agent: str,
    task_type: str,
    payload: dict,
    due_at: str | None = None,
    db_path: str | None = None,
    business_id: int = 1,
) -> dict:
    with db.connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO agent_tasks"
            " (business_id, from_agent, to_agent, task_type, payload, due_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (business_id, from_agent, to_agent, task_type, json.dumps(payload), due_at),
        )
        conn.commit()
        return get_task(cur.lastrowid, db_path)


def get_task(task_id: int, db_path: str | None = None) -> dict:
    with db.connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM agent_tasks WHERE id = ?", (task_id,)
        ).fetchone()
    if not row:
        raise ValueError(f"No task with id {task_id}.")
    task = dict(row)
    task["payload"] = json.loads(task["payload"])
    return task


def list_tasks(db_path: str | None = None) -> list[dict]:
    with db.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM agent_tasks ORDER BY created_at"
        ).fetchall()
    tasks = []
    for row in rows:
        task = dict(row)
        task["payload"] = json.loads(task["payload"])
        tasks.append(task)
    return tasks


def due_tasks(
    to_agent: str, include_future: bool = False, db_path: str | None = None
) -> list[dict]:
    """Pending tasks for an agent whose due time has arrived (or all pending)."""
    now = datetime.now().isoformat(timespec="seconds")
    pending = [
        t
        for t in list_tasks(db_path)
        if t["status"] == "pending" and t["to_agent"] == to_agent
    ]
    if include_future:
        return pending
    return [t for t in pending if t["due_at"] is None or t["due_at"] <= now]


def complete_task(task_id: int, result: str, db_path: str | None = None) -> dict:
    return _set_status(task_id, "done", result, db_path)


def fail_task(task_id: int, result: str, db_path: str | None = None) -> dict:
    return _set_status(task_id, "failed", result, db_path)


def _set_status(task_id: int, status: str, result: str, db_path: str | None) -> dict:
    get_task(task_id, db_path)  # raises if missing
    with db.connect(db_path) as conn:
        conn.execute(
            "UPDATE agent_tasks SET status = ?, result = ? WHERE id = ?",
            (status, result, task_id),
        )
        conn.commit()
    return get_task(task_id, db_path)


def schedule_confirmation(
    appointment_id: int, db_path: str | None = None, business_id: int = 1
) -> dict:
    """Secretary → Follow-up handoff: confirmation reminder for an appointment.

    Due 24h before the appointment; immediately if that moment already passed.
    """
    appt = booking.get_appointment(appointment_id, db_path, business_id)
    if appt["status"] != "booked":
        raise booking.BookingError(
            f"Appointment {appointment_id} is not booked; nothing to confirm."
        )
    starts = datetime.strptime(f"{appt['date']} {appt['time']}", "%Y-%m-%d %H:%M")
    due = starts - timedelta(hours=CONFIRMATION_LEAD_HOURS)
    due = max(due, datetime.now())
    return create_task(
        from_agent="secretary",
        to_agent="followup",
        task_type="appointment_confirmation",
        payload={"appointment_id": appointment_id},
        due_at=due.isoformat(timespec="seconds"),
        db_path=db_path,
        business_id=business_id,
    )
