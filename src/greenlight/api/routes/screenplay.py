from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from ...db.client import query
from ...tools.fountain_normalizer import beautify_fountain, lint_fountain
from ..services import script_repo
from ..services.script_repo import (
    apply_branch,
    commit_version,
    create_branch,
    get_active,
    get_raw_fountain,
    get_scenes,
    get_version_meta,
    list_branches,
    list_versions,
    load_script,
    preview_apply,
    revert_version,
    set_active,
    unload_script,
)
from ._helpers import get_script_or_404, read_script_text

router = APIRouter()


class LoadIn(BaseModel):
    author: str = ""
    raw_text: str | None = None


class CommitIn(BaseModel):
    branch_id: str
    base_version_id: str
    message: str = "Edit"
    author: str = ""
    raw_fountain: str | None = None
    scene: dict | None = None


class BranchIn(BaseModel):
    name: str
    from_version_id: str


class RevertIn(BaseModel):
    branch_id: str
    revert_to_version_id: str
    author: str = ""


class ApplyIn(BaseModel):
    source_branch_id: str
    target_branch_id: str
    author: str = ""


class ActiveIn(BaseModel):
    branch_id: str = ""
    version_id: str = ""


class BeautifyIn(BaseModel):
    text: str


def get_current_text(script_id: str) -> str:
    """Prefer active/head version text; fall back to uploaded file."""
    state = get_active()
    if state["script_id"] == script_id and state["version_id"]:
        text = get_raw_fountain(state["version_id"])
        if text is not None:
            return text
    return read_script_text(script_id)


@router.post("/scripts/{script_id}/load")
async def load(script_id: str, body: LoadIn):
    get_script_or_404(script_id)
    text = body.raw_text if body.raw_text else get_current_text(script_id)
    result = load_script(script_id, text, author=body.author)
    return result


@router.post("/scripts/{script_id}/unload")
async def unload(script_id: str):
    unload_script()
    return {"script_id": script_id, "loaded": False}


@router.get("/scripts/{script_id}/repo")
async def repo(script_id: str):
    get_script_or_404(script_id)
    if not script_repo.is_loaded(script_id):
        return {"script_id": script_id, "loaded": False, "branches": [], "versions": []}
    return {
        "script_id": script_id,
        "loaded": True,
        "branches": list_branches(script_id),
        "versions": list_versions(script_id),
        "active": get_active(),
    }


@router.get("/session/active")
async def session_active():
    state = get_active()
    if not state["script_id"]:
        return {"loaded": False}
    title_rows = query(
        "SELECT title FROM greenlight.scripts WHERE id = %(id)s",
        {"id": state["script_id"]},
    )
    return {
        "loaded": True,
        **state,
        "title": title_rows[0][0] if title_rows else "",
        "branches": list_branches(state["script_id"]),
    }


@router.put("/scripts/{script_id}/active")
async def set_session(script_id: str, body: ActiveIn):
    get_script_or_404(script_id)
    set_active(script_id, body.branch_id, body.version_id)
    return {"ok": True}


@router.get("/versions/{version_id}")
async def version_detail(version_id: str):
    meta = get_version_meta(version_id)
    if meta is None:
        raise HTTPException(404, "Version not found")
    return {**meta, "scenes": get_scenes(version_id)}


@router.get("/versions/{version_id}/fountain")
async def version_fountain(version_id: str):
    text = get_raw_fountain(version_id)
    if text is None:
        raise HTTPException(404, "Version not found")
    return PlainTextResponse(text)


@router.post("/scripts/{script_id}/versions")
async def commit(script_id: str, body: CommitIn):
    get_script_or_404(script_id)
    try:
        return commit_version(
            script_id=script_id,
            branch_id=body.branch_id,
            base_version_id=body.base_version_id,
            message=body.message,
            author=body.author,
            raw_fountain=body.raw_fountain,
            scene=body.scene,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/scripts/{script_id}/branches")
async def new_branch(script_id: str, body: BranchIn):
    get_script_or_404(script_id)
    try:
        return create_branch(script_id, body.name, body.from_version_id)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/scripts/{script_id}/revert")
async def revert(script_id: str, body: RevertIn):
    get_script_or_404(script_id)
    try:
        return revert_version(script_id, body.branch_id, body.revert_to_version_id, body.author)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/scripts/{script_id}/apply-branch")
async def apply(script_id: str, body: ApplyIn):
    get_script_or_404(script_id)
    try:
        return apply_branch(script_id, body.source_branch_id, body.target_branch_id, body.author)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/versions/{a}/diff/{b}")
async def diff(a: str, b: str):
    ea, eb = script_repo._version_elements(a), script_repo._version_elements(b)
    if not ea and not eb:
        raise HTTPException(404, "Versions not found")
    return {"a": a, "b": b, "changes": script_repo.diff_elements(ea, eb)}


@router.get("/branches/{source_head}/preview-apply/{target_head}")
async def preview(source_head: str, target_head: str):
    return {
        "source_head": source_head,
        "target_head": target_head,
        "changes": preview_apply(source_head, target_head),
    }


@router.post("/screenplay/beautify")
async def beautify(body: BeautifyIn):
    """Canonical blank-line reflow + lint of Fountain text (stateless)."""
    result = beautify_fountain(body.text)
    return {
        "text": result.fountain,
        "changed": result.changed,
        "confidence": result.confidence,
        "stats": result.stats,
        "lint": lint_fountain(result.fountain),
    }
