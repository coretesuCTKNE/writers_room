"""Persistence for agent runs: record + query structured agent outputs.

Every agent run (bible check, analytics, rewrite pass, coverage, etc.) lands in
the agent_runs table so the work is queryable and displayable in the UI, rather
than being a fire-and-forget LLM response.
"""

import json
import logging
import uuid

from ...db.client import insert, query

logger = logging.getLogger(__name__)


def record_agent_run(
    agent: str,
    script_id: str = "",
    scene_id: str = "",
    status: str = "completed",
    prompt: str = "",
    result: dict | list | str | None = None,
    elapsed_s: float = 0.0,
) -> str:
    """Insert an agent run record. Returns the new run_id."""
    run_id = str(uuid.uuid4())
    if isinstance(result, dict | list):
        result_json = json.dumps(result, ensure_ascii=False, default=str)
    elif isinstance(result, str):
        result_json = result
    else:
        result_json = "{}"

    insert(
        "agent_runs",
        [
            {
                "run_id": run_id,
                "agent": agent,
                "script_id": script_id,
                "scene_id": scene_id,
                "status": status,
                "prompt": prompt or "",
                "result_json": result_json,
                "elapsed_s": float(elapsed_s or 0.0),
            }
        ],
    )
    return run_id


def list_agent_runs(script_id: str, agent: str | None = None, limit: int = 50) -> list[dict]:
    """Most recent agent runs for a script, newest first."""
    params: dict = {"sid": script_id, "lim": int(limit)}
    sql = """
        SELECT run_id, agent, script_id, scene_id, status, prompt, result_json,
               elapsed_s, toString(created_at)
        FROM greenlight.agent_runs
        WHERE script_id = %(sid)s
    """
    if agent:
        sql += " AND agent = %(agent)s"
        params["agent"] = agent
    sql += " ORDER BY created_at DESC LIMIT %(lim)s"
    rows = query(sql, params)
    out = []
    for r in rows:
        try:
            result_json = json.loads(r[6]) if r[6] else {}
        except json.JSONDecodeError:
            result_json = r[6] or {}
        out.append(
            {
                "run_id": r[0],
                "agent": r[1],
                "script_id": r[2],
                "scene_id": r[3],
                "status": r[4],
                "prompt": r[5],
                "result": result_json,
                "elapsed_s": r[7],
                "created_at": r[8],
            }
        )
    return out


def latest_agent_run(script_id: str, agent: str) -> dict | None:
    """Most recent run for a specific agent, or None."""
    rows = list_agent_runs(script_id, agent=agent, limit=1)
    return rows[0] if rows else None
