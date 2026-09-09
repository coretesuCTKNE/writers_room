"""Take retention: principal keeps only N newest table-read takes, older takes
(and their paired backing tracks) are deleted — files and DB rows.

Covers the retention service directly plus its wiring into the generate route.
Uses a throwaway fake owner so real dev-DB assets are never pruned by tests.
"""

import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from greenlight.api.app import app
from greenlight.api.services import audio_retention
from greenlight.config import settings
from greenlight.db.client import command, insert, query

AUDIO_DIR = Path("generated_audio")
OWNER = f"ret-{uuid.uuid4().hex[:8]}"
BASE_TS = datetime(2026, 1, 1, 12, 0, 0)

SCENE = """INT. LAB - NIGHT

AVA
Line one.

REX
Line two.
"""


def _wait_for(check, timeout=5.0):
    """Poll until check() is truthy (ClickHouse ALTER DELETE is async)."""
    deadline = time.monotonic() + timeout
    while True:
        if check():
            return True
        if time.monotonic() > deadline:
            return False
        time.sleep(0.25)


def _count_rows(asset_ids):
    if not asset_ids:
        return 0
    rows = query(
        "SELECT count() FROM greenlight.generated_audio_assets WHERE asset_id IN %(ids)s",
        {"ids": tuple(asset_ids)},
    )
    return rows[0][0]


@pytest.fixture(autouse=True)
def _retention_settings(monkeypatch):
    monkeypatch.setattr(settings, "table_read_take_limit", 3)
    monkeypatch.setattr(audio_retention, "current_principal", lambda: OWNER)


def _make_script(script_id, owner=OWNER):
    insert(
        "scripts",
        [
            {
                "id": script_id,
                "title": "Retention test",
                "author": "t",
                "hash": "",
                "owner": owner,
            }
        ],
    )


def _seed_take(script_id, scene_id, stamp, minutes, with_backing=True):
    """Insert one take (table_read asset) + optional paired backing track.

    Explicit created_at (BASE_TS + minutes) makes newest/oldest deterministic.
    Returns ([asset_ids], [files]).
    """
    rows = []
    files = []
    ref = AUDIO_DIR / f"table_read_{stamp}.wav"
    ref.write_bytes(b"RIFF-ref")
    files.append(ref)
    rows.append(
        {
            "asset_id": str(uuid.uuid4()),
            "script_id": script_id,
            "scene_id": scene_id,
            "purpose": "table_read",
            "audio_url": f"/generated_audio/table_read_{stamp}.wav",
        }
    )
    if with_backing:
        back = AUDIO_DIR / f"backing_track_{stamp}.wav"
        back.write_bytes(b"RIFF-back")
        files.append(back)
        rows.append(
            {
                "asset_id": str(uuid.uuid4()),
                "script_id": script_id,
                "scene_id": scene_id,
                "purpose": "backing_track",
                "audio_url": f"/generated_audio/backing_track_{stamp}.wav",
            }
        )
    created_at = BASE_TS + timedelta(minutes=minutes)
    for row in rows:
        row["created_at"] = created_at
    insert("generated_audio_assets", rows)
    return [r["asset_id"] for r in rows], files


def _cleanup(files, script_ids):
    for f in files:
        f.unlink(missing_ok=True)
    for sid in script_ids:
        command(
            "DELETE FROM greenlight.generated_audio_assets WHERE script_id = %(sid)s",
            {"sid": sid},
        )
        command(
            "DELETE FROM greenlight.table_read_takes WHERE script_id = %(sid)s",
            {"sid": sid},
        )
        command("DELETE FROM greenlight.scripts WHERE id = %(sid)s", {"sid": sid})


class TestPruneService:
    def test_prune_removes_oldest_takes_and_backings(self):
        sid = f"ret-{uuid.uuid4().hex[:8]}"
        _make_script(sid)
        ids, files = [], []
        try:
            for i in range(5):
                take_ids, take_files = _seed_take(sid, "scene_a", f"{i:08x}", minutes=i)
                ids += take_ids
                files += take_files

            removed = audio_retention.prune_table_read_takes()

            assert removed == 2
            assert _wait_for(lambda: _count_rows(ids[:4]) == 0)
            assert _count_rows(ids[4:]) == 6
            assert not files[0].exists()
            assert not files[3].exists()
            assert files[4].exists() and files[5].exists()
        finally:
            _cleanup(files, [sid])

    def test_zero_limit_disables_prune(self, monkeypatch):
        monkeypatch.setattr(settings, "table_read_take_limit", 0)
        sid = f"ret-{uuid.uuid4().hex[:8]}"
        _make_script(sid)
        ids, files = [], []
        try:
            for i in range(5):
                take_ids, take_files = _seed_take(sid, "scene_a", f"{i:08x}", minutes=i)
                ids += take_ids
                files += take_files

            assert audio_retention.prune_table_read_takes() == 0
            assert _count_rows(ids) == 10
        finally:
            _cleanup(files, [sid])

    def test_other_owner_untouched(self):
        other = f"ret-{uuid.uuid4().hex[:8]}"
        sid = f"ret-{uuid.uuid4().hex[:8]}"
        _make_script(sid, owner=other)
        ids, files = [], []
        try:
            for i in range(5):
                take_ids, take_files = _seed_take(sid, "scene_a", f"{i:08x}", minutes=i)
                ids += take_ids
                files += take_files

            assert audio_retention.prune_table_read_takes() == 0
            assert _count_rows(ids) == 10
            assert files[0].exists()
        finally:
            _cleanup(files, [sid])

    def test_backing_with_mismatched_stamp_survives(self):
        sid = f"ret-{uuid.uuid4().hex[:8]}"
        _make_script(sid)
        ids, files = [], []
        stray_back = AUDIO_DIR / "backing_track_deadbeef.wav"
        stray_back.write_bytes(b"RIFF-stray")
        try:
            for i in range(4):
                take_ids, take_files = _seed_take(
                    sid, "scene_a", f"{i:08x}", minutes=i, with_backing=(i > 0)
                )
                ids += take_ids
                files += take_files
            stray_id = str(uuid.uuid4())
            insert(
                "generated_audio_assets",
                [
                    {
                        "asset_id": stray_id,
                        "script_id": sid,
                        "scene_id": "scene_a",
                        "purpose": "backing_track",
                        "audio_url": "/generated_audio/backing_track_deadbeef.wav",
                        "created_at": BASE_TS,
                    }
                ],
            )
            ids.append(stray_id)

            removed = audio_retention.prune_table_read_takes()

            assert removed == 1
            assert _wait_for(lambda: _count_rows(ids[:1]) == 0)
            assert _count_rows([stray_id]) == 1
            assert stray_back.exists()
        finally:
            _cleanup(files + [stray_back], [sid])


class TestRouteWiring:
    @pytest.fixture
    def client(self, monkeypatch):
        monkeypatch.setattr(settings, "table_read_take_limit", 1)
        monkeypatch.setattr("greenlight.api.routes.table_read.is_tts_available", lambda: False)
        monkeypatch.setattr("greenlight.api.routes._helpers.current_principal", lambda: OWNER)
        return TestClient(app)

    def test_generate_prunes_to_limit(self, client):
        sid = f"ret-{uuid.uuid4().hex[:8]}"
        _make_script(sid)
        body = {"script_id": sid, "scene_number": 1, "scene_text": SCENE}
        try:
            first = client.post("/api/table-read/generate", json=body)
            assert first.status_code == 200
            second = client.post("/api/table-read/generate", json=body)
            assert second.status_code == 200

            def one_take_left():
                return (
                    query(
                        "SELECT count() FROM greenlight.generated_audio_assets "
                        "WHERE script_id = %(sid)s AND purpose = 'table_read'",
                        {"sid": sid},
                    )[0][0]
                    == 1
                )

            assert _wait_for(one_take_left)
            kept_url = query(
                "SELECT audio_url FROM greenlight.generated_audio_assets "
                "WHERE script_id = %(sid)s AND purpose = 'table_read'",
                {"sid": sid},
            )[0][0]
            assert (AUDIO_DIR / kept_url.rsplit("/", 1)[-1]).exists()
        finally:
            urls = query(
                "SELECT audio_url FROM greenlight.generated_audio_assets WHERE script_id = %(sid)s",
                {"sid": sid},
            )
            _cleanup(
                [AUDIO_DIR / u[0].rsplit("/", 1)[-1] for u in urls],
                [sid],
            )
