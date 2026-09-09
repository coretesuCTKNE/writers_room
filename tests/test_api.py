import pytest
from fastapi.testclient import TestClient

from greenlight.api.app import app


@pytest.fixture
def client():
    return TestClient(app)


class TestHealth:
    def test_health_endpoint(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data


class TestScripts:
    def test_list_scripts(self, client):
        response = client.get("/api/scripts")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


class TestCoverage:
    def test_coverage_requires_script(self, client):
        response = client.post(
            "/api/scripts/nonexistent/coverage",
            json={"script_text": "Hello world."},
        )
        assert response.status_code == 404


class TestHistory:
    def test_list_edits(self, client):
        response = client.get("/api/history/edits")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
