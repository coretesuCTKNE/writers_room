"""Agent work routes: expose each agent's durable output to the UI.

These are deterministic over ClickHouse (no LLM). They let the frontend present
the work the agents produce:
- run history (every agent run persisted in agent_runs)
- bible facts (what the bible agent reads/writes)
- analytics stats + coverage history (what the analytics agent queries)

Input validation mirrors the tool layer so route and tool agree.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ...agents import tools
from ...db.client import query
from ..services.agent_output import list_agent_runs
from ..services.agent_runner import run_agent
from ._helpers import get_script_or_404
from .goals import _goal_out, _latest_version_stats

router = APIRouter()


# ---------------------------------------------------------------------------
# Agent run history
# ---------------------------------------------------------------------------


@router.get("/scripts/{script_id}/agents/runs")
async def agent_run_history(
    script_id: str,
    agent: str = "",
    limit: int = 20,
):
    get_script_or_404(script_id)
    return list_agent_runs(script_id, agent=agent or None, limit=limit)


# ---------------------------------------------------------------------------
# Bible facts (bible agent's working set)
# ---------------------------------------------------------------------------


class BibleFactRequest(BaseModel):
    character_id: str
    category: str
    claim: str
    source_page: int = 0


@router.get("/scripts/{script_id}/bible-facts")
async def list_bible_facts(script_id: str, character_id: str = ""):
    get_script_or_404(script_id)
    return tools.list_bible_facts(script_id, character_id=character_id or None)


@router.post("/scripts/{script_id}/bible-facts")
async def add_bible_fact(script_id: str, req: BibleFactRequest):
    get_script_or_404(script_id)
    result = tools.add_bible_fact(
        script_id,
        req.character_id,
        req.category,
        req.claim,
        req.source_page,
    )
    if "error" in result:
        raise HTTPException(422, result["error"])
    return result


@router.delete("/scripts/{script_id}/bible-facts/{fact_id}")
async def delete_bible_fact(script_id: str, fact_id: str):
    get_script_or_404(script_id)
    return tools.delete_bible_fact(script_id, fact_id)


# ---------------------------------------------------------------------------
# Analytics reads (analytics agent's context)
# ---------------------------------------------------------------------------


@router.get("/scripts/{script_id}/analytics/stats")
async def analytics_stats(script_id: str):
    get_script_or_404(script_id)
    return tools.script_stats(script_id)


@router.get("/scripts/{script_id}/analytics/coverage")
async def analytics_coverage(script_id: str, limit: int = Query(default=5, ge=1, le=20)):
    get_script_or_404(script_id)
    return tools.coverage_history(script_id, limit=limit)


@router.get("/scripts/{script_id}/storyops")
async def story_ops(script_id: str):
    """One-shot Story Ops payload feeding the in-app dashboard page."""
    get_script_or_404(script_id)

    commits = query(
        """
        SELECT toString(created_at), word_count, page_count, message
        FROM greenlight.script_versions
        WHERE script_id = %(sid)s
        ORDER BY created_at ASC
        LIMIT 200
        """,
        {"sid": script_id},
    )
    commit_history = [
        {
            "created_at": r[0],
            "word_count": r[1],
            "page_count": r[2],
            "message": r[3],
        }
        for r in commits
    ]

    latest = _latest_version_stats(script_id)
    scene_rows: list[dict] = []
    if latest["version_id"]:
        rows = query(
            """
            SELECT scene_number, heading, setting, time_of_day,
                   dialogue_words, action_words, characters
            FROM greenlight.scene_stats
            WHERE script_id = %(sid)s AND version_id = %(vid)s
            ORDER BY scene_number
            """,
            {"sid": script_id, "vid": latest["version_id"]},
        )
        scene_rows = [
            {
                "scene_number": r[0],
                "heading": r[1],
                "setting": r[2],
                "time_of_day": r[3],
                "dialogue_words": r[4],
                "action_words": r[5],
                "characters": r[6],
            }
            for r in rows
        ]

    goal_rows = query(
        """
        SELECT goal_id, metric, target, deadline, note, toString(created_at)
        FROM greenlight.writing_goals FINAL
        WHERE script_id = %(sid)s AND active
        ORDER BY created_at
        """,
        {"sid": script_id},
    )
    goals = [_goal_out(r, latest) for r in goal_rows]

    return {
        "script_id": script_id,
        "summary": tools.script_stats(script_id),
        "goals": goals,
        "commit_history": commit_history,
        "scene_stats": scene_rows,
        "coverage_history": tools.coverage_history(script_id, limit=10),
        "agent_runs": [
            {
                "run_id": r["run_id"],
                "agent": r["agent"],
                "status": r["status"],
                "elapsed_s": r["elapsed_s"],
                "created_at": r["created_at"],
            }
            for r in list_agent_runs(script_id, limit=20)
        ],
    }


# ---------------------------------------------------------------------------
# Showrunner (routes to bible / analytics / rewrite)
# ---------------------------------------------------------------------------


class ShowrunnerRequest(BaseModel):
    prompt: str


@router.post("/scripts/{script_id}/showrunner")
async def run_showrunner(script_id: str, req: ShowrunnerRequest):
    script = get_script_or_404(script_id)
    if not req.prompt.strip():
        raise HTTPException(422, "Prompt is required")
    result = await run_agent(
        "showrunner",
        req.prompt,
        script_id=script_id,
    )
    if "error" in result:
        raise HTTPException(500, f"Showrunner failed: {result['error']}")
    return {
        "script_id": script_id,
        "title": script["title"],
        "response": result.get("response", ""),
        "elapsed_s": result.get("elapsed_s", 0),
        "source": "showrunner_agent",
    }


# ---------------------------------------------------------------------------
# Story ops coach (analytics agent w/ Grafana MCP tools)
# ---------------------------------------------------------------------------


class CoachRequest(BaseModel):
    prompt: str


@router.post("/scripts/{script_id}/coach")
async def run_coach(script_id: str, req: CoachRequest):
    script = get_script_or_404(script_id)
    if not req.prompt.strip():
        raise HTTPException(422, "Prompt is required")
    result = await run_agent(
        "analytics",
        req.prompt,
        script_id=script_id,
    )
    if "error" in result:
        raise HTTPException(500, f"Coach failed: {result['error']}")
    return {
        "script_id": script_id,
        "title": script["title"],
        "response": result.get("response", ""),
        "elapsed_s": result.get("elapsed_s", 0),
        "source": "story_ops_coach",
    }
