"""Tests for the empty screenplay flow: create → empty → commit first scene → scenes appear."""


import pytest
from fastapi.testclient import TestClient

from greenlight.api.app import app


@pytest.fixture
def client():
    return TestClient(app)


class TestEmptyScreenplayFlow:
    def test_create_then_commit_scene(self, client):
        """Create blank screenplay, then commit a scene to it, verify scenes appear."""
        # Create blank screenplay
        create_res = client.post(
            "/api/scripts/create",
            json={"title": "Flow Test", "author": "Tester", "genre": ""},
        )
        assert create_res.status_code == 200
        data = create_res.json()
        script_id = data["id"]
        version_id = data["loaded"]["version_id"]
        branch_id = data["loaded"]["branch_id"]

        # Verify empty scenes
        detail = client.get(f"/api/versions/{version_id}").json()
        assert len(detail["scenes"]) == 0

        # Commit first scene
        scene_text = """INT. OFFICE - DAY

A desk covered in papers. ANNA enters.

ANNA
Where is everyone?

The room is silent."""
        commit = client.post(
            f"/api/scripts/{script_id}/versions",
            json={
                "branch_id": branch_id,
                "base_version_id": version_id,
                "message": "Add first scene",
                "author": "Tester",
                "scene": {"number": 1, "text": scene_text},
            },
        ).json()
        assert commit.get("unchanged") is not True
        new_vid = commit["version_id"]

        # Verify scene now exists
        detail2 = client.get(f"/api/versions/{new_vid}").json()
        assert len(detail2["scenes"]) == 1
        assert "INT. OFFICE" in detail2["scenes"][0]["text"]
        assert "ANNA" in detail2["scenes"][0]["text"]

    def test_create_and_load_idempotent(self, client):
        """Creating a screenplay and loading it should be idempotent (re-activates)."""
        create_res = client.post(
            "/api/scripts/create",
            json={"title": "Idempotent", "author": "X", "genre": ""},
        )
        script_id = create_res.json()["id"]

        # Load again — re-activates existing script, doesn't reload content
        load_res = client.post(
            f"/api/scripts/{script_id}/load",
            json={"raw_text": "Title: Loaded\n\n===\n\nINT. ROOM - DAY\n\nHello."},
        )
        assert load_res.status_code == 200
        data = load_res.json()
        assert data["loaded"] is True
        assert data["already_loaded"] is True
        assert data["scene_count"] == 0  # blank screenplay, skeleton has no scenes

    def test_create_skeleton_fountain_valid(self, client):
        """Created screenplay's skeleton should be valid Fountain."""
        from greenlight.tools.fountain_document import parse_document

        create_res = client.post(
            "/api/scripts/create",
            json={"title": "Valid Fountain", "author": "A", "genre": ""},
        )
        script_id = create_res.json()["id"]

        text = client.get(f"/api/scripts/{script_id}/text").text
        elements = parse_document(text)
        title_elements = [e for e in elements if e.type == "title_page"]
        assert len(title_elements) >= 1
