"""Tests for dictation REST routes + vocabulary engine integration + WS handler.

The WS handler tests swap the Gemini Live session factory for a fake (DI at
the third-party network boundary — the one sanctioned exception to the
project's no-mocks rule, §12 of dev_plans/03-screenplay-dictation.md).
"""

import asyncio
import uuid
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from google.genai import types as genai_types

from greenlight.api.app import app
from greenlight.api.ws import dictation as ws_dictation
from greenlight.config import SCRIPTS_DIR


@pytest.fixture
def client():
    return TestClient(app)


SAMPLE = """INT. DINER - NIGHT

Rain hammers the window. SARAH sits alone with cold coffee.

SARAH
(quietly)
You said you'd call.

JOE
I know what I said.

CUT TO:

EXT. PARKING LOT - CONTINUOUS

Joe follows her into the rain.

JOE
Wait!
"""


@pytest.fixture
def script_id(client):
    sid = f"test_{uuid.uuid4().hex[:12]}"
    from greenlight.db.client import insert

    insert(
        "scripts",
        [
            {
                "id": sid,
                "title": "Dictation Test",
                "author": "t",
                "genre": "",
                "draft": 1,
                "owner": "local",
            }
        ],
    )
    yield sid
    from greenlight.db.client import get_ch_client

    get_ch_client().command(
        "DELETE FROM greenlight.scripts WHERE id = %(sid)s",
        parameters={"sid": sid},
    )


class TestDictationStartStop:
    def test_start_returns_session_id(self, client, script_id):
        res = client.post(
            f"/api/scripts/{script_id}/dictation/start",
            json={"scene_number": 1},
        )
        assert res.status_code == 200
        data = res.json()
        assert "session_id" in data
        assert data["script_id"] == script_id

    def test_start_unknown_script_404(self, client):
        res = client.post(
            "/api/scripts/nonexistent/dictation/start",
            json={"scene_number": 1},
        )
        assert res.status_code == 404

    def test_stop_after_start(self, client, script_id):
        start = client.post(
            f"/api/scripts/{script_id}/dictation/start",
            json={"scene_number": 1},
        )
        sid = start.json()["session_id"]
        res = client.post(
            f"/api/scripts/{script_id}/dictation/stop",
            json={"session_id": sid},
        )
        assert res.status_code == 200
        assert res.json()["ended"] is True


class TestVocabularyEngineIntegration:
    def test_extract_and_insert(self):
        from greenlight.tools.vocabulary_engine import (
            extract_vocabulary,
            fountain_insert,
        )

        terms, names = extract_vocabulary(SAMPLE)
        assert "SARAH" in names
        assert "JOE" in names

        # Simulate inserting a character cue
        cmd = {"action": "character", "value": "SARAH"}
        fountain = fountain_insert(cmd)
        assert fountain == "\n\nSARAH\n"

    def test_compound_character_flow(self):
        from greenlight.tools.vocabulary_engine import (
            detect_commands,
            fountain_insert,
        )

        result = detect_commands("character SALLY parenthetical laughing dialogue I agree")
        assert result.compound is True

        # Build fountain output
        parts = []
        for cmd in result.commands:
            parts.append(fountain_insert(cmd))
        if result.dialogue:
            parts.append(result.dialogue)
        text = "".join(parts)

        assert "\n\nSALLY\n" in text
        assert "(laughing)" in text
        assert "I agree" in text


# ---------------------------------------------------------------------------
# WS handler — fake Gemini Live session
# ---------------------------------------------------------------------------


def _final(text: str) -> genai_types.LiveServerMessage:
    # Real wire: finalized utterance on input_transcription with finished=None
    return genai_types.LiveServerMessage(
        server_content=genai_types.LiveServerContent(
            input_transcription=genai_types.Transcription(text=text)
        )
    )


def _interim(text: str) -> genai_types.LiveServerMessage:
    # Real wire: partials on the separate interim_input_transcription field
    return genai_types.LiveServerMessage(
        server_content=genai_types.LiveServerContent(
            interim_input_transcription=genai_types.Transcription(text=text)
        )
    )


class FakeGeminiSession:
    """Records sent audio, replays canned transcript events.

    receive() blocks until the client has sent audio or a stream-end signal so
    the relay cannot race ahead of test-side sends. With require_end=True it
    additionally waits for audio_stream_end (deterministic end-signal checks).
    """

    def __init__(self, events: list[genai_types.LiveServerMessage], require_end: bool = False):
        self.events = events
        self.require_end = require_end
        self.audio_chunks: list[bytes] = []
        self.end_signals = 0
        self.closed = False
        self._got_input = asyncio.Event()
        self._got_end = asyncio.Event()

    async def send_realtime_input(self, audio=None, audio_stream_end=None, **kwargs):
        if audio is not None:
            self.audio_chunks.append(audio.data)
            self._got_input.set()
        if audio_stream_end:
            self.end_signals += 1
            self._got_input.set()
            self._got_end.set()

    async def receive(self):
        await self._got_input.wait()
        if self.require_end:
            await self._got_end.wait()
        for event in self.events:
            yield event

    async def close(self):
        self.closed = True


class FakeConnect:
    def __init__(self, session: FakeGeminiSession):
        self.session = session

    async def __aenter__(self) -> FakeGeminiSession:
        return self.session

    async def __aexit__(self, *exc) -> bool:
        await self.session.close()
        return False


@pytest.fixture
def fake_gemini():
    """Installs the fake session factory; test sets fake_gemini['session']."""
    holder: dict = {}

    def factory(model, config):
        holder["model"] = model
        holder["config"] = config
        return FakeConnect(holder["session"])

    ws_dictation.set_session_factory(factory)
    yield holder
    ws_dictation.set_session_factory(ws_dictation._default_session_factory)


@pytest.fixture
def dictation_script():
    """Script text file read by read_script_text (file-based, no DB row needed)."""
    sid = f"dict_{uuid.uuid4().hex[:12]}"
    path = SCRIPTS_DIR / f"{sid}.txt"
    path.write_text(SAMPLE, encoding="utf-8")
    yield sid
    path.unlink(missing_ok=True)


@pytest.fixture
def committed_script_no_disk(client):
    """Script whose actors exist only as a committed DB version (no file on
    disk, clean session). Mirrors the prod bug: dictation read the root
    snapshot via read_script_text and missed committed characters."""
    sid = f"dictdb_{uuid.uuid4().hex[:12]}"
    from greenlight.db.client import insert

    insert(
        "scripts",
        [
            {
                "id": sid,
                "title": "Dictated Commit Test",
                "author": "t",
                "genre": "",
                "draft": 1,
                "owner": "local",
            }
        ],
    )
    load = client.post(f"/api/scripts/{sid}/load", json={"raw_text": "TITLE: Blank\n"}).json()
    client.post(
        f"/api/scripts/{sid}/versions",
        json={
            "branch_id": load["branch_id"],
            "base_version_id": load["version_id"],
            "message": "cast",
            "author": "t",
            "raw_fountain": "TITLE: Blank\n\nINT. DINER - NIGHT\n\nSARAH\nHi.\n\nJOE\nHey.\n",
        },
    )
    yield sid
    from greenlight.db.client import get_ch_client

    ch = get_ch_client()
    ch.command("DELETE FROM greenlight.scripts WHERE id = %(sid)s", parameters={"sid": sid})


@contextmanager
def _start_session(
    client: TestClient, holder: dict, sid: str, events, require_end: bool = False, scene_text=None
):
    session = FakeGeminiSession(events, require_end=require_end)
    holder["session"] = session
    with client.websocket_connect("/api/ws/dictation") as ws:
        start = {"type": "start", "script_id": sid}
        if scene_text is not None:
            start["scene_text"] = scene_text
        ws.send_json(start)
        started = ws.receive_json()
        assert started["type"] == "started"
        yield ws, session, started


class TestDictationWebSocket:
    def test_started_payload_and_config(self, client, fake_gemini, dictation_script):
        with _start_session(client, fake_gemini, dictation_script, []) as (ws, _, started):
            assert started["session_id"]
            assert started["vocabulary_count"] > 0
            assert "SARAH" in started["characters"]
            assert "JOE" in started["characters"]

            config = fake_gemini["config"]
            assert fake_gemini["model"]
            atc = config.input_audio_transcription
            assert atc.mode == genai_types.AudioTranscriptionConfigMode.SMART
            vocab_upper = [t.upper() for t in atc.custom_vocabulary]
            assert "SARAH" in vocab_upper
            assert "INT." in vocab_upper

    def test_unknown_script_returns_error(self, client, fake_gemini):
        fake_gemini["session"] = FakeGeminiSession([])
        with client.websocket_connect("/api/ws/dictation") as ws:
            ws.send_json({"type": "start", "script_id": "nope"})
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert msg["message"] == "Script not found"

    def test_committed_actors_in_shortlist(self, client, fake_gemini, committed_script_no_disk):
        """Actors committed as a DB version (no disk file) must reach the 1-9
        shortlist — regression for dictation reading the root snapshot instead
        of the branch head."""
        with _start_session(client, fake_gemini, committed_script_no_disk, []) as (ws, _, started):
            chars = started["characters"]
            assert "SARAH" in chars
            assert "JOE" in chars

    def test_binary_audio_and_stream_end_forwarded(self, client, fake_gemini, dictation_script):
        with _start_session(
            client, fake_gemini, dictation_script, [_final("Hello there.")], require_end=True
        ) as (
            ws,
            session,
            _,
        ):
            chunk = b"\x01\x02" * 1600
            ws.send_bytes(chunk)
            ws.send_json({"type": "audio_stream_end"})

            msg = ws.receive_json()
            assert msg == {"type": "transcript", "text": "Hello there.", "is_final": True}
            assert session.audio_chunks == [chunk]
            assert session.end_signals == 1

    def test_command_utterance_discards_raw_text(self, client, fake_gemini, dictation_script):
        with _start_session(
            client, fake_gemini, dictation_script, [_final("New scene interior office night.")]
        ) as (ws, _, _):
            ws.send_bytes(b"\x00" * 3200)

            msg = ws.receive_json()
            assert msg["type"] == "command"
            assert msg["action"] == "scene_heading"
            assert msg["value"] == "INT. OFFICE - NIGHT"

    def test_compound_emission_order(self, client, fake_gemini, dictation_script):
        with _start_session(
            client,
            fake_gemini,
            dictation_script,
            [_final("Character SALLY parenthetical laughing dialogue I agree.")],
        ) as (ws, _, _):
            ws.send_bytes(b"\x00" * 3200)

            first = ws.receive_json()
            second = ws.receive_json()
            third = ws.receive_json()
            assert first == {"type": "command", "action": "character", "value": "SALLY"}
            assert second == {"type": "command", "action": "parenthetical", "value": "(laughing)"}
            assert third == {
                "type": "transcript",
                "text": "I agree",
                "is_final": True,
                "compound": True,
            }

    def test_interim_then_final(self, client, fake_gemini, dictation_script):
        with _start_session(
            client, fake_gemini, dictation_script, [_interim("hel"), _final("Hello.")]
        ) as (ws, _, _):
            ws.send_bytes(b"\x00" * 3200)

            interim = ws.receive_json()
            final = ws.receive_json()
            assert interim == {"type": "transcript", "text": "hel", "is_final": False}
            assert final == {"type": "transcript", "text": "Hello.", "is_final": True}

    def test_duplicate_final_deduped(self, client, fake_gemini, dictation_script):
        # Gemini Live double-emits the same final when turn detection AND a
        # client audio_stream_end flush the same span; relay must drop the
        # duplicate echo or the editor inserts the text twice.
        with _start_session(
            client,
            fake_gemini,
            dictation_script,
            [_final("Hello there."), _final("Hello there.")],
        ) as (ws, _, _):
            ws.send_bytes(b"\x00" * 3200)

            msg = ws.receive_json()
            assert msg == {"type": "transcript", "text": "Hello there.", "is_final": True}
            with pytest.raises(Exception):
                ws.receive_json()

    def test_delete_command_from_tail(self, client, fake_gemini, dictation_script):
        with _start_session(
            client, fake_gemini, dictation_script, [_final("and then scratch that.")]
        ) as (ws, _, _):
            ws.send_bytes(b"\x00" * 3200)

            msg = ws.receive_json()
            assert msg["type"] == "command"
            assert msg["action"] == "delete"
            assert msg["scope"] == "last_segment"

    def test_action_caps_first_appearance_unseen_in_scene(
        self, client, fake_gemini, dictation_script
    ):
        # SARAH has cues elsewhere in the script but is absent from the
        # dictated scene text → first mention in dictated action gets capped
        with _start_session(
            client,
            fake_gemini,
            dictation_script,
            [_final("sarah walks into the rain.")],
            scene_text="INT. DINER - NIGHT\n\nRain hammers the window.",
        ) as (ws, _, _):
            ws.send_bytes(b"\x00" * 3200)
            msg = ws.receive_json()
            assert msg == {
                "type": "transcript",
                "text": "SARAH walks into the rain.",
                "is_final": True,
            }

    def test_action_no_recap_for_name_already_in_scene(self, client, fake_gemini, dictation_script):
        with _start_session(
            client,
            fake_gemini,
            dictation_script,
            [_final("sarah walks into the rain.")],
            scene_text="INT. DINER - NIGHT\n\nSARAH sits alone.",
        ) as (ws, _, _):
            ws.send_bytes(b"\x00" * 3200)
            msg = ws.receive_json()
            assert msg == {
                "type": "transcript",
                "text": "sarah walks into the rain.",
                "is_final": True,
            }

    def test_stop_closes_session(self, client, fake_gemini, dictation_script):
        with _start_session(client, fake_gemini, dictation_script, []) as (ws, session, _):
            ws.send_json({"type": "stop"})
        assert session.closed is True

    def test_session_warn_and_expired_timers(
        self, client, fake_gemini, dictation_script, monkeypatch
    ):
        monkeypatch.setattr(ws_dictation.settings, "dictation_session_warn_seconds", 0.05)
        monkeypatch.setattr(ws_dictation.settings, "dictation_session_max_seconds", 0.1)

        with _start_session(client, fake_gemini, dictation_script, []) as (ws, _, _):
            warn = ws.receive_json()
            expired = ws.receive_json()
            assert warn["type"] == "session_warn"
            assert warn["remaining_seconds"] > 0
            assert expired == {"type": "session_expired"}
