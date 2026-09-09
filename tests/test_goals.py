"""Tests for writing goals REST routes (Story Ops, dev_plans/06)."""

import uuid

import pytest
from fastapi.testclient import TestClient

from greenlight.api.app import app
from greenlight.db.client import get_ch_client, insert


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def script_id():
    sid = f"test_{uuid.uuid4().hex[:12]}"
    insert(
        "scripts",
        [
            {
                "id": sid,
                "title": "Goals Test",
                "author": "t",
                "draft": 1,
                "genre": "",
                "owner": "local",
            }
        ],
    )
    yield sid
    get_ch_client().command(
        "DELETE FROM greenlight.scripts WHERE id = %(sid)s",
        parameters={"sid": sid},
    )


class TestGoalLifecycle:
    def test_unknown_script_404(self, client):
        assert client.get("/api/scripts/nonexistent/goals").status_code == 404
        assert (
            client.post(
                "/api/scripts/nonexistent/goals",
                json={"metric": "words", "target": 100},
            ).status_code
            == 404
        )

    def test_empty_then_create_list_delete(self, client, script_id):
        assert client.get(f"/api/scripts/{script_id}/goals").json() == []

        res = client.post(
            f"/api/scripts/{script_id}/goals",
            json={"metric": "words", "target": 5000, "deadline": "2026-09-09"},
        )
        assert res.status_code == 200
        goal_id = res.json()["goal_id"]

        goals = client.get(f"/api/scripts/{script_id}/goals").json()
        assert len(goals) == 1
        goal = goals[0]
        assert goal["metric"] == "words"
        assert goal["target"] == 5000
        assert goal["deadline"] == "2026-09-09"
        # No versions for this script -> zero progress
        assert goal["current"] == 0
        assert goal["pct"] == 0.0
        assert goal["remaining"] == 5000

        assert client.delete(f"/api/scripts/{script_id}/goals/{goal_id}").status_code == 200
        assert client.get(f"/api/scripts/{script_id}/goals").json() == []

    def test_invalid_metric_422(self, client, script_id):
        res = client.post(
            f"/api/scripts/{script_id}/goals",
            json={"metric": "caffeine", "target": 10},
        )
        assert res.status_code == 422

    def test_delete_unknown_goal_404(self, client, script_id):
        assert client.delete(f"/api/scripts/{script_id}/goals/nope").status_code == 404

    def test_progress_against_version_stats(self, client, script_id):
        """Goal progress reads the latest version's word_count (backfill schema)."""
        from greenlight.db.client import insert as ch_insert

        branch_id = str(uuid.uuid4())
        version_id = str(uuid.uuid4())
        ch_insert(
            "script_versions",
            [
                {
                    "version_id": version_id,
                    "script_id": script_id,
                    "branch_id": branch_id,
                    "raw_fountain": "INT. A - NIGHT\n\nAction line here.\n",
                    "content_hash": "deadbeef",
                    "word_count": 2500,
                    "page_count": 1,
                }
            ],
        )
        ch_insert(
            "scene_stats",
            [
                {
                    "script_id": script_id,
                    "version_id": version_id,
                    "scene_number": 1,
                    "heading": "INT. A - NIGHT",
                    "setting": "INT",
                    "time_of_day": "NIGHT",
                    "dialogue_lines": 0,
                    "action_lines": 1,
                    "dialogue_words": 0,
                    "action_words": 3,
                    "characters": [],
                }
            ],
        )

        client.post(f"/api/scripts/{script_id}/goals", json={"metric": "words", "target": 5000})
        client.post(f"/api/scripts/{script_id}/goals", json={"metric": "scenes", "target": 2})
        goals = {g["metric"]: g for g in client.get(f"/api/scripts/{script_id}/goals").json()}
        assert goals["words"]["current"] == 2500
        assert goals["words"]["pct"] == 50.0
        assert goals["scenes"]["current"] == 1
        assert goals["scenes"]["pct"] == 50.0
