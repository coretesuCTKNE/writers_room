"""Writing goals — set + track draft targets (Story Ops, plan 06).

GET    /scripts/{script_id}/goals           list active goals w/ progress
POST   /scripts/{script_id}/goals           create goal {metric, target, deadline?, note?}
DELETE /scripts/{script_id}/goals/{goal_id} retire a goal (mutation-free re-insert)

Progress is computed against the latest version's stats (script_versions
word_count/page_count + scene_stats scene count), so it moves on every commit.
"""

import uuid
from datetime import date

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ...db.client import insert, query
from ._helpers import get_script_or_404

router = APIRouter()

_METRICS = ("words", "pages", "scenes")


class GoalIn(BaseModel):
    metric: str
    target: int = Field(gt=0, le=100_000)
    deadline: date | None = None
    note: str = ""


def _latest_version_stats(script_id: str) -> dict:
    rows = query(
        """
        SELECT version_id, word_count, page_count
        FROM greenlight.script_versions FINAL
        WHERE script_id = %(sid)s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        {"sid": script_id},
    )
    if not rows:
        return {"version_id": "", "words": 0, "pages": 0, "scenes": 0}
    scene_count = query(
        "SELECT count() FROM greenlight.scene_stats "
        "WHERE script_id = %(sid)s AND version_id = %(vid)s",
        {"sid": script_id, "vid": rows[0][0]},
    )[0][0]
    return {
        "version_id": rows[0][0],
        "words": rows[0][1],
        "pages": rows[0][2],
        "scenes": scene_count,
    }


def _goal_out(row: tuple, current: dict) -> dict:
    goal_id, metric, target, deadline, note, created_at = row
    value = current.get(metric, 0)
    pct = round(100.0 * value / target, 1) if target else 0.0
    days_left = (deadline - date.today()).days if deadline else None
    return {
        "goal_id": goal_id,
        "metric": metric,
        "target": target,
        "deadline": str(deadline) if deadline else None,
        "note": note,
        "created_at": created_at,
        "current": value,
        "pct": min(pct, 100.0),
        "remaining": max(target - value, 0),
        "days_left": days_left,
    }


@router.get("/scripts/{script_id}/goals")
async def list_goals(script_id: str):
    get_script_or_404(script_id)
    rows = query(
        """
        SELECT goal_id, metric, target, deadline, note, toString(created_at)
        FROM greenlight.writing_goals FINAL
        WHERE script_id = %(sid)s AND active
        ORDER BY created_at
        """,
        {"sid": script_id},
    )
    current = _latest_version_stats(script_id)
    return [_goal_out(r, current) for r in rows]


@router.post("/scripts/{script_id}/goals")
async def create_goal(script_id: str, body: GoalIn):
    get_script_or_404(script_id)
    if body.metric not in _METRICS:
        raise HTTPException(422, f"metric must be one of {', '.join(_METRICS)}")
    goal_id = str(uuid.uuid4())
    insert(
        "writing_goals",
        [
            {
                "goal_id": goal_id,
                "script_id": script_id,
                "metric": body.metric,
                "target": body.target,
                "deadline": body.deadline or date(1970, 1, 1),
                "note": body.note,
                "active": True,
            }
        ],
    )
    return {"goal_id": goal_id, "created": True}


@router.delete("/scripts/{script_id}/goals/{goal_id}")
async def delete_goal(script_id: str, goal_id: str):
    get_script_or_404(script_id)
    rows = query(
        """
        SELECT goal_id, script_id, metric, target, deadline, note, created_at
        FROM greenlight.writing_goals FINAL
        WHERE goal_id = %(gid)s AND script_id = %(sid)s AND active
        LIMIT 1
        """,
        {"gid": goal_id, "sid": script_id},
    )
    if not rows:
        raise HTTPException(404, "Goal not found")
    r = rows[0]
    insert(
        "writing_goals",
        [
            {
                "goal_id": r[0],
                "script_id": r[1],
                "metric": r[2],
                "target": r[3],
                "deadline": r[4],
                "note": r[5],
                "active": False,
                "created_at": r[6],
            }
        ],
    )
    return {"goal_id": goal_id, "deleted": True}
