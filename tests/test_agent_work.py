"""Chunk 4: agent-work routes — bible facts, analytics reads, run history.

Uses real ClickHouse + FastAPI TestClient (no mocking), matching repo convention.
Tests the deterministic endpoints; no live LLM required.
"""

import pytest
from fastapi.testclient import TestClient

from greenlight.api.app import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def script(client):
    res = client.post(
        "/api/scripts/create",
        json={"title": "Agent Work Test", "author": "Tester", "genre": "Drama"},
    )
    assert res.status_code == 200
    return res.json()["id"]


class TestBibleFacts:
    def test_list_empty(self, client, script):
        res = client.get(f"/api/scripts/{script}/bible-facts")
        assert res.status_code == 200
        assert res.json() == []

    def test_add_and_list(self, client, script):
        res = client.post(
            f"/api/scripts/{script}/bible-facts",
            json={
                "character_id": "DET",
                "category": "personality",
                "claim": "stoic",
                "source_page": 3,
            },
        )
        assert res.status_code == 200
        fact = res.json()
        assert "fact_id" in fact

        listed = client.get(f"/api/scripts/{script}/bible-facts").json()
        assert len(listed) == 1
        assert listed[0]["claim"] == "stoic"

        filtered = client.get(f"/api/scripts/{script}/bible-facts?character_id=DET").json()
        assert len(filtered) == 1
        assert client.get(f"/api/scripts/{script}/bible-facts?character_id=OTHER").json() == []

    def test_add_rejects_bad_category(self, client, script):
        res = client.post(
            f"/api/scripts/{script}/bible-facts",
            json={"character_id": "DET", "category": "nope", "claim": "x"},
        )
        assert res.status_code == 422

    def test_delete(self, client, script):
        fact = client.post(
            f"/api/scripts/{script}/bible-facts",
            json={"character_id": "DET", "category": "timeline", "claim": "arrives day 2"},
        ).json()
        res = client.delete(f"/api/scripts/{script}/bible-facts/{fact['fact_id']}")
        assert res.status_code == 200
        assert res.json()["deleted_fact_id"] == fact["fact_id"]


class TestAnalytics:
    def test_stats(self, client, script):
        res = client.get(f"/api/scripts/{script}/analytics/stats")
        assert res.status_code == 200
        st = res.json()
        assert st["script_id"] == script
        assert "scene_count" in st and "coverage_breakdown" in st
        assert st["bible_fact_count"] >= 0

    def test_coverage_empty(self, client, script):
        res = client.get(f"/api/scripts/{script}/analytics/coverage")
        assert res.status_code == 200
        assert res.json() == []


class TestRunHistory:
    def test_empty_history(self, client, script):
        res = client.get(f"/api/scripts/{script}/agents/runs")
        assert res.status_code == 200
        assert res.json() == []


class TestScriptGuard:
    def test_unknown_script_404(self, client):
        for path in (
            "/api/scripts/nope/agents/runs",
            "/api/scripts/nope/bible-facts",
            "/api/scripts/nope/analytics/stats",
        ):
            assert client.get(path).status_code == 404
        assert (
            client.post(
                "/api/scripts/nope/showrunner", json={"prompt": "check continuity"}
            ).status_code
            == 404
        )


class TestShowrunnerRoute:
    """Structural-only: never invokes the live LLM (would need Vertex creds + ~30s).
    Exercises the short-circuit guards that return before any model call."""

    def test_unknown_script_404(self, client):
        res = client.post("/api/scripts/nope/showrunner", json={"prompt": "check continuity"})
        assert res.status_code == 404

    def test_empty_prompt_422(self, client, script):
        res = client.post(f"/api/scripts/{script}/showrunner", json={"prompt": "   "})
        assert res.status_code == 422
