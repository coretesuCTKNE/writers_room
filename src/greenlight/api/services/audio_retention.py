"""Table-read retention: keep only the newest N takes per principal.

A "take" is a `table_read` asset; its `backing_track` (paired by the shared
filename stamp) is deleted alongside. Removal goes through audio_store so both
local-disk and GCS modes are handled.
"""

import logging
import re

from ...config import settings
from ...db.client import command, query
from ...tools.audio_store import delete_audio
from .script_repo import current_principal

logger = logging.getLogger(__name__)

_STAMP_RE = re.compile(r"^(?:table_read|backing_track)_([0-9a-f]{8})\.wav$")


def _stamp(audio_url: str) -> str | None:
    """Extract the 8-hex take stamp from table_read/backing_track filenames."""
    name = audio_url.rsplit("/", 1)[-1]
    m = _STAMP_RE.match(name)
    return m.group(1) if m else None


def _delete_asset(asset_id: str, audio_url: str) -> None:
    delete_audio(audio_url)
    command(
        "DELETE FROM greenlight.generated_audio_assets WHERE asset_id = %(aid)s",
        {"aid": asset_id},
    )


def prune_table_read_takes() -> int:
    """Delete the principal's oldest takes beyond settings.table_read_take_limit.

    Returns the number of takes removed (paired backing tracks not counted).
    """
    limit = settings.table_read_take_limit
    if limit <= 0:
        return 0

    takes = query(
        """
        SELECT a.asset_id, a.audio_url, a.script_id, a.scene_id
        FROM greenlight.generated_audio_assets AS a
        INNER JOIN greenlight.scripts AS s ON s.id = a.script_id
        WHERE a.purpose = 'table_read' AND s.owner = %(owner)s
              AND s.deleted_at = toDateTime(0)
        ORDER BY a.created_at DESC, a.asset_id DESC
        """,
        {"owner": current_principal()},
    )
    stale = takes[limit:]
    if not stale:
        return 0

    removed = 0
    for asset_id, audio_url, script_id, scene_id in stale:
        backings = query(
            """
            SELECT asset_id, audio_url
            FROM greenlight.generated_audio_assets
            WHERE purpose = 'backing_track' AND script_id = %(sid)s
                  AND scene_id = %(scid)s
            """,
            {"sid": script_id, "scid": scene_id},
        )
        stamp = _stamp(audio_url)
        paired = [
            (aid, url)
            for aid, url in backings
            if (stamp and _stamp(url) == stamp) or (not stamp and not _stamp(url))
        ]
        _delete_asset(asset_id, audio_url)
        for aid, url in paired:
            _delete_asset(aid, url)
        removed += 1

    logger.info(f"Take retention: removed {removed} take(s) beyond limit {limit}")
    return removed
