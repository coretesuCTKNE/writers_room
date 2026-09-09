import logging

from fastapi import APIRouter, HTTPException

from ...config import AUDIO_DIR
from ...db.client import command, query
from ...tools.audio_store import delete_audio, is_cloud_url
from ..services.script_repo import current_principal

logger = logging.getLogger(__name__)

router = APIRouter()

PURPOSES = {"pitch_reel", "table_read", "scratch_track", "backing_track"}


@router.get("/assets")
async def list_assets():
    """Assets for the current principal's scripts only (owner-scoped)."""
    rows = query(
        """
        SELECT a.asset_id, a.script_id, a.scene_id, a.purpose, a.audio_url,
               toString(a.created_at)
        FROM greenlight.generated_audio_assets AS a
        INNER JOIN greenlight.scripts AS s ON s.id = a.script_id
        WHERE s.owner = %(owner)s AND s.deleted_at = toDateTime(0)
        ORDER BY a.created_at DESC
        LIMIT 200
        """,
        {"owner": current_principal()},
    )
    assets = []
    for asset_id, script_id, scene_id, purpose, audio_url, created_at in rows:
        filename = audio_url.split("/")[-1]
        if is_cloud_url(audio_url):
            # Bucket objects have no local stat; presence is implied by the URL
            file_exists, size = True, 0
        else:
            filepath = AUDIO_DIR / filename
            file_exists = filepath.exists()
            size = filepath.stat().st_size if file_exists else 0
        assets.append(
            {
                "asset_id": asset_id,
                "script_id": script_id,
                "scene_id": scene_id,
                "purpose": purpose,
                "audio_url": audio_url,
                "filename": filename,
                "file_exists": file_exists,
                "size_bytes": size,
                "created_at": created_at,
            }
        )
    return assets


@router.delete("/assets/{asset_id}")
async def delete_asset(asset_id: str):
    rows = query(
        """
        SELECT a.asset_id, a.audio_url
        FROM greenlight.generated_audio_assets AS a
        INNER JOIN greenlight.scripts AS s ON s.id = a.script_id
        WHERE a.asset_id = %(aid)s AND s.owner = %(owner)s AND s.deleted_at = toDateTime(0)
        """,
        {"aid": asset_id, "owner": current_principal()},
    )
    if not rows:
        raise HTTPException(404, "Asset not found")

    audio_url = rows[0][1]
    removed = delete_audio(audio_url)

    command(
        "DELETE FROM greenlight.generated_audio_assets WHERE asset_id = %(aid)s",
        {"aid": asset_id},
    )

    return {"deleted": asset_id, "file_removed": removed}
