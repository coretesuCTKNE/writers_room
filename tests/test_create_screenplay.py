"""Tests for blank-screenplay creation (Phase A.5)."""

import pytest
from fastapi.testclient import TestClient

from greenlight.api.app import app


@pytest.fixture
def client():
    return TestClient(app)


class TestCreateScreenplay:
    def test_create_screenplay(self, client):
        res = client.post(
            "/api/scripts/create",
            json={"title": "My New Script", "author": "Jane", "genre": "Drama"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["title"] == "My New Script"
        assert data["id"]
        assert data["char_count"] > 0
        loaded = data["loaded"]
        assert loaded["loaded"] is True
        assert loaded["branch_id"]
        assert loaded["version_id"]
        assert loaded["scene_count"] == 0

    def test_create_screenplay_rejects_empty_title(self, client):
        res = client.post("/api/scripts/create", json={"title": "  "})
        assert res.status_code == 422

    def test_create_screenplay_appears_in_list(self, client):
        res = client.post(
            "/api/scripts/create",
            json={"title": "Listed Script", "author": "A", "genre": ""},
        )
        script_id = res.json()["id"]

        scripts = client.get("/api/scripts").json()
        assert any(s["id"] == script_id for s in scripts)

    def test_create_screenplay_skeleton_format(self, client):
        res = client.post(
            "/api/scripts/create",
            json={"title": "Skeleton Test", "author": "Writer", "genre": "Thriller"},
        )
        script_id = res.json()["id"]

        text = client.get(f"/api/scripts/{script_id}/text").text
        assert "Title: Skeleton Test" in text
        assert "Author: Writer" in text
        assert "Genre: Thriller" in text

    def test_create_screenplay_no_genre(self, client):
        res = client.post(
            "/api/scripts/create",
            json={"title": "No Genre", "author": "X"},
        )
        assert res.status_code == 200
        text = client.get(f"/api/scripts/{res.json()['id']}/text").text
        assert "Genre:" not in text
