"""Shared route helpers — eliminate 4x script-existence check + 2x read-text.

Used by coverage, rewrite, screenplay, table_read, and any future script-bound routes.
"""

from fastapi import HTTPException

from ...config import SCRIPTS_DIR
from ...db.client import query
from ..services.script_repo import current_principal


def get_script_or_404(script_id: str) -> dict:
    """Return {'id', 'title'} for a script owned by the current principal, or 404.

    Centralizes the SELECT id, title FROM greenlight.scripts WHERE id = ... pattern
    repeated in coverage, rewrite, and screenplay routes. Filters soft-deleted
    and not-owned scripts — the 404 gate for every script-bound route.
    """
    rows = query(
        "SELECT id, title FROM greenlight.scripts "
        "WHERE id = %(id)s AND deleted_at = toDateTime(0) AND owner = %(owner)s",
        {"id": script_id, "owner": current_principal()},
    )
    if not rows:
        raise HTTPException(404, "Script not found")
    return {"id": rows[0][0], "title": rows[0][1]}


def read_script_text(script_id: str) -> str:
    """Return raw script text. Prefers .txt (PDF extract) over raw upload file.

    Falls back to the root version's raw_fountain when neither disk file
    exists (Cloud Run restarts wipe the ephemeral uploads dir; the version
    repo in ClickHouse is the source of truth).
    """
    txt_path = SCRIPTS_DIR / f"{script_id}.txt"
    raw_path = SCRIPTS_DIR / script_id
    if txt_path.exists():
        return txt_path.read_text(encoding="utf-8", errors="replace")
    if raw_path.exists():
        return raw_path.read_text(encoding="utf-8", errors="replace")
    rows = query(
        "SELECT raw_fountain FROM greenlight.script_versions "
        "WHERE script_id = %(sid)s ORDER BY created_at ASC LIMIT 1",
        {"sid": script_id},
    )
    if rows:
        return rows[0][0]
    raise HTTPException(404, "Script source text not found")
