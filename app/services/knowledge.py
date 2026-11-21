"""Business knowledge: the configured profile the Secretary answers from.

Plain Python, independent of the agent, so future agents (M2 Follow-up) can
reuse it.
"""

import json
import os
from functools import lru_cache
from pathlib import Path

DEFAULT_BUSINESS_FILE = Path(__file__).resolve().parents[2] / "data" / "business.json"


def business_file() -> Path:
    return Path(os.environ.get("SECRETARY_BUSINESS_FILE", DEFAULT_BUSINESS_FILE))


@lru_cache(maxsize=1)
def _load(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def get_profile() -> dict:
    return _load(str(business_file()))


def get_service(service_id: str) -> dict | None:
    for service in get_profile()["services"]:
        if service["id"] == service_id:
            return service
    return None


def hours_for_day(day_name: str) -> tuple[str, str] | None:
    """Opening hours for a weekday name ('monday'...), or None if closed."""
    hours = get_profile()["hours"].get(day_name.lower())
    return (hours[0], hours[1]) if hours else None


def profile_as_prompt_text() -> str:
    """Render the business profile for the agent's system prompt."""
    p = get_profile()
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
