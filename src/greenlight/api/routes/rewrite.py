"""Rewrite agent route: targeted rewrite passes based on coverage + LT findings."""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..services.agent_runner import run_agent
from ._helpers import get_script_or_404

logger = logging.getLogger(__name__)

router = APIRouter()


class RewriteRequest(BaseModel):
    script_text: str
    instructions: str = ""
    focus: str = ""  # e.g. "dialogue", "pacing", "character"
    scene_id: str = ""


@router.post("/scripts/{script_id}/rewrite")
async def run_rewrite(script_id: str, req: RewriteRequest):
    script = get_script_or_404(script_id)
    title = script["title"]

    prompt = "Rewrite the following screenplay."
    if req.focus:
        prompt += f" Focus on improving: {req.focus}."
    if req.instructions:
        prompt += f" Additional instructions: {req.instructions}"
    prompt += f"\n\nSCREENPLAY:\n{req.script_text[:120_000]}"

    result = await run_agent("rewrite", prompt, script_id=script_id, scene_id=req.scene_id)

    if "error" in result:
        raise HTTPException(500, f"Rewrite agent failed: {result['error']}")

    return {
        "script_id": script_id,
        "title": title,
        "rewrite": result.get("response", ""),
        "elapsed_s": result.get("elapsed_s", 0),
        "source": "rewrite_agent",
    }


@router.post("/scripts/{script_id}/bible-check")
async def run_bible_check(script_id: str, req: RewriteRequest):
    script = get_script_or_404(script_id)
    title = script["title"]

    prompt = "Check the following screenplay for continuity issues against the established bible."
    if req.instructions:
        prompt += f" Focus areas: {req.instructions}"
    prompt += f"\n\nSCREENPLAY:\n{req.script_text[:120_000]}"

    result = await run_agent("bible", prompt, script_id=script_id, scene_id=req.scene_id)

    if "error" in result:
        raise HTTPException(500, f"Bible check failed: {result['error']}")

    return {
        "script_id": script_id,
        "title": title,
        "bible_check": result.get("response", ""),
        "elapsed_s": result.get("elapsed_s", 0),
        "source": "bible_agent",
    }
