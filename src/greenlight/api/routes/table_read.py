import hashlib
import json
import logging
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ...config import settings
from ...db.client import insert, query
from ...tools.audio_store import store_audio
from ...tools.fountain_parser import parse_scene
from ...tools.stitcher import stitch_backing_track, stitch_table_read
from ...tools.tts_engine import generate_table_read, is_tts_available
from ...tools.voice_casting import (
    GEMINI_VOICES,
    build_voice_casting,
    get_voice_preferences,
)
from ..services.audio_retention import prune_table_read_takes
from ._helpers import get_script_or_404

logger = logging.getLogger(__name__)

router = APIRouter()


class TableReadRequest(BaseModel):
    script_id: str
    scene_text: str
    user_character: str | None = None
    voice_preferences: dict[str, str] | None = None
    narration: bool = False
    scene_number: int = Field(default=0, ge=0, le=65535)


class TableReadLookupRequest(BaseModel):
    script_id: str
    scene_text: str
    scene_number: int = Field(default=0, ge=0, le=65535)


def _scene_hash(scene_text: str) -> str:
    normalized = "\n".join(line.strip() for line in scene_text.splitlines()).strip()
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


@router.get("/voices")
async def list_voices():
    return [
        {"key": key, "id": v["id"], "style": v["style"], "gender": v["gender"]}
        for key, v in GEMINI_VOICES.items()
    ]


@router.post("/table-read/generate")
async def generate_table_read_route(req: TableReadRequest):
    get_script_or_404(req.script_id)
    try:
        scene = parse_scene(
            req.scene_text,
            scene_id=f"scene_{uuid.uuid4().hex[:8]}",
            include_narration=req.narration,
        )

        if not scene.turns:
            raise HTTPException(400, "No dialogue turns found in scene")

        max_turns = settings.table_read_max_turns
        if max_turns and len(scene.turns) > max_turns:
            raise HTTPException(
                400,
                f"Scene has {len(scene.turns)} dialogue turns; table-read "
                f"supports up to {max_turns}. Split the scene or disable narration.",
            )

        voices = build_voice_casting(
            characters=scene.characters,
            script_id=req.script_id,
            preferences={
                **get_voice_preferences(req.script_id),
                **(req.voice_preferences or {}),
            },
        )
        voice_map = {v.character_name: v for v in voices}

        tts_available = is_tts_available()
        audio_urls: list[str | None]
        if tts_available:
            audio_urls = await generate_table_read(scene.turns, voice_map)
        else:
            audio_urls = [None] * len(scene.turns)

        stamp = uuid.uuid4().hex[:8]
        reference_path = stitch_table_read(
            scene.turns, audio_urls, output_path=f"generated_audio/table_read_{stamp}.wav"
        )

        backing_path = None
        if req.user_character:
            backing_path = stitch_backing_track(
                scene.turns,
                audio_urls,
                req.user_character,
                output_path=f"generated_audio/backing_track_{stamp}.wav",
            )

        reference_url = store_audio(reference_path)
        backing_url = store_audio(backing_path) if backing_path else None

        asset_id = str(uuid.uuid4())
        try:
            rows = [
                {
                    "asset_id": asset_id,
                    "script_id": req.script_id,
                    "scene_id": scene.scene_id,
                    "purpose": "table_read",
                    "audio_url": reference_url,
                }
            ]
            if backing_url:
                rows.append(
                    {
                        "asset_id": str(uuid.uuid4()),
                        "script_id": req.script_id,
                        "scene_id": scene.scene_id,
                        "purpose": "backing_track",
                        "audio_url": backing_url,
                    }
                )
            insert("generated_audio_assets", rows)
        except Exception as e:
            logger.warning(f"Failed to persist audio asset: {e}", exc_info=True)

        try:
            prune_table_read_takes()
        except Exception as e:
            logger.warning(f"Take retention failed: {e}", exc_info=True)

        response = {
            "asset_id": asset_id,
            "scene_id": scene.scene_id,
            "scene_number": req.scene_number,
            "characters": scene.characters,
            "turns": [
                {
                    "speaker": t.speaker,
                    "text": t.text[:100],
                    "duration_ms": t.estimated_duration_ms,
                    "audio_url": audio_urls[i] if i < len(audio_urls) else None,
                }
                for i, t in enumerate(scene.turns)
            ],
            "reference_audio": reference_url,
            "backing_audio": backing_url,
            "total_turns": len(scene.turns),
            "total_duration_ms": sum(t.estimated_duration_ms for t in scene.turns),
            "tts_available": tts_available,
            "user_character": req.user_character,
            "narration": req.narration,
            "voice_preferences": req.voice_preferences or {},
        }

        if req.scene_number > 0:
            try:
                insert(
                    "table_read_takes",
                    [
                        {
                            "script_id": req.script_id,
                            "scene_number": req.scene_number,
                            "scene_hash": _scene_hash(req.scene_text),
                            "result_json": json.dumps(response),
                        }
                    ],
                )
            except Exception as e:
                logger.warning(f"Failed to persist table read take: {e}", exc_info=True)

        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Table read generation failed: {e}", exc_info=True)
        raise HTTPException(500, f"Table read failed: {e}")


@router.post("/table-read/lookup")
async def lookup_table_read(req: TableReadLookupRequest):
    """Return the most recent take for a scene, with a stale flag if the
    scene text changed since it was generated."""
    get_script_or_404(req.script_id)
    if req.scene_number <= 0:
        return {"found": False, "stale": False, "result": None}
    rows = query(
        "SELECT scene_hash, result_json FROM greenlight.table_read_takes "
        "WHERE script_id = %(sid)s AND scene_number = %(num)s "
        "ORDER BY created_at DESC LIMIT 1",
        {"sid": req.script_id, "num": req.scene_number},
    )
    if not rows:
        return {"found": False, "stale": False, "result": None}
    saved_hash, result_json = rows[0]
    try:
        result = json.loads(result_json)
    except ValueError:
        return {"found": False, "stale": False, "result": None}
    return {
        "found": True,
        "stale": saved_hash != _scene_hash(req.scene_text),
        "result": result,
    }


@router.get("/table-read/voice-casting")
async def saved_voice_casting(script_id: str):
    """Persisted voice preferences {character: voice_key} for a script."""
    return get_voice_preferences(script_id)
