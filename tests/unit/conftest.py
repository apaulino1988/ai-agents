import pytest


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Point the app at a throwaway SQLite database."""
    path = tmp_path / "test.db"
    monkeypatch.setenv("SECRETARY_DB_PATH", str(path))
    return str(path)
