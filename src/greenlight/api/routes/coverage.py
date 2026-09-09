import json
import logging
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...db.client import insert, query
from ..services.coverage_service import generate_coverage, is_coverage_available
from ._helpers import get_script_or_404

logger = logging.getLogger(__name__)

router = APIRouter()


class CoverageRequest(BaseModel):
    script_text: str


@router.get("/scripts/{script_id}/coverage/latest")
async def latest_coverage(script_id: str):
    get_script_or_404(script_id)
    rows = query(
        """
        SELECT coverage_id, title, verdict, logline, synopsis, scores,
               analyst_notes, toString(created_at)
        FROM greenlight.coverage
        LEFT JOIN greenlight.scripts ON scripts.id = coverage.script_id
        WHERE coverage.script_id = %(sid)s
        ORDER BY coverage.created_at DESC
        LIMIT 1
        """,
        {"sid": script_id},
    )
    if not rows:
        return {"found": False}
    r = rows[0]
    try:
        comments = json.loads(r[5]) if r[5] else {}
    except json.JSONDecodeError:
        comments = {}
    return {
        "found": True,
        "coverage_id": r[0],
        "script_id": script_id,
        "title": r[1],
        "verdict": r[2],
        "logline": r[3],
        "synopsis": r[4],
        "comments": comments,
        "analyst_notes": r[6],
        "source": "stored",
        "created_at": r[7],
    }


@router.post("/scripts/{script_id}/coverage")
async def run_coverage(script_id: str, req: CoverageRequest):
    script = get_script_or_404(script_id)
    title = script["title"]

    if len(req.script_text.strip()) < 500:
        raise HTTPException(
            422,
            "Screenplay too short for meaningful coverage (minimum ~500 characters)",
        )

    if not is_coverage_available():
        raise HTTPException(
            503,
            "LLM not configured (GOOGLE_API_KEY or GOOGLE_CLOUD_PROJECT missing)",
        )

    try:
        llm_coverage = await generate_coverage(req.script_text)
    except Exception as e:
        logger.error(f"Reader agent coverage failed: {e}", exc_info=True)
        raise HTTPException(502, f"LLM coverage failed: {e}") from e

    verdict = (llm_coverage or {}).get("verdict", "CONSIDER").upper()
    if verdict not in ("PASS", "CONSIDER", "RECOMMEND"):
        verdict = "CONSIDER"

    logline = (llm_coverage or {}).get("logline", "")
    synopsis = (llm_coverage or {}).get("synopsis", "")
    analyst_notes = (llm_coverage or {}).get("analyst_notes", "")

    coverage_id = str(uuid.uuid4())
    insert(
        "coverage",
        [
            {
                "coverage_id": coverage_id,
                "script_id": script_id,
                "verdict": verdict,
                "logline": logline,
                "synopsis": synopsis,
                "scores": json.dumps((llm_coverage or {}).get("comments", {})),
                "analyst_notes": analyst_notes,
            }
        ],
    )

    return {
        "coverage_id": coverage_id,
        "script_id": script_id,
        "title": title,
        "verdict": verdict,
        "logline": logline,
        "synopsis": synopsis,
        "comments": (llm_coverage or {}).get("comments", {}),
        "analyst_notes": analyst_notes,
        "source": "reader_agent",
    }
