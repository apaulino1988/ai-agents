"""Google Calendar provider (calendar-sync spec). RED-phase stub."""

import httpx  # noqa: F401
import jwt  # noqa: F401

_token_cache: dict = {}


def enabled() -> bool:
    raise NotImplementedError


def _access_token() -> str:
    raise NotImplementedError


def create_event(appointment: dict) -> str | None:
    raise NotImplementedError


def delete_event(event_id: str) -> None:
    raise NotImplementedError


def busy_intervals(date: str) -> list:
    raise NotImplementedError
