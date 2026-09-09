"""Tests for generated-audio asset listing + lightweight delete."""

import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from greenlight.api.app import app
from greenlight.db.client import command, insert, query


@pytest.fixture
def client():
    return TestClient(app)


AUDIO_DIR = Path("generated_audio")


def _make_script(script_id: str, owner: str = "local") -> None:
    """Create a scripts row the asset JOIN can resolve. Auth is off in tests,
    so the request principal is 'local'."""
    insert(
        "scripts",
        [{"id": script_id, "title": "Asset test", "hash": "test", "owner": owner}],
    )


class TestDeleteAsset:
    def test_delete_removes_row_and_file(self, client):
        asset_id = str(uuid.uuid4())
        script_id = f"asset-test-{uuid.uuid4().hex[:8]}"
        filename = f"asset_test_{asset_id[:8]}.wav"
        wav = AUDIO_DIR / filename
        wav.parent.mkdir(exist_ok=True)
        wav.write_bytes(b"RIFF-dummy")
        _make_script(script_id)
        insert(
            "generated_audio_assets",
            [
                {
                    "asset_id": asset_id,
                    "script_id": script_id,
                    "scene_id": "s1",
                    "purpose": "table_read",
                    "audio_url": f"/generated_audio/{filename}",
                }
            ],
        )
        try:
            res = client.delete(f"/api/assets/{asset_id}")
            assert res.status_code == 200
            assert res.json()["deleted"] == asset_id
            assert res.json()["file_removed"] is True
            assert not wav.exists()

            rows = query(
                "SELECT count() FROM greenlight.generated_audio_assets WHERE asset_id = %(aid)s",
                {"aid": asset_id},
            )
            assert rows[0][0] == 0
        finally:
            wav.unlink(missing_ok=True)
            command(
                "DELETE FROM greenlight.generated_audio_assets WHERE asset_id = %(aid)s",
                {"aid": asset_id},
            )
            command("DELETE FROM greenlight.scripts WHERE id = %(sid)s", {"sid": script_id})

    def test_delete_nonexistent_404(self, client):
        assert client.delete("/api/assets/no-such-asset").status_code == 404

    def test_delete_twice_404(self, client):
        asset_id = str(uuid.uuid4())
        script_id = f"asset-test-{uuid.uuid4().hex[:8]}"
        _make_script(script_id)
        insert(
            "generated_audio_assets",
            [
                {
                    "asset_id": asset_id,
                    "script_id": script_id,
                    "scene_id": "s1",
                    "purpose": "scratch_track",
                    "audio_url": "/generated_audio/gone.wav",
                }
            ],
        )
        try:
            assert client.delete(f"/api/assets/{asset_id}").status_code == 200
            assert client.delete(f"/api/assets/{asset_id}").status_code == 404
        finally:
            command(
                "DELETE FROM greenlight.generated_audio_assets WHERE asset_id = %(aid)s",
                {"aid": asset_id},
            )
            command("DELETE FROM greenlight.scripts WHERE id = %(sid)s", {"sid": script_id})

    def test_delete_other_owners_asset_404(self, client):
        """Cross-tenant delete must 404 even when the asset exists."""
        asset_id = str(uuid.uuid4())
        script_id = f"asset-test-{uuid.uuid4().hex[:8]}"
        _make_script(script_id, owner="someone-else")
        insert(
            "generated_audio_assets",
            [
                {
                    "asset_id": asset_id,
                    "script_id": script_id,
                    "scene_id": "s1",
                    "purpose": "table_read",
                    "audio_url": "/generated_audio/not-yours.wav",
                }
            ],
        )
        try:
            assert client.delete(f"/api/assets/{asset_id}").status_code == 404
        finally:
            command(
                "DELETE FROM greenlight.generated_audio_assets WHERE asset_id = %(aid)s",
                {"aid": asset_id},
            )
            command("DELETE FROM greenlight.scripts WHERE id = %(sid)s", {"sid": script_id})


class TestListAssets:
    def test_list_assets_shape(self, client):
        res = client.get("/api/assets")
        assert res.status_code == 200
        assert isinstance(res.json(), list)
        if res.json():
            asset = res.json()[0]
            assert {"asset_id", "script_id", "audio_url", "file_exists"} <= set(asset)

    def test_list_assets_excludes_other_owners(self, client):
        """Assets tied to another owner's script must never be listed."""
        asset_id = str(uuid.uuid4())
        script_id = f"asset-test-{uuid.uuid4().hex[:8]}"
        _make_script(script_id, owner="someone-else")
        insert(
            "generated_audio_assets",
            [
                {
                    "asset_id": asset_id,
                    "script_id": script_id,
                    "scene_id": "s1",
                    "purpose": "table_read",
                    "audio_url": "/generated_audio/hidden.wav",
                }
            ],
        )
        try:
            res = client.get("/api/assets")
            assert res.status_code == 200
            assert all(a["asset_id"] != asset_id for a in res.json())
        finally:
            command(
                "DELETE FROM greenlight.generated_audio_assets WHERE asset_id = %(aid)s",
                {"aid": asset_id},
            )
            command("DELETE FROM greenlight.scripts WHERE id = %(sid)s", {"sid": script_id})
