"""Appointment booking: availability, book, cancel, reschedule.

Single-provider calendar on a 30-minute slot grid. Plain Python service layer
(no agent dependencies) so future agents can reuse it. Every operation is
tenant-scoped via `business_id` (default 1 = the migrated original business).
"""

from contextlib import contextmanager
from datetime import date as date_cls
from datetime import datetime, timedelta

from app import db
from app.services import calendar, knowledge
from app.tenant import current_business_id

SLOT_MINUTES = 30


@contextmanager
def _tenant(business_id: int):
    """Calendar calls read the tenant from context (keeps their public
    single-tenant call shape); booking bridges its explicit business_id in."""
    token = current_business_id.set(business_id)
    try:
        yield
    finally:
        current_business_id.reset(token)


class BookingError(Exception):
    """Raised for invalid booking operations; message is safe to show the agent."""


def _parse_date(value: str) -> date_cls:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise BookingError(f"Invalid date '{value}', expected YYYY-MM-DD.") from exc


def _parse_time(value: str) -> datetime:
    try:
        return datetime.strptime(value, "%H:%M")
    except ValueError as exc:
        raise BookingError(f"Invalid time '{value}', expected HH:MM.") from exc


def _booked_intervals(conn, date: str, business_id: int) -> list[tuple[datetime, datetime]]:
    rows = conn.execute(
        "SELECT time, duration_minutes FROM appointments"
        " WHERE date = ? AND status = 'booked' AND business_id = ?",
        (date, business_id),
    ).fetchall()
    intervals = []
    for row in rows:
        start = _parse_time(row["time"])
        intervals.append((start, start + timedelta(minutes=row["duration_minutes"])))
    return intervals


def check_availability(
    date: str,
    service_id: str,
    db_path: str | None = None,
    business_id: int = 1,
) -> list[str]:
    """Open start times (HH:MM) for a service on a date."""
    service = knowledge.get_service(service_id, business_id, db_path)
    if not service:
        raise BookingError(f"Unknown service '{service_id}'.")
    day = _parse_date(date)
    hours = knowledge.hours_for_day(day.strftime("%A"), business_id, db_path)
    if not hours:
        return []

    open_t, close_t = _parse_time(hours[0]), _parse_time(hours[1])
    duration = timedelta(minutes=service["duration_minutes"])

    with db.connect(db_path) as conn:
        booked = _booked_intervals(conn, date, business_id)
    # The owner's real calendar blocks slots too (fails open to []).
    with _tenant(business_id):
        booked += calendar.busy_intervals(date)

    slots = []
    cursor = open_t
    while cursor + duration <= close_t:
        end = cursor + duration
        if not any(start < end and cursor < stop for start, stop in booked):
            slots.append(cursor.strftime("%H:%M"))
        cursor += timedelta(minutes=SLOT_MINUTES)
    return slots


def book_appointment(
    service_id: str,
    date: str,
    time: str,
    customer_name: str,
    customer_phone: str,
    db_path: str | None = None,
    business_id: int = 1,
) -> dict:
    service = knowledge.get_service(service_id, business_id, db_path)
    if not service:
        raise BookingError(f"Unknown service '{service_id}'.")
    if not customer_name.strip() or not customer_phone.strip():
        raise BookingError("Customer name and phone are required.")
    if time not in check_availability(date, service_id, db_path, business_id):
        raise BookingError(
            f"{time} on {date} is not available for {service['name']}."
        )

    with db.connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO appointments"
            " (business_id, service_id, date, time, duration_minutes,"
            "  customer_name, customer_phone)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                business_id,
                service_id,
                date,
                time,
                service["duration_minutes"],
                customer_name.strip(),
                customer_phone.strip(),
            ),
        )
        conn.commit()
        appointment_id = cur.lastrowid

    appt = get_appointment(appointment_id, db_path, business_id)
    with _tenant(business_id):
        event_id = calendar.create_event(appt)  # None when disabled/failed
    if event_id:
        with db.connect(db_path) as conn:
            conn.execute(
                "UPDATE appointments SET calendar_event_id = ? WHERE id = ?",
                (event_id, appointment_id),
            )
            conn.commit()
        appt = get_appointment(appointment_id, db_path, business_id)
    return appt


def get_appointment(
    appointment_id: int, db_path: str | None = None, business_id: int = 1
) -> dict:
    with db.connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM appointments WHERE id = ? AND business_id = ?",
            (appointment_id, business_id),
        ).fetchone()
    if not row:
        raise BookingError(f"No appointment with id {appointment_id}.")
    return dict(row)


def find_appointments(
    customer_phone: str, db_path: str | None = None, business_id: int = 1
) -> list[dict]:
    with db.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM appointments"
            " WHERE customer_phone = ? AND status = 'booked' AND business_id = ?"
            " ORDER BY date, time",
            (customer_phone.strip(), business_id),
        ).fetchall()
    return [dict(r) for r in rows]


def cancel_appointment(
    appointment_id: int, db_path: str | None = None, business_id: int = 1
) -> dict:
    appt = get_appointment(appointment_id, db_path, business_id)
    if appt["status"] != "booked":
        raise BookingError(f"Appointment {appointment_id} is already cancelled.")
    with db.connect(db_path) as conn:
        conn.execute(
            "UPDATE appointments SET status = 'cancelled' WHERE id = ?",
            (appointment_id,),
        )
        conn.commit()
    if appt.get("calendar_event_id"):
        with _tenant(business_id):
            calendar.delete_event(appt["calendar_event_id"])
    return get_appointment(appointment_id, db_path, business_id)


def confirm_appointment(
    appointment_id: int, db_path: str | None = None, business_id: int = 1
) -> dict:
    appt = get_appointment(appointment_id, db_path, business_id)
    if appt["status"] != "booked":
        raise BookingError(f"Appointment {appointment_id} is cancelled; cannot confirm.")
    with db.connect(db_path) as conn:
        conn.execute(
            "UPDATE appointments SET confirmed_at = datetime('now') WHERE id = ?",
            (appointment_id,),
        )
        conn.commit()
    return get_appointment(appointment_id, db_path, business_id)


def reschedule_appointment(
    appointment_id: int,
    new_date: str,
    new_time: str,
    db_path: str | None = None,
    business_id: int = 1,
) -> dict:
    appt = get_appointment(appointment_id, db_path, business_id)
    if appt["status"] != "booked":
        raise BookingError(f"Appointment {appointment_id} is cancelled; book a new one.")
    new_appt = book_appointment(
        appt["service_id"],
        new_date,
        new_time,
        appt["customer_name"],
        appt["customer_phone"],
        db_path,
        business_id,
    )
    cancel_appointment(appointment_id, db_path, business_id)
    return new_appt
