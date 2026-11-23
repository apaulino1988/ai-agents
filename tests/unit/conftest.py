import pytest

# Real integration credentials must never reach unit tests. Importing app.main
# anywhere in the session (e.g. webhook tests at collection time) runs
# load_dotenv(), so a developer's populated .env would otherwise enable the
# real Twilio/Google code paths suite-wide.
INTEGRATION_ENV_VARS = [
    "TWILIO_ACCOUNT_SID",
    "TWILIO_AUTH_TOKEN",
    "TWILIO_FROM_NUMBER",
    "TWILIO_WHATSAPP_FROM",
    "TWILIO_VALIDATE",
    "GOOGLE_SERVICE_ACCOUNT_FILE",
    "GOOGLE_CALENDAR_ID",
    "BUSINESS_TIMEZONE",
]


@pytest.fixture(autouse=True)
def isolate_integration_env(monkeypatch):
    """Strip real channel/calendar credentials; tests opt in via monkeypatch."""
    for var in INTEGRATION_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    """Every unit test gets a throwaway SQLite database.

    Autouse because profiles now live in the DB (multi-tenant AC-006): any
    test touching knowledge/booking would otherwise read — or migrate! — the
    developer's real secretary.db.
    """
    path = tmp_path / "test.db"
    monkeypatch.setenv("SECRETARY_DB_PATH", str(path))
    return str(path)


@pytest.fixture
def temp_db(_isolated_db):
    """Point the app at a throwaway SQLite database."""
    return _isolated_db
