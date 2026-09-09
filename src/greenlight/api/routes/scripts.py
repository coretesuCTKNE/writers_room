import hashlib
import io
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from pypdf import PdfReader

from ...config import SCRIPTS_DIR
from ...db.client import insert, query
from ...tools.fdx_to_fountain import FdxError, convert_fdx
from ...tools.fountain_normalizer import NormalizationResult, normalize_source
from ...tools.screenplay_template import TITLE_PAGE_SKELETON
from ..services.script_repo import current_principal
from ._helpers import get_script_or_404
from .screenplay import get_current_text

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_UPLOAD_BYTES = 10 * 1024 * 1024

SUPPORTED_SUFFIXES = {".pdf", ".txt", ".text", ".fountain", ".fnt", ".fdx"}


class NormalizeIn(BaseModel):
    force: bool = True
    author: str = ""


class CreateScreenplayRequest(BaseModel):
    title: str
    author: str = ""
    credit: str = "Written by"
    source: str = ""
    draft_date: str = ""
    contact: str = ""
    genre: str = ""


def _source_path(script_id: str) -> Path:
    return SCRIPTS_DIR / script_id


def _fountain_path(script_id: str) -> Path:
    return SCRIPTS_DIR / f"{script_id}.txt"


def _format_path(script_id: str) -> Path:
    return SCRIPTS_DIR / f"{script_id}.format"


def _suffix_of(filename: str) -> str:
    return Path(filename or "").suffix.lower()


def _ingest_source(suffix: str, content: bytes, *, force: bool = False) -> NormalizationResult:
    """Turn any supported upload into Fountain text + integrity report."""
    if suffix == ".pdf":
        try:
            reader = PdfReader(io.BytesIO(content))
            extracted = "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as e:
            raise HTTPException(422, f"PDF could not be read: {e}") from e
        if not extracted.strip():
            raise HTTPException(
                415,
                "This PDF has no text layer (scanned/image PDF). Export a text-based "
                "PDF or upload the .fountain / .txt source instead.",
            )
        return normalize_source(extracted, force=force)

    text = content.decode("utf-8", errors="replace")
    if suffix == ".fdx":
        try:
            fdx = convert_fdx(text)
        except FdxError as e:
            raise HTTPException(415, str(e)) from e
        return NormalizationResult(
            fountain=fdx.fountain,
            changed=True,
            confidence=fdx.confidence,
            warnings=fdx.warnings,
            stats=fdx.stats,
        )
    return normalize_source(text, force=force)


@router.post("/scripts/upload")
async def upload_script(
    file: UploadFile = File(...),
    title: str = "",
    author: str = "",
    genre: str = "",
):
    hasher = hashlib.sha256()
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_UPLOAD_BYTES:
            raise HTTPException(
                413,
                f"File exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)}MB",
            )
        hasher.update(chunk)
        chunks.append(chunk)
    content = b"".join(chunks)
    file_hash = hasher.hexdigest()

    suffix = _suffix_of(file.filename or "")
    if suffix and suffix not in SUPPORTED_SUFFIXES:
        raise HTTPException(
            415,
            f"Unsupported file type '{suffix}'. Supported: {', '.join(sorted(SUPPORTED_SUFFIXES))}",
        )

    result = _ingest_source(suffix or ".txt", content)
    text = result.fountain

    script_id = str(uuid.uuid4())
    if not title:
        title = file.filename or "Untitled"

    _source_path(script_id).write_bytes(content)
    _fountain_path(script_id).write_text(text, encoding="utf-8")
    _format_path(script_id).write_text(suffix or ".txt", encoding="utf-8")

    insert(
        "scripts",
        [
            {
                "id": script_id,
                "title": title,
                "author": author,
                "genre": genre,
                "hash": file_hash,
                "owner": current_principal(),
            }
        ],
    )

    try:
        from ..services.script_repo import load_script

        loaded = load_script(script_id, text, author=author)
    except Exception as e:
        _source_path(script_id).unlink(missing_ok=True)
        _fountain_path(script_id).unlink(missing_ok=True)
        _format_path(script_id).unlink(missing_ok=True)
        query("DELETE FROM greenlight.scripts WHERE id = %(id)s", {"id": script_id})
        logger.warning(f"load_script failed for {script_id}: {e}", exc_info=True)
        raise HTTPException(422, f"Script could not be loaded: {e}") from e

    return {
        "id": script_id,
        "title": title,
        "hash": file_hash,
        "char_count": len(text),
        "source_format": (suffix or ".txt").lstrip("."),
        "normalized": result.changed,
        "confidence": result.confidence,
        "warnings": result.warnings,
        "stats": result.stats,
        "loaded": loaded,
    }


@router.post("/scripts/{script_id}/normalize")
async def normalize_script(script_id: str, body: NormalizeIn):
    """Re-run source -> Fountain normalization and commit the result as a new version."""
    get_script_or_404(script_id)

    source = _source_path(script_id)
    if not source.exists():
        raise HTTPException(404, "Original source file not found — cannot re-normalize")
    fmt_path = _format_path(script_id)
    suffix = fmt_path.read_text(encoding="utf-8").strip() if fmt_path.exists() else ".txt"

    try:
        result = _ingest_source(suffix, source.read_bytes(), force=body.force)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(422, f"Normalization failed: {e}") from e

    _fountain_path(script_id).write_text(result.fountain, encoding="utf-8")

    from ..services.script_repo import (
        commit_version,
        get_branch_head,
        is_loaded,
        list_branches,
        load_script,
    )

    version_id = ""
    unchanged = False
    if is_loaded(script_id):
        branches = list_branches(script_id)
        main = next((b for b in branches if b["name"] == "main"), None)
        if main is None:
            raise HTTPException(409, "Script has no main branch")
        head = get_branch_head(main["branch_id"])
        commit = commit_version(
            script_id=script_id,
            branch_id=main["branch_id"],
            base_version_id=head,
            message="Auto-format to Fountain",
            author=body.author or "normalizer",
            raw_fountain=result.fountain,
        )
        version_id = commit["version_id"]
        unchanged = bool(commit.get("unchanged"))
    else:
        loaded = load_script(script_id, result.fountain, author=body.author)
        version_id = loaded.get("version_id", "")

    stats = result.stats
    return {
        "script_id": script_id,
        "version_id": version_id,
        "normalized": result.changed,
        "unchanged": unchanged,
        "confidence": result.confidence,
        "warnings": result.warnings,
        "stats": stats,
        "scene_count": stats.get("scenes", 0),
    }


@router.get("/scripts")
async def list_scripts():
    rows = query(
        "SELECT id, title, author, draft, genre, toString(created_at) "
        "FROM greenlight.scripts "
        "WHERE deleted_at = toDateTime(0) AND owner = %(owner)s "
        "ORDER BY created_at DESC",
        {"owner": current_principal()},
    )
    return [
        {
            "id": r[0],
            "title": r[1],
            "author": r[2],
            "draft": r[3],
            "genre": r[4],
            "created_at": r[5],
        }
        for r in rows
    ]


@router.get("/scripts/{script_id}")
async def get_script(script_id: str):
    rows = query(
        "SELECT id, title, author, draft, genre, toString(created_at) "
        "FROM greenlight.scripts "
        "WHERE id = %(id)s AND deleted_at = toDateTime(0) AND owner = %(owner)s",
        {"id": script_id, "owner": current_principal()},
    )
    if not rows:
        raise HTTPException(404, "Script not found")
    r = rows[0]
    return {
        "id": r[0],
        "title": r[1],
        "author": r[2],
        "draft": r[3],
        "genre": r[4],
        "created_at": r[5],
    }


@router.post("/scripts/create")
async def create_screenplay(req: CreateScreenplayRequest):
    title = req.title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="Title is required")

    script_id = str(uuid.uuid4())
    skeleton = TITLE_PAGE_SKELETON(
        title,
        author=req.author,
        credit=req.credit,
        source=req.source,
        draft_date=req.draft_date,
        contact=req.contact,
        genre=req.genre,
    )

    insert(
        "scripts",
        [
            {
                "id": script_id,
                "title": title,
                "author": req.author,
                "genre": req.genre,
                "hash": hashlib.sha256(skeleton.encode()).hexdigest()[:16],
                "owner": current_principal(),
            }
        ],
    )

    filepath = SCRIPTS_DIR / script_id
    filepath.write_text(skeleton, encoding="utf-8")

    loaded = None
    try:
        from ..services.script_repo import _scaffold

        loaded = _scaffold(
            script_id, skeleton, author=req.author, message="Blank screenplay created"
        )
    except Exception as e:
        logger.warning(f"_scaffold failed for {script_id}: {e}", exc_info=True)

    return {
        "id": script_id,
        "title": title,
        "hash": hashlib.sha256(skeleton.encode()).hexdigest()[:16],
        "char_count": len(skeleton),
        "loaded": loaded,
    }


@router.get("/scripts/{script_id}/text")
async def get_script_text(script_id: str):
    get_script_or_404(script_id)
    # Serve the ACTIVE committed version — the upload file on disk is only the
    # original ingest; edits live in script_versions. get_current_text prefers
    # the active session version, falls back to file / root version.
    return PlainTextResponse(get_current_text(script_id))


@router.delete("/scripts/{script_id}")
async def delete_script(script_id: str):
    from ..services.script_repo import delete_script as soft_delete

    if not soft_delete(script_id):
        raise HTTPException(404, "Script not found")

    _fountain_path(script_id).unlink(missing_ok=True)
    _source_path(script_id).unlink(missing_ok=True)
    _format_path(script_id).unlink(missing_ok=True)

    return {"ok": True}
