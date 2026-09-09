"""Tests for GET /scripts/{id}/text DB fallback (ephemeral uploads dir)."""

import pytest
from fastapi.testclient import TestClient

from greenlight.api.app import app
from greenlight.config import SCRIPTS_DIR
from greenlight.db.client import command


@pytest.fixture
def client():
    return TestClient(app)


def _cleanup(sid: str):
    for suffix in ("", ".txt", ".format"):
        (SCRIPTS_DIR / f"{sid}{suffix}").unlink(missing_ok=True)
    command("DELETE FROM greenlight.script_versions WHERE script_id = %(sid)s", {"sid": sid})
    command("DELETE FROM greenlight.script_branches WHERE script_id = %(sid)s", {"sid": sid})
    command("DELETE FROM greenlight.scripts WHERE id = %(sid)s", {"sid": sid})


class TestScriptTextFallback:
    def test_text_served_from_db_when_disk_files_gone(self, client):
        res = client.post("/api/scripts/create", json={"title": "Ephemeral", "author": "T"})
        sid = res.json()["id"]
        try:
            (SCRIPTS_DIR / sid).unlink(missing_ok=True)
            (SCRIPTS_DIR / f"{sid}.txt").unlink(missing_ok=True)

            res = client.get(f"/api/scripts/{sid}/text")
            assert res.status_code == 200
            assert "Title: Ephemeral" in res.text
        finally:
            _cleanup(sid)

    def test_text_404_when_nothing_anywhere(self, client):
        assert client.get("/api/scripts/no-such-id/text").status_code == 404
