"""Tenant (business) registry — multi-tenant spec.

Plain service layer over the `businesses` table: lookups used for request
routing (slug, receiving phone number) and the admin CRUD used by onboarding.
Profiles live here as JSON (AC-006): no module reads data/business.json at
runtime — the file is only the seed source for the default tenant.
"""

import json
import sqlite3

from app import db

DEFAULT_BUSINESS_ID = 1

_MUTABLE_FIELDS = (
    "name",
    "profile",
    "timezone",
    "twilio_number",
    "whatsapp_sender",
    "calendar_id",
    "status",
)


class TenantError(Exception):
    """Invalid tenant operation; message safe to surface to the admin API."""


def _to_business(row: sqlite3.Row | None) -> dict | None:
    if not row:
        return None
    business = dict(row)
    business["profile"] = json.loads(business["profile"])
    return business


def _normalize_number(number: str) -> str:
    return number.removeprefix("whatsapp:").strip()


def get_business(business_id: int, db_path: str | None = None) -> dict | None:
    with db.connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM businesses WHERE id = ?", (business_id,)
        ).fetchone()
    return _to_business(row)


def get_default(db_path: str | None = None) -> dict:
    business = get_business(DEFAULT_BUSINESS_ID, db_path)
    if not business:
        raise TenantError("Default business is missing.")
    return business


def get_by_slug(slug: str, db_path: str | None = None) -> dict | None:
    with db.connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM businesses WHERE slug = ?", (slug.strip(),)
        ).fetchone()
    return _to_business(row)


def get_by_number(number: str, db_path: str | None = None) -> dict | None:
    """The business owning a receiving phone number (SMS or WhatsApp)."""
    bare = _normalize_number(number)
    with db.connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM businesses WHERE twilio_number = ? OR whatsapp_sender = ?",
            (bare, bare),
        ).fetchone()
    return _to_business(row)


def list_businesses(db_path: str | None = None) -> list[dict]:
    with db.connect(db_path) as conn:
        rows = conn.execute("SELECT * FROM businesses ORDER BY id").fetchall()
    return [_to_business(r) for r in rows]


def _check_numbers_free(
    conn, twilio_number: str | None, whatsapp_sender: str | None, exclude_id: int | None
) -> None:
    for number in (twilio_number, whatsapp_sender):
        if not number:
            continue
        row = conn.execute(
            "SELECT id FROM businesses"
            " WHERE (twilio_number = ? OR whatsapp_sender = ?)"
            " AND (? IS NULL OR id != ?)",
            (number, number, exclude_id, exclude_id),
        ).fetchone()
        if row:
            raise TenantError(f"Number {number} already belongs to another business.")


def create_business(
    slug: str,
    name: str,
    profile: dict,
    timezone: str = "UTC",
    twilio_number: str | None = None,
    whatsapp_sender: str | None = None,
    calendar_id: str | None = None,
    db_path: str | None = None,
) -> dict:
    twilio_number = _normalize_number(twilio_number) if twilio_number else None
    whatsapp_sender = _normalize_number(whatsapp_sender) if whatsapp_sender else None
    with db.connect(db_path) as conn:
        _check_numbers_free(conn, twilio_number, whatsapp_sender, exclude_id=None)
        try:
            cur = conn.execute(
                "INSERT INTO businesses"
                " (slug, name, profile, timezone, twilio_number, whatsapp_sender, calendar_id)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    slug.strip(),
                    name.strip(),
                    json.dumps(profile),
                    timezone,
                    twilio_number,
                    whatsapp_sender,
                    calendar_id,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise TenantError(f"Slug '{slug}' is already taken.") from exc
        conn.commit()
        business_id = cur.lastrowid
    return get_business(business_id, db_path)


def update_business(slug: str, db_path: str | None = None, **fields) -> dict:
    business = get_by_slug(slug, db_path)
    if not business:
        raise TenantError(f"No business with slug '{slug}'.")
    unknown = set(fields) - set(_MUTABLE_FIELDS)
    if unknown:
        raise TenantError(f"Unknown fields: {', '.join(sorted(unknown))}.")
    if not fields:
        return business

    for key in ("twilio_number", "whatsapp_sender"):
        if fields.get(key):
            fields[key] = _normalize_number(fields[key])
    if "profile" in fields:
        fields["profile"] = json.dumps(fields["profile"])

    with db.connect(db_path) as conn:
        _check_numbers_free(
            conn,
            fields.get("twilio_number"),
            fields.get("whatsapp_sender"),
            exclude_id=business["id"],
        )
        assignments = ", ".join(f"{key} = ?" for key in fields)
        conn.execute(
            # column names come from _MUTABLE_FIELDS, never from user input
            f"UPDATE businesses SET {assignments} WHERE id = ?",
            (*fields.values(), business["id"]),
        )
        conn.commit()
    return get_business(business["id"], db_path)
