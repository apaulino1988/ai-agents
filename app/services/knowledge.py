"""Business knowledge: the per-tenant profile the agents answer from.

Profiles live in the `businesses` table (multi-tenant AC-006). The default
tenant (id=1) is seeded from `data/business.json` on first connect — that
file is a seed source only, never read at answer time. Plain Python,
independent of the agent, so every agent role shares it.
"""

import json
import os
from pathlib import Path

from app import db

DEFAULT_BUSINESS_FILE = Path(__file__).resolve().parents[2] / "data" / "business.json"


def business_file() -> Path:
    """Seed source for the default tenant (see db._seed_default_business)."""
    return Path(os.environ.get("SECRETARY_BUSINESS_FILE", DEFAULT_BUSINESS_FILE))


def get_profile(business_id: int = 1, db_path: str | None = None) -> dict:
    with db.connect(db_path) as conn:
        row = conn.execute(
            "SELECT profile FROM businesses WHERE id = ?", (business_id,)
        ).fetchone()
    if not row:
        raise LookupError(f"No business with id {business_id}.")
    return json.loads(row["profile"])


def get_service(
    service_id: str, business_id: int = 1, db_path: str | None = None
) -> dict | None:
    for service in get_profile(business_id, db_path)["services"]:
        if service["id"] == service_id:
            return service
    return None


def hours_for_day(
    day_name: str, business_id: int = 1, db_path: str | None = None
) -> tuple[str, str] | None:
    """Opening hours for a weekday name ('monday'...), or None if closed."""
    hours = get_profile(business_id, db_path)["hours"].get(day_name.lower())
    return (hours[0], hours[1]) if hours else None


def profile_as_prompt_text(business_id: int = 1, db_path: str | None = None) -> str:
    """Render the business profile for the agent's system prompt."""
    p = get_profile(business_id, db_path)
    lines = [
        f"Business: {p['name']} — {p['tagline']}",
        p["description"],
        f"Location: {p['location']}",
        f"Phone: {p['phone']} · Email: {p['email']}",
        "",
        "Opening hours:",
    ]
    for day, hours in p["hours"].items():
        lines.append(
            f"- {day.capitalize()}: "
            + (f"{hours[0]}–{hours[1]}" if hours else "Closed")
        )
    lines.append("")
    lines.append("Services (id · name · duration · price):")
    for s in p["services"]:
        price = "Free" if s["price_usd"] == 0 else f"${s['price_usd']}"
        lines.append(
            f"- {s['id']} · {s['name']} · {s['duration_minutes']} min · {price}"
            f" — {s['description']}"
        )
    lines.append("")
    lines.append("Policies:")
    for policy in p["policies"]:
        lines.append(f"- {policy}")
    return "\n".join(lines)
