import time
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SERVICESIGNAL_DB", str(tmp_path / "test.sqlite"))
    monkeypatch.setenv("AGENT_PROVIDER", "fixture")
    monkeypatch.setenv("PUBLIC_ORIGIN", "http://testserver")
    monkeypatch.setattr(time, "time", lambda: datetime(2026, 9, 13, 12, tzinfo=UTC).timestamp())
    with TestClient(app, headers={"X-ServiceSignal": "1"}) as c:
        assert c.post("/api/session", json={}).status_code == 200
        yield c
