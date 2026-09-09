"""Version + branch CRUD + commit/revert/apply."""

import uuid

from ....db.client import insert, query
from ....tools.story_stats import document_stats
from .parsing import (
    _content_hash,
    _parse,
    diff_elements,
    get_raw_fountain,
    replace_scene,
)
from .state import persist_scene_stats, record_edit, set_active


def list_branches(script_id: str) -> list[dict]:
    rows = query(
        """
        SELECT branch_id, name, head_version_id, toString(created_at)
        FROM greenlight.script_branches FINAL
        WHERE script_id = %(sid)s
        ORDER BY created_at
        """,
        {"sid": script_id},
    )
    return [
        {"branch_id": r[0], "name": r[1], "head_version_id": r[2], "created_at": r[3]} for r in rows
    ]


def list_versions(script_id: str) -> list[dict]:
    rows = query(
        """
        SELECT version_id, branch_id, parent_version_id, message, author,
               content_hash, length(raw_fountain), toString(created_at)
        FROM greenlight.script_versions FINAL
        WHERE script_id = %(sid)s
        ORDER BY created_at
        """,
        {"sid": script_id},
    )
    return [
        {
            "version_id": r[0],
            "branch_id": r[1],
            "parent_version_id": r[2],
            "message": r[3],
            "author": r[4],
            "content_hash": r[5],
            "size_bytes": r[6],
            "created_at": r[7],
        }
        for r in rows
    ]


def get_version_meta(version_id: str) -> dict | None:
    rows = query(
        """
        SELECT version_id, script_id, branch_id, parent_version_id, message, author,
               content_hash, length(raw_fountain), toString(created_at)
        FROM greenlight.script_versions FINAL
        WHERE version_id = %(vid)s
        """,
        {"vid": version_id},
    )
    if not rows:
        return None
    r = rows[0]
    return {
        "version_id": r[0],
        "script_id": r[1],
        "branch_id": r[2],
        "parent_version_id": r[3],
        "message": r[4],
        "author": r[5],
        "content_hash": r[6],
        "size_bytes": r[7],
        "created_at": r[8],
    }


def get_branch(branch_id: str) -> dict:
    rows = query(
        """
        SELECT branch_id, script_id, name, head_version_id
        FROM greenlight.script_branches
        WHERE branch_id = %(bid)s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        {"bid": branch_id},
    )
    if not rows:
        raise ValueError(f"Branch {branch_id} not found")
    return {
        "branch_id": rows[0][0],
        "script_id": rows[0][1],
        "name": rows[0][2],
        "head_version_id": rows[0][3],
    }


def get_branch_head(branch_id: str) -> str:
    return get_branch(branch_id)["head_version_id"]


def create_branch(script_id: str, name: str, from_version_id: str) -> dict:
    meta = get_version_meta(from_version_id)
    if meta is None or meta["script_id"] != script_id:
        raise ValueError(f"Version {from_version_id} not found on script {script_id}")
    existing = [b["name"] for b in list_branches(script_id)]
    if name in existing:
        raise ValueError(f"Branch '{name}' already exists")
    branch_id = str(uuid.uuid4())
    insert(
        "script_branches",
        [
            {
                "branch_id": branch_id,
                "script_id": script_id,
                "name": name,
                "head_version_id": from_version_id,
            }
        ],
    )
    return {"branch_id": branch_id, "name": name, "head_version_id": from_version_id}


def commit_version(
    script_id: str,
    branch_id: str,
    base_version_id: str,
    message: str,
    author: str,
    raw_fountain: str | None = None,
    scene: dict | None = None,
) -> dict:
    """Append an immutable new snapshot and move the branch head.

    Provide either the full raw_fountain text, or scene={number, text} to have
    the server splice a single scene into the base document.
    """
    base_text = get_raw_fountain(base_version_id)
    if base_text is None:
        raise ValueError(f"Base version {base_version_id} not found")

    if scene is not None:
        try:
            new_text = replace_scene(base_text, int(scene["number"]), str(scene.get("text", "")))
        except ValueError:
            new_text = base_text.rstrip() + "\n\n" + str(scene.get("text", "")).strip() + "\n"
    elif raw_fountain is not None:
        new_text = raw_fountain
    else:
        raise ValueError("Provide raw_fountain or scene")

    new_hash = _content_hash(new_text)
    if new_hash == _content_hash(base_text):
        return {"version_id": base_version_id, "unchanged": True}

    elements = _parse(new_text)
    doc = document_stats(elements)
    version_id = str(uuid.uuid4())
    insert(
        "script_versions",
        [
            {
                "version_id": version_id,
                "script_id": script_id,
                "branch_id": branch_id,
                "parent_version_id": base_version_id,
                "message": message or "Edit",
                "author": author,
                "raw_fountain": new_text,
                "content_hash": new_hash,
                "word_count": doc["words"],
                "page_count": doc["pages"],
            }
        ],
    )

    branch = get_branch(branch_id)
    insert(
        "script_branches",
        [
            {
                "branch_id": branch_id,
                "script_id": script_id,
                "name": branch["name"],
                "head_version_id": version_id,
            }
        ],
    )
    set_active(script_id, branch_id, version_id)

    persist_scene_stats(script_id, version_id, elements)

    diff = diff_elements(_parse(base_text), elements)
    record_edit(script_id, base_version_id, version_id, source="manual", diff_summary=diff)

    return {
        "version_id": version_id,
        "parent_version_id": base_version_id,
        "branch_id": branch_id,
        "content_hash": new_hash,
        "changed": len(diff),
    }


def revert_version(script_id: str, branch_id: str, revert_to: str, author: str) -> dict:
    head = get_branch_head(branch_id)
    if not head:
        raise ValueError(f"Branch {branch_id} has no head")
    target_text = get_raw_fountain(revert_to)
    if target_text is None:
        raise ValueError(f"Version {revert_to} not found")
    return commit_version(
        script_id=script_id,
        branch_id=branch_id,
        base_version_id=head,
        message=f"Revert to {revert_to[:8]}",
        author=author,
        raw_fountain=target_text,
    )


def apply_branch(script_id: str, source_branch_id: str, target_branch_id: str, author: str) -> dict:
    """Apply source branch content as one new commit on target (no merge)."""
    source_head = get_branch_head(source_branch_id)
    target_head = get_branch_head(target_branch_id)
    source_text = get_raw_fountain(source_head)
    if source_text is None:
        raise ValueError("Source branch has no versions")
    return commit_version(
        script_id=script_id,
        branch_id=target_branch_id,
        base_version_id=target_head,
        message=f"Apply branch {source_branch_id[:8]}",
        author=author,
        raw_fountain=source_text,
    )


def diff_versions(a_version_id: str, b_version_id: str) -> list[dict]:
    from .parsing import _version_elements

    return diff_elements(_version_elements(a_version_id), _version_elements(b_version_id))


def preview_apply(source_head: str, target_head: str) -> list[dict]:
    return diff_versions(target_head, source_head)
