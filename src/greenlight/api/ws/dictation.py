"""WebSocket handler for Gemini Live dictation.

Bidirectional relay: client sends binary audio + JSON control,
server sends JSON outbound (transcripts, commands, session events).

Hard rule: NEVER call receive_bytes() / receive_text() on a mixed-frame
socket — always raw receive() + branch on bytes/text key.
"""

import asyncio
import json
import logging
import time
import uuid
from collections import deque
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from google.genai import types as genai_types

from ...config import settings
from ...tools.vocabulary_engine import (
    capitalize_first_appearance,
    check_stoplist_collisions,
    detect_commands,
    extract_vocabulary,
    rank_characters,
    seed_seen_names,
    strip_list_artifacts,
)
from ...utils.genai_client import get_dictation_client

logger = logging.getLogger(__name__)

router = APIRouter()

_RING_BUFFER_MAX = 30

# Gemini Live double-emits a final when its turn detection and a client-raised
# audio_stream_end flush the same span; suppress the duplicate echo.
_FINAL_DEDUP_WINDOW = 2.0


def _default_session_factory(model: str, config: genai_types.LiveConnectConfig) -> Any:
    client = get_dictation_client()
    return client.aio.live.connect(model=model, config=config)


# DI boundary for the Gemini Live session (third-party network seam — tests
# swap in a fake via set_session_factory).
_session_factory: Callable[[str, genai_types.LiveConnectConfig], Any] = _default_session_factory


def set_session_factory(factory: Callable[[str, genai_types.LiveConnectConfig], Any]) -> None:
    global _session_factory
    _session_factory = factory


async def _client_to_gemini(ws: WebSocket, session, buf: deque) -> None:
    """Pump: client WS → Gemini Live session."""
    while True:
        message = await ws.receive()
        if message["type"] == "websocket.disconnect":
            break

        if "bytes" in message:
            chunk = message["bytes"]
            if session is not None:
                await session.send_realtime_input(
                    audio=genai_types.Blob(data=chunk, mime_type="audio/pcm;rate=16000")
                )
            else:
                buf.append(chunk)

        elif "text" in message:
            try:
                data = json.loads(message["text"])
            except json.JSONDecodeError:
                continue

            msg_type = data.get("type", "")

            if msg_type == "audio_stream_end":
                if session is not None:
                    await session.send_realtime_input(audio_stream_end=True)

            elif msg_type == "stop":
                break

            elif msg_type == "audio" and "data" in data:
                import base64

                raw = base64.b64decode(data["data"])
                if session is not None:
                    await session.send_realtime_input(
                        audio=genai_types.Blob(data=raw, mime_type="audio/pcm;rate=16000")
                    )
                else:
                    buf.append(raw)


async def _gemini_to_client(
    ws: WebSocket,
    session,
    mode: list[str],
    character_names: list[str],
    seen_names: set[str],
) -> None:
    """Pump: Gemini Live session → client WS. Applies command detection.

    Wire semantics (verified against the live preview endpoint): partials
    arrive on ``interim_input_transcription``; the finalized utterance arrives
    on ``input_transcription`` with ``finished`` left None — so presence of
    ``input_transcription`` itself marks the final, not any flag.
    """
    # Gemini Live can finalize the same span twice (its own turn detection
    # PLUS our client-side audio_stream_end both flush it) → drop an identical
    # consecutive final so the editor doesn't insert the text twice.
    last_final: list[tuple[str | None, float]] = [(None, 0.0)]  # (text, start monotonic)

    def _dedupe(text: str) -> bool:
        now = time.monotonic()
        prev_text, prev_at = last_final[0]
        if prev_text == text and now - prev_at < _FINAL_DEDUP_WINDOW:
            return True
        last_final[0] = (text, now)
        return False

    async for message in session.receive():
        sc = message.server_content
        if sc is None:
            continue

        interim = sc.interim_input_transcription
        if interim is not None and interim.text:
            await ws.send_json({"type": "transcript", "text": interim.text, "is_final": False})
            continue

        inp = sc.input_transcription
        if inp is not None and inp.text:
            text = inp.text
            clean = strip_list_artifacts(text)
            result = detect_commands(clean)

            if result.commands:
                for cmd in result.commands:
                    await ws.send_json({"type": "command", **cmd})
                    action = cmd["action"]
                    if action == "character":
                        mode[0] = "dialogue"
                        seen_names.add(cmd["value"].upper())
                    elif action in ("new_paragraph", "scene_heading", "transition"):
                        mode[0] = "action"

            if result.dialogue:
                if not _dedupe(result.dialogue):
                    await ws.send_json(
                        {
                            "type": "transcript",
                            "text": result.dialogue,
                            "is_final": True,
                            "compound": True,
                        }
                    )
            elif not result.commands:
                if mode[0] == "action":
                    prose, seen_names = capitalize_first_appearance(
                        clean, character_names, seen_names
                    )
                else:
                    prose = clean
                if not _dedupe(prose):
                    await ws.send_json({"type": "transcript", "text": prose, "is_final": True})


async def _session_timers(ws: WebSocket, session_id: str) -> None:
    """Warn at 8 min, kill at 10 min."""
    warn_at = settings.dictation_session_warn_seconds
    kill_at = settings.dictation_session_max_seconds

    await asyncio.sleep(warn_at)
    try:
        await ws.send_json({"type": "session_warn", "remaining_seconds": kill_at - warn_at})
    except Exception:
        return

    await asyncio.sleep(kill_at - warn_at)
    try:
        await ws.send_json({"type": "session_expired"})
    except Exception:
        pass


@router.websocket("/ws/dictation")
async def dictation_websocket(ws: WebSocket):
    await ws.accept()

    session = None
    session_id = None
    timer_task = None
    mode = ["action"]
    seen_names: set[str] = set()
    character_names: list[str] = []
    buf: deque[bytes] = deque(maxlen=_RING_BUFFER_MAX)

    try:
        # ── Phase 1: Wait for start message ──────────────────────────
        start_msg = None
        while start_msg is None:
            raw = await ws.receive()
            if raw["type"] == "websocket.disconnect":
                return
            if "text" in raw:
                try:
                    data = json.loads(raw["text"])
                    if data.get("type") == "start":
                        start_msg = data
                except json.JSONDecodeError:
                    pass

        script_id = start_msg.get("script_id", "")

        if not script_id:
            await ws.send_json({"type": "error", "message": "script_id required"})
            return

        # ── Phase 2: Extract vocabulary ───────────────────────────────
        from ...api.routes.screenplay import get_current_text

        try:
            # HEAD-resolving: active branch head first, then upload/file/root.
            # read_script_text alone (root snapshot) misses committed actors.
            script_text = get_current_text(script_id)
        except Exception:
            await ws.send_json({"type": "error", "message": "Script not found"})
            return

        vocabulary, character_names = extract_vocabulary(script_text)
        shortlist = rank_characters(script_text, character_names)
        collisions = check_stoplist_collisions(character_names)

        # Seed "seen" from the scene being dictated only — names introduced
        # elsewhere in the script should still cap on first mention here.
        scene_text = start_msg.get("scene_text") or ""
        seen_names = seed_seen_names(scene_text, character_names)

        # ── Phase 3: Connect to Gemini Live ───────────────────────────
        session_id = str(uuid.uuid4())
        config = genai_types.LiveConnectConfig(
            response_modalities=[genai_types.Modality.TEXT],
            input_audio_transcription=genai_types.AudioTranscriptionConfig(
                language_codes=[],
                custom_vocabulary=vocabulary,
                mode=genai_types.AudioTranscriptionConfigMode.SMART,
            ),
        )

        # ── Phase 4-6: Session lifecycle ─────────────────────────────
        async with _session_factory(settings.dictation_model, config) as live_session:
            session = live_session

            await ws.send_json(
                {
                    "type": "started",
                    "session_id": session_id,
                    "vocabulary_count": len(vocabulary),
                    "characters": shortlist,
                    "stoplist_collisions": collisions,
                }
            )

            while buf:
                chunk = buf.popleft()
                await session.send_realtime_input(
                    audio=genai_types.Blob(data=chunk, mime_type="audio/pcm;rate=16000")
                )

            timer_task = asyncio.create_task(_session_timers(ws, session_id))

            async with asyncio.TaskGroup() as tg:
                t1 = tg.create_task(_client_to_gemini(ws, session, buf))
                t2 = tg.create_task(
                    _gemini_to_client(ws, session, mode, character_names, seen_names)
                )
                t1.add_done_callback(lambda _: t2.cancel())
                t2.add_done_callback(lambda _: t1.cancel())

    except WebSocketDisconnect:
        logger.info("Dictation client disconnected")
    except Exception as e:
        logger.error(f"Dictation WS error: {e}", exc_info=True)
    finally:
        if timer_task is not None:
            timer_task.cancel()
            try:
                await timer_task
            except asyncio.CancelledError:
                pass
        if session is not None:
            try:
                await session.close()
            except Exception:
                pass
        try:
            await ws.close()
        except Exception:
            pass
