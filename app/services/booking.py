"""Appointment booking: availability, book, cancel, reschedule.

Single-provider calendar on a 30-minute slot grid. Plain Python service layer
(no agent dependencies) so future agents can reuse it.
"""

from datetime import date as date_cls
from datetime import datetime, timedelta

from app import db
from app.services import knowledge

SLOT_MINUTES = 30


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


def _booked_intervals(conn, date: str) -> list[tuple[datetime, datetime]]:
    rows = conn.execute(
        "SELECT time, duration_minutes FROM appointments"
        " WHERE date = ? AND status = 'booked'",
        (date,),
    ).fetchall()
    intervals = []
    for row in rows:
        start = _parse_time(row["time"])
        intervals.append((start, start + timedelta(minutes=row["duration_minutes"])))
    return intervals


def check_availability(date: str, service_id: str, db_path: str | None = None) -> list[str]:
    """Open start times (HH:MM) for a service on a date."""
    service = knowledge.get_service(service_id)
    if not service:
        raise BookingError(f"Unknown service '{service_id}'.")
    day = _parse_date(date)
    hours = knowledge.hours_for_day(day.strftime("%A"))
    if not hours:
        return []

    open_t, close_t = _parse_time(hours[0]), _parse_time(hours[1])
    duration = timedelta(minutes=service["duration_minutes"])

    with db.connect(db_path) as conn:
        booked = _booked_intervals(conn, date)

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
) -> dict:
    service = knowledge.get_service(service_id)
    if not service:
        raise BookingError(f"Unknown service '{service_id}'.")
    if not customer_name.strip() or not customer_phone.strip():
        raise BookingError("Customer name and phone are required.")
    if time not in check_availability(date, service_id, db_path):
        raise BookingError(
            f"{time} on {date} is not available for {service['name']}."
        )

    with db.connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO appointments"
            " (service_id, date, time, duration_minutes, customer_name, customer_phone)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                service_id,
                date,
                time,
                service["duration_minutes"],
                customer_name.strip(),
                customer_phone.strip(),
            ),
        )
        conn.commit()
        return get_appointment(cur.lastrowid, db_path)


def get_appointment(appointment_id: int, db_path: str | None = None) -> dict:
    with db.connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM appointments WHERE id = ?", (appointment_id,)
        ).fetchone()
    if not row:
        raise BookingError(f"No appointment with id {appointment_id}.")
    return dict(row)


def find_appointments(customer_phone: str, db_path: str | None = None) -> list[dict]:
    with db.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM appointments"
            " WHERE customer_phone = ? AND status = 'booked'"
            " ORDER BY date, time",
            (customer_phone.strip(),),
        ).fetchall()
    return [dict(r) for r in rows]


def cancel_appointment(appointment_id: int, db_path: str | None = None) -> dict:
    appt = get_appointment(appointment_id, db_path)
    if appt["status"] != "booked":
        raise BookingError(f"Appointment {appointment_id} is already cancelled.")
    with db.connect(db_path) as conn:
        conn.execute(
            "UPDATE appointments SET status = 'cancelled' WHERE id = ?",
            (appointment_id,),
        )
        conn.commit()
    return get_appointment(appointment_id, db_path)


def reschedule_appointment(
    appointment_id: int, new_date: str, new_time: str, db_path: str | None = None
) -> dict:
    appt = get_appointment(appointment_id, db_path)
    if appt["status"] != "booked":
        raise BookingError(f"Appointment {appointment_id} is cancelled; book a new one.")
    new_appt = book_appointment(
        appt["service_id"],
        new_date,
        new_time,
        appt["customer_name"],
        appt["customer_phone"],
        db_path,
    )
    cancel_appointment(appointment_id, db_path)
    return new_appt
