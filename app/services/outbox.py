"""Outbound customer messages.

POC stand-in for the M3 SMS/WhatsApp channel: messages land here instead of
being delivered, and are reviewable via the API.
"""

from app import db


def record(
    to_phone: str,
    body: str,
    customer_name: str | None = None,
    appointment_id: int | None = None,
    channel: str = "sms-outbox",
    db_path: str | None = None,
    business_id: int = 1,
) -> dict:
    with db.connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO outbox"
            " (business_id, to_phone, customer_name, body, channel, appointment_id)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (business_id, to_phone, customer_name, body, channel, appointment_id),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM outbox WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
    return dict(row)


def list_messages(db_path: str | None = None) -> list[dict]:
    with db.connect(db_path) as conn:
        rows = conn.execute("SELECT * FROM outbox ORDER BY created_at").fetchall()
    return [dict(r) for r in rows]
