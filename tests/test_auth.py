"""Tests for the Firebase auth middleware (flag off = passthrough, flag on = 401)."""

import pytest
from fastapi.testclient import TestClient

from greenlight.api.app import app


@pytest.fixture
def client():
    return TestClient(app)


class TestAuthOff:
    """Default (FIREBASE_PROJECT_ID empty): everything passes, principal local."""

    def test_scripts_without_token(self, client):
        assert client.get("/api/scripts").status_code == 200

    def test_health_without_token(self, client):
        assert client.get("/api/health").status_code in (200, 503)

    def test_ws_without_token(self, client):
        with client.websocket_connect("/api/ws/agents") as ws:
            assert ws is not None


class TestAuthOn:
    """FIREBASE_PROJECT_ID set: bearer token required except /api/health."""

    @pytest.fixture(autouse=True)
    def _auth_on(self, monkeypatch):
        from greenlight.config import settings

        monkeypatch.setattr(settings, "firebase_project_id", "greenlight15488")
        yield

    def test_scripts_without_token_401(self, client):
        res = client.get("/api/scripts")
        assert res.status_code == 401
        assert res.json()["detail"] == "Authentication required"

    def test_scripts_bad_token_401(self, client):
        res = client.get("/api/scripts", headers={"Authorization": "Bearer not-a-token"})
        assert res.status_code == 401

    def test_health_exempt(self, client):
        assert client.get("/api/health").status_code in (200, 503)

    def test_non_api_paths_exempt(self, client):
        # SPA fallback path (no dist required, route still answers)
        assert client.get("/").status_code in (200, 404)

    def test_ws_without_token_rejected(self, client):
        with pytest.raises(Exception):
            with client.websocket_connect("/api/ws/agents"):
                pass
