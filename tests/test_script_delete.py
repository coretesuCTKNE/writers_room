"""Tests for soft script deletion (mutation-free, children preserved)."""

import pytest
from fastapi.testclient import TestClient

from greenlight.api.app import app
from greenlight.db.client import command, query


@pytest.fixture
def client():
    return TestClient(app)


def _cleanup(sid: str):
    command("DELETE FROM greenlight.script_versions WHERE script_id = %(sid)s", {"sid": sid})
    command("DELETE FROM greenlight.script_branches WHERE script_id = %(sid)s", {"sid": sid})
    command("DELETE FROM greenlight.scenes WHERE script_id = %(sid)s", {"sid": sid})
    command("DELETE FROM greenlight.scripts WHERE id = %(sid)s", {"sid": sid})


class TestDeleteScript:
    def test_delete_hides_script_everywhere(self, client):
        res = client.post("/api/scripts/create", json={"title": "Doomed Script", "author": "T"})
        sid = res.json()["id"]
        try:
            assert any(s["id"] == sid for s in client.get("/api/scripts").json())

            res = client.delete(f"/api/scripts/{sid}")
            assert res.status_code == 200
            assert res.json() == {"ok": True}

            assert not any(s["id"] == sid for s in client.get("/api/scripts").json())
            assert client.get(f"/api/scripts/{sid}").status_code == 404
            # 404 gate on script-bound routes (get_script_or_404 filters deleted)
            gated = client.post(
                f"/api/scripts/{sid}/coverage", json={"script_text": "Hello world."}
            )
            assert gated.status_code == 404
        finally:
            _cleanup(sid)

    def test_delete_is_soft_row_survives_with_deleted_at(self, client):
        res = client.post("/api/scripts/create", json={"title": "Soft Del", "author": "T"})
        sid = res.json()["id"]
        try:
            client.delete(f"/api/scripts/{sid}")

            rows = query(
                "SELECT deleted_at FROM greenlight.scripts WHERE id = %(sid)s",
                {"sid": sid},
            )
            assert rows, "scripts row must survive soft delete"
            assert rows[0][0].year > 1970, "deleted_at must be set to a real timestamp"

            versions = query(
                "SELECT count() FROM greenlight.script_versions WHERE script_id = %(sid)s",
                {"sid": sid},
            )
            assert versions[0][0] > 0, "children (script_versions) must stay intact"
        finally:
            _cleanup(sid)

    def test_double_delete_404(self, client):
        res = client.post("/api/scripts/create", json={"title": "Once Only", "author": "T"})
        sid = res.json()["id"]
        try:
            assert client.delete(f"/api/scripts/{sid}").status_code == 200
            assert client.delete(f"/api/scripts/{sid}").status_code == 404
        finally:
            _cleanup(sid)

    def test_delete_nonexistent_404(self, client):
        assert client.delete("/api/scripts/no-such-script").status_code == 404
