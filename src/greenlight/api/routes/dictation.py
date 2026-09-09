"""Dictation session REST routes.

POST /scripts/{script_id}/dictation/start — log session start
POST /scripts/{script_id}/dictation/stop  — log session end

The actual dictation audio flows through the WebSocket at /api/ws/dictation.
These routes exist only for session metadata in ClickHouse.
"""

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...config import settings
from ...db.client import command, query
from ._helpers import get_script_or_404

router = APIRouter()


class DictationStartIn(BaseModel):
    scene_number: int = 0
    model: str = ""


class DictationStopIn(BaseModel):
    session_id: str


@router.post("/scripts/{script_id}/dictation/start")
async def dictation_start(script_id: str, body: DictationStartIn):
    """Log a dictation session start."""
    get_script_or_404(script_id)

    sid = str(uuid.uuid4())
    model = body.model or settings.dictation_model

    command(
        "INSERT INTO greenlight.dictation_sessions "
        "(session_id, script_id, scene_number, model) VALUES "
        "(%(sid)s, %(script_id)s, %(scene)s, %(model)s)",
        {"sid": sid, "script_id": script_id, "scene": body.scene_number, "model": model},
    )

    return {"session_id": sid, "script_id": script_id}


@router.post("/scripts/{script_id}/dictation/stop")
async def dictation_stop(script_id: str, body: DictationStopIn):
    get_script_or_404(script_id)
    """Log a dictation session end.

    Mutation-free upsert: re-insert the session row with ended=true. Fresh
    databases use ReplacingMergeTree(ended_at) so the newer row wins; the
    pre-existing local table (plain MergeTree) just accumulates rows — we pick
    the latest row per session_id here instead of relying on FINAL, so both
    engine shapes work.
    """
    rows = query(
        """
        SELECT session_id, script_id, scene_number, model, vocabulary_count,
               created_at, ended
        FROM greenlight.dictation_sessions
        WHERE session_id = %(sid)s AND script_id = %(script_id)s
        ORDER BY created_at DESC
        """,
        {"sid": body.session_id, "script_id": script_id},
    )
    if not rows:
        raise HTTPException(404, "Dictation session not found")

    # Prefer an already-ended row so a repeated stop keeps re-inserting the
    # same terminal state instead of stacking duplicates.
    r = next((row for row in rows if row[6]), rows[0])
    command(
        "INSERT INTO greenlight.dictation_sessions "
        "(session_id, script_id, scene_number, model, vocabulary_count, created_at, "
        "ended_at, ended) VALUES "
        "(%(sid)s, %(script_id)s, %(scene)s, %(model)s, %(vocab)s, %(created)s, "
        "now(), true)",
        {
            "sid": r[0],
            "script_id": r[1],
            "scene": r[2],
            "model": r[3],
            "vocab": r[4],
            "created": r[5],
        },
    )
    return {"session_id": body.session_id, "ended": True}
