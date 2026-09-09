"""Deterministic active_sessions resolution (ms timestamps, plain MergeTree).

Regression tests for the session tie/dedup bug: ReplacingMergeTree(updated_at)
on the shared engine kept arbitrary (non-max) survivors at merge time, so
set_active writes appeared to vanish and sessions randomly reverted to older
scripts or empty state. Now: plain MergeTree (rows never collapse) +
millisecond timestamps + argMax-style read.
"""

import pytest
from fastapi.testclient import TestClient

from greenlight.api.app import app
from greenlight.api.services.script_repo.state import (
    get_active,
    set_active,
    unload_script,
)
from greenlight.db.client import command, insert, query

TEST_PRINCIPAL = "test-active-sessions-ms"


@pytest.fixture
def clean_active_sessions():
    """Isolate active_sessions rows created by these tests."""
    yield
    command(
        "ALTER TABLE greenlight.active_sessions DELETE WHERE principal = %(p)s",
        {"p": TEST_PRINCIPAL},
    )
    command("ALTER TABLE greenlight.active_sessions DELETE WHERE principal = 'local'")


pytestmark = pytest.mark.usefixtures("clean_active_sessions")


@pytest.fixture
def client():
    return TestClient(app)


def _latest_row(principal: str) -> tuple:
    rows = query(
        "SELECT script_id, version_id FROM greenlight.active_sessions "
        "WHERE principal = %(p)s ORDER BY updated_at DESC LIMIT 1",
        {"p": principal},
    )
    return rows[0] if rows else ("", "")


class TestActiveSessionsMs:
    def test_column_is_millisecond_precision(self):
        types = query(
            "SELECT type FROM system.columns "
            "WHERE database = currentDatabase() AND table = 'active_sessions' "
            "AND name = 'updated_at'"
        )
        assert types and types[0][0].startswith("DateTime64")

    def test_engine_is_not_replacing(self):
        engines = query(
            "SELECT engine FROM system.tables "
            "WHERE database = currentDatabase() AND table = 'active_sessions'"
        )
        assert engines and "Replacing" not in engines[0][0]

    def test_rapid_switch_resolves_to_last_write(self):
        """Load A, load B, reload A in quick succession: latest row must win."""
        set_active("script-a", "br-a", "ver-a1")
        set_active("script-b", "br-b", "ver-b1")
        set_active("script-a", "br-a", "ver-a2")
        assert get_active() == {
            "script_id": "script-a",
            "branch_id": "br-a",
            "version_id": "ver-a2",
        }

    def test_unload_clears_then_load_restores(self):
        """Unload writes an empty row; a fresh load must deterministically
        win afterwards (the old bug: empty row and load row tied and the
        empty row could win)."""
        set_active("script-a", "br-a", "ver-a1")
        unload_script()
        assert get_active()["script_id"] == ""
        set_active("script-a", "br-a", "ver-a2")
        assert get_active() == {
            "script_id": "script-a",
            "branch_id": "br-a",
            "version_id": "ver-a2",
        }

    def test_explicit_ms_offsets_never_tie(self):
        """Rows with explicit sub-second offsets resolve by offset order,
        proving ms precision drives the latest-row selection."""
        command(
            "ALTER TABLE greenlight.active_sessions DELETE WHERE principal = %(p)s",
            {"p": TEST_PRINCIPAL},
        )
        insert(
            "active_sessions",
            [
                {
                    "principal": TEST_PRINCIPAL,
                    "script_id": "early",
                    "branch_id": "br",
                    "version_id": "ver-early",
                    "updated_at": "2026-09-08 12:00:00.000",
                },
                {
                    "principal": TEST_PRINCIPAL,
                    "script_id": "late",
                    "branch_id": "br",
                    "version_id": "ver-late",
                    "updated_at": "2026-09-08 12:00:00.500",
                },
            ],
        )
        rows = query(
            "SELECT script_id FROM greenlight.active_sessions WHERE principal = %(p)s",
            {"p": TEST_PRINCIPAL},
        )
        assert len(rows) == 2  # plain MergeTree: rows never collapse
        assert _latest_row(TEST_PRINCIPAL) == ("late", "ver-late")

    def test_load_endpoint_sets_session_for_switched_script(self, client):
        """End-to-end: load script A, then B via /load — /session/active must
        always reflect the last load, never the earlier one."""
        a = client.post("/api/scripts/create", json={"title": "Switch A"}).json()["id"]
        b = client.post("/api/scripts/create", json={"title": "Switch B"}).json()["id"]

        client.post(f"/api/scripts/{a}/load", json={})
        assert client.get("/api/session/active").json()["script_id"] == a

        client.post(f"/api/scripts/{b}/load", json={})
        assert client.get("/api/session/active").json()["script_id"] == b

        client.post(f"/api/scripts/{a}/load", json={})
        assert client.get("/api/session/active").json()["script_id"] == a
