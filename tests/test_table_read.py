import pytest
from fastapi.testclient import TestClient

from greenlight.api.app import app

SCENE = """INT. HOUSE - NIGHT

JOHNNY
They're coming to get you.

BARBARA
Stop it. This isn't funny.
"""


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr("greenlight.api.routes.table_read.is_tts_available", lambda: False)
    return TestClient(app)


@pytest.fixture(autouse=True)
def _owned_test_scripts():
    """Register the fictional script ids these tests use (owner-gated routes)."""
    from greenlight.db.client import command, insert

    ids = [
        "tr_test_missing",
        "tr_test_persist",
        "tr_test_stale",
        "tr_test_voices",
        "tr_test_empty",
        "tr_test_bounds",
        "tr_test_turn_cap",
    ]
    insert(
        "scripts",
        [
            {"id": sid, "title": f"TR {sid}", "author": "t", "hash": "", "owner": "local"}
            for sid in ids
        ],
    )
    yield
    command("DELETE FROM greenlight.scripts WHERE id IN %(ids)s", {"ids": tuple(ids)})


class TestTableReadPersistence:
    def test_lookup_missing_take(self, client):
        response = client.post(
            "/api/table-read/lookup",
            json={"script_id": "tr_test_missing", "scene_number": 99, "scene_text": SCENE},
        )
        assert response.status_code == 200
        assert response.json()["found"] is False

    def test_generate_then_lookup_restores(self, client):
        body = {
            "script_id": "tr_test_persist",
            "scene_number": 7,
            "scene_text": SCENE,
            "voice_preferences": {"JOHNNY": "puck"},
            "narration": False,
        }
        gen = client.post("/api/table-read/generate", json=body)
        assert gen.status_code == 200
        result = gen.json()
        assert result["voice_preferences"] == {"JOHNNY": "puck"}

        look = client.post(
            "/api/table-read/lookup",
            json={
                "script_id": body["script_id"],
                "scene_number": body["scene_number"],
                "scene_text": SCENE,
            },
        )
        assert look.status_code == 200
        data = look.json()
        assert data["found"] is True
        assert data["stale"] is False
        assert data["result"]["reference_audio"] == result["reference_audio"]

    def test_lookup_stale_after_scene_edit(self, client):
        base = {
            "script_id": "tr_test_stale",
            "scene_number": 3,
            "scene_text": SCENE,
        }
        gen = client.post("/api/table-read/generate", json=base)
        assert gen.status_code == 200

        edited = {**base, "scene_text": SCENE + "\nJOHNNY\nOne more line.\n"}
        data = client.post("/api/table-read/lookup", json=edited).json()
        assert data["found"] is True
        assert data["stale"] is True

    def test_voice_casting_prefill_survives(self, client):
        gen = client.post(
            "/api/table-read/generate",
            json={
                "script_id": "tr_test_voices",
                "scene_number": 1,
                "scene_text": SCENE,
                "voice_preferences": {"BARBARA": "zephyr"},
            },
        )
        assert gen.status_code == 200
        prefs = client.get(
            "/api/table-read/voice-casting", params={"script_id": "tr_test_voices"}
        ).json()
        assert prefs.get("BARBARA") == "zephyr"

    def test_generate_rejects_bad_scene_number(self, client):
        response = client.post(
            "/api/table-read/generate",
            json={
                "script_id": "tr_test_bounds",
                "scene_number": 99999,
                "scene_text": SCENE,
            },
        )
        assert response.status_code == 422

    def test_generate_requires_dialogue(self, client):
        response = client.post(
            "/api/table-read/generate",
            json={"script_id": "tr_test_empty", "scene_text": "Just action. No dialogue."},
        )
        assert response.status_code == 400

    def test_generate_rejects_scene_over_turn_cap(self, client, monkeypatch):
        from greenlight.config import settings

        monkeypatch.setattr(settings, "table_read_max_turns", 3)
        long_scene = SCENE + "\n".join([f"JOHNNY\nLine number {i}." for i in range(5)])
        response = client.post(
            "/api/table-read/generate",
            json={"script_id": "tr_test_turn_cap", "scene_text": long_scene},
        )
        assert response.status_code == 400
        assert "up to 3" in response.json()["detail"]
