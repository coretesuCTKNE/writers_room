"""Story Ops aggregate endpoint — one-shot payload for the in-app dashboard.

Real ClickHouse + FastAPI TestClient (repo convention). No LLM calls.
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
        json={"title": "Story Ops Test", "author": "Tester", "genre": "Drama"},
    )
    assert res.status_code == 200
    return res.json()["id"]


class TestStoryOps:
    def test_empty_script_shape(self, client, script):
        res = client.get(f"/api/scripts/{script}/storyops")
        assert res.status_code == 200
        data = res.json()
        assert data["script_id"] == script
        # scripts/create scaffolds a root snapshot, so one commit exists.
        assert len(data["commit_history"]) == 1
        assert data["scene_stats"] == []
        assert data["goals"] == []
        assert data["coverage_history"] == []
        assert data["agent_runs"] == []
        assert data["summary"]["script_id"] == script
        assert "scene_count" in data["summary"]

    def test_unknown_script_404(self, client):
        assert client.get("/api/scripts/nope/storyops").status_code == 404

    def test_commit_history_after_commit(self, client, script):
        import uuid
        from datetime import datetime

        from greenlight.db.client import insert as ch_insert

        branch_id = str(uuid.uuid4())
        version_id = str(uuid.uuid4())
        ch_insert(
            "script_versions",
            [
                {
                    "version_id": version_id,
                    "script_id": script,
                    "branch_id": branch_id,
                    "raw_fountain": "INT. A - NIGHT\n\nAction line.\n",
                    "content_hash": "feedface",
                    "word_count": 1234,
                    "page_count": 1,
                    "message": "story ops commit",
                    # Future-dated so it deterministically wins the
                    # ORDER BY created_at DESC race with the root snapshot.
                    "created_at": datetime(2030, 1, 1),
                }
            ],
        )
        ch_insert(
            "scene_stats",
            [
                {
                    "script_id": script,
                    "version_id": version_id,
                    "scene_number": 1,
                    "heading": "INT. A - NIGHT",
                    "setting": "INT",
                    "time_of_day": "NIGHT",
                    "dialogue_lines": 2,
                    "action_lines": 1,
                    "dialogue_words": 10,
                    "action_words": 3,
                    "characters": ["DET"],
                }
            ],
        )

        res = client.get(f"/api/scripts/{script}/storyops")
        assert res.status_code == 200
        data = res.json()
        assert len(data["commit_history"]) == 2
        commit = next(c for c in data["commit_history"] if c["word_count"] == 1234)
        assert {"created_at", "word_count", "page_count", "message"} <= set(commit)
        assert commit["message"] == "story ops commit"
        assert len(data["scene_stats"]) == 1
        first_scene = data["scene_stats"][0]
        assert first_scene["heading"] == "INT. A - NIGHT"
        assert first_scene["characters"] == ["DET"]
        assert {
            "scene_number",
            "heading",
            "dialogue_words",
            "action_words",
            "characters",
        } <= set(first_scene)

    def test_goals_included(self, client, script):
        res = client.post(
            f"/api/scripts/{script}/goals",
            json={"metric": "words", "target": 1000},
        )
        assert res.status_code == 200
        data = client.get(f"/api/scripts/{script}/storyops").json()
        assert len(data["goals"]) == 1
        goal = data["goals"][0]
        assert goal["metric"] == "words"
        assert goal["target"] == 1000
        assert "pct" in goal and "current" in goal
