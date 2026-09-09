"""Lifecycle, scaffold, and active-session state for scripts."""

import uuid
from contextvars import ContextVar
from datetime import datetime

from ....db.client import command, insert, query
from ....tools.fountain_document import ScriptElement, summarize_scenes
from ....tools.story_stats import compute_scene_stats, document_stats
from .parsing import _content_hash, _parse, get_scenes

# Request-scoped identity. Default "local" = auth off (local dev + tests);
# the auth middleware sets the verified Firebase uid per request/WS session.
principal_var: ContextVar[str] = ContextVar("greenlight_principal", default="local")


def current_principal() -> str:
    return principal_var.get()


def script_exists(script_id: str) -> bool:
    return bool(query("SELECT 1 FROM greenlight.scripts WHERE id = %(id)s", {"id": script_id}))


def is_loaded(script_id: str) -> bool:
    return bool(
        query(
            "SELECT 1 FROM greenlight.script_branches WHERE script_id = %(sid)s LIMIT 1",
            {"sid": script_id},
        )
    )


def _scaffold(script_id: str, raw_text: str, author: str, message: str = "Initial load") -> dict:
    """Create the version repo for a script: main branch + root snapshot.

    Central helper used by both load_script (upload) and create_script (blank).
    """
    branch_id = str(uuid.uuid4())
    version_id = str(uuid.uuid4())
    elements = _parse(raw_text)
    doc = document_stats(elements)

    insert(
        "script_branches",
        [
            {
                "branch_id": branch_id,
                "script_id": script_id,
                "name": "main",
                "head_version_id": version_id,
            }
        ],
    )
    insert(
        "script_versions",
        [
            {
                "version_id": version_id,
                "script_id": script_id,
                "branch_id": branch_id,
                "parent_version_id": "",
                "message": message,
                "author": author,
                "raw_fountain": raw_text,
                "content_hash": _content_hash(raw_text),
                "word_count": doc["words"],
                "page_count": doc["pages"],
            }
        ],
    )

    persist_breakdown(script_id, elements)
    persist_scene_stats(script_id, version_id, elements)
    set_active(script_id, branch_id, version_id)

    return {
        "script_id": script_id,
        "loaded": True,
        "branch_id": branch_id,
        "version_id": version_id,
        "scene_count": len(get_scenes(version_id)),
        "word_count": doc["words"],
        "page_count": doc["pages"],
    }


def load_script(script_id: str, raw_text: str, author: str = "") -> dict:
    """Create the version repo for a script: main branch + root snapshot."""
    if is_loaded(script_id):
        rows = query(
            """
            SELECT branch_id, head_version_id, name FROM greenlight.script_branches FINAL
            WHERE script_id = %(sid)s ORDER BY created_at
            """,
            {"sid": script_id},
        )
        branches = [{"branch_id": r[0], "head_version_id": r[1], "name": r[2]} for r in rows]
        target = next((b for b in branches if b.get("name") == "main"), branches[0])
        head = target["head_version_id"]
        set_active(script_id, target["branch_id"], head)
        return {
            "script_id": script_id,
            "loaded": True,
            "branch_id": target["branch_id"],
            "version_id": head,
            "scene_count": len(get_scenes(head)),
            "already_loaded": True,
        }

    return _scaffold(script_id, raw_text, author, message="Initial load")


def _insert_active_session(script_id: str, branch_id: str, version_id: str) -> None:
    """Append one active_sessions row for the current principal."""
    command(
        "INSERT INTO greenlight.active_sessions "
        "(principal, script_id, branch_id, version_id, updated_at) VALUES "
        "(%(principal)s, %(script_id)s, %(branch_id)s, %(version_id)s, now64(3))",
        {
            "principal": current_principal(),
            "script_id": script_id,
            "branch_id": branch_id,
            "version_id": version_id,
        },
    )


def unload_script() -> None:
    """Clear the active session pointer. Version history is kept (append-only)."""
    _insert_active_session("", "", "")


def delete_script(script_id: str) -> bool:
    """Soft-delete a script, mutation-free.

    Lightweight delete hides the current row immediately, then a replacement
    row with deleted_at = now() is re-inserted. List/read paths filter on
    deleted_at = toDateTime(0), so children (scenes, versions, coverage, ...)
    become unreachable via the 404 gate but stay intact for a future TTL purge.
    Returns False when the script does not exist or is already deleted.
    """
    rows = query(
        "SELECT id, title, author, draft, genre, hash, html_rendered, owner, created_at "
        "FROM greenlight.scripts "
        "WHERE id = %(id)s AND deleted_at = toDateTime(0) AND owner = %(owner)s",
        {"id": script_id, "owner": current_principal()},
    )
    if not rows:
        return False
    rid, title, author, draft, genre, file_hash, html_rendered, owner, created_at = rows[0]
    command("DELETE FROM greenlight.scripts WHERE id = %(id)s", {"id": script_id})
    insert(
        "scripts",
        [
            {
                "id": rid,
                "title": title,
                "author": author,
                "draft": draft,
                "genre": genre,
                "hash": file_hash,
                "html_rendered": html_rendered,
                "owner": owner,
                "deleted_at": datetime.now(),
                "created_at": created_at,
            }
        ],
    )
    return True


def persist_breakdown(script_id: str, elements: list[ScriptElement]) -> None:
    """Populate scenes/characters tables from the initial parse."""
    scenes = summarize_scenes(elements)
    scene_stats = compute_scene_stats(elements)
    if scenes:
        # summarize_scenes and compute_scene_stats both emit one entry per
        # scene_heading element in document order, so they zip 1:1.
        inserts = []
        for sc, st in zip(scenes, scene_stats):
            inserts.append(
                {
                    "script_id": script_id,
                    "scene_id": f"{script_id}:s{sc['ordinal'] + 1}",
                    "heading": sc["heading"],
                    "page": sc["ordinal"] + 1,
                    "cast": sc["characters"],
                    "locations": [],
                    "props": [],
                    "ordinal": sc["ordinal"],
                    "setting": st["setting"],
                    "time_of_day": st["time_of_day"],
                }
            )
        insert("scenes", inserts)
    names: list[str] = []
    for el in elements:
        if el.type == "character" and el.character_name and el.character_name not in names:
            names.append(el.character_name)
    if names:
        insert(
            "characters",
            [
                {
                    "script_id": script_id,
                    "character_id": f"{script_id}:{name.lower().replace(' ', '_')}",
                    "name": name,
                }
                for name in names
            ],
        )


def persist_scene_stats(script_id: str, version_id: str, elements: list[ScriptElement]) -> None:
    """Store per-scene stats for a version. Append-only; backfill handles history."""
    rows = compute_scene_stats(elements)
    if not rows:
        return
    insert(
        "scene_stats",
        [
            {
                "script_id": script_id,
                "version_id": version_id,
                "scene_number": r["scene_number"],
                "heading": r["heading"],
                "setting": r["setting"],
                "time_of_day": r["time_of_day"],
                "dialogue_lines": r["dialogue_lines"],
                "action_lines": r["action_lines"],
                "dialogue_words": r["dialogue_words"],
                "action_words": r["action_words"],
                "characters": r["characters"],
            }
            for r in rows
        ],
    )


def record_edit(
    script_id: str,
    base_version_id: str,
    result_version_id: str,
    source: str,
    diff_summary: list[dict],
) -> None:
    import json

    insert(
        "scene_edits",
        [
            {
                "script_id": script_id,
                "scene_id": "__commit__",
                "source": source,
                "before_md": base_version_id,
                "after_md": result_version_id,
                "diff": json.dumps(diff_summary[:200]),
            }
        ],
    )


def set_active(script_id: str, branch_id: str, version_id: str) -> None:
    """Append a fresh session row; readers take the latest per principal."""
    _insert_active_session(script_id, branch_id, version_id)


def get_active() -> dict:
    # Rows are never collapsed (plain MergeTree): max-updated_at is always
    # present, so a direct argMax-style read is deterministic. ReplacingMergeTree
    # + FINAL was dropped — merge dedup on the shared engine kept arbitrary
    # survivors, silently reverting sessions.
    rows = query(
        """
        SELECT script_id, branch_id, version_id
        FROM greenlight.active_sessions
        WHERE principal = %(p)s
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        {"p": current_principal()},
    )
    if not rows:
        return {"script_id": "", "branch_id": "", "version_id": ""}
    return {"script_id": rows[0][0], "branch_id": rows[0][1], "version_id": rows[0][2]}
