import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...proto.coverage_harness import run_coverage
from ...proto.opencode_client import is_healthy

logger = logging.getLogger(__name__)

router = APIRouter()


class ProtoCoverageRequest(BaseModel):
    script_text: str


@router.get("/proto/health")
async def proto_health():
    return {"opencode_healthy": is_healthy()}


@router.post("/proto/coverage")
async def proto_coverage(req: ProtoCoverageRequest):
    if not is_healthy():
        raise HTTPException(
            503, "opencode server not running. Start with: opencode serve --port 4096"
        )

    try:
        result = run_coverage(req.script_text)
        return result
    except Exception as e:
        logger.error(f"Coverage failed: {e}", exc_info=True)
        raise HTTPException(500, f"Coverage generation failed: {e}")
