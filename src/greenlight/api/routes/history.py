from fastapi import APIRouter

from ...db.client import query
from ..services.script_repo import current_principal

router = APIRouter()


@router.get("/history/edits")
async def list_edits():
    rows = query(
        "SELECT edit_id, scene_id, source, before_md, after_md, toString(created_at) "
        "FROM greenlight.scene_edits "
        "WHERE script_id IN (SELECT id FROM greenlight.scripts "
        "WHERE owner = %(owner)s AND deleted_at = toDateTime(0)) "
        "ORDER BY created_at DESC LIMIT 50",
        {"owner": current_principal()},
    )
    return [
        {
            "edit_id": r[0],
            "scene_id": r[1],
            "source": r[2],
            "before_md": r[3],
            "after_md": r[4],
            "created_at": r[5],
        }
        for r in rows
    ]
