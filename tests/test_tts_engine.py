"""TTS engine: per-call timeout behavior."""

import asyncio
import time
import uuid

from greenlight.config import settings
from greenlight.tools import tts_engine
from greenlight.tools.fountain_parser import DialogueTurn
from greenlight.tools.voice_casting import VoiceAssignment


class _HangingModels:
    def generate_content(self, *args, **kwargs):
        time.sleep(10)
        raise AssertionError("should have been abandoned by timeout")


class _HangingClient:
    models = _HangingModels()


async def test_turn_audio_times_out(monkeypatch):
    """A hung TTS call returns None after tts_call_timeout_seconds, not 10s."""
    monkeypatch.setattr(settings, "tts_call_timeout_seconds", 0.2)
    monkeypatch.setattr(tts_engine, "_get_client", lambda: _HangingClient())

    turn = DialogueTurn(speaker="AVA", text=f"timeout probe {uuid.uuid4().hex}")
    voice = VoiceAssignment(character_name="AVA", voice_id="kore")

    start = time.monotonic()
    result = await tts_engine.generate_turn_audio(turn, voice, asyncio.Semaphore(1))
    elapsed = time.monotonic() - start

    assert result is None
    assert elapsed < 5
