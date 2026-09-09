"""Pure parse operations: fountain -> elements -> scenes/diffs."""

import hashlib
from dataclasses import asdict

from ....db.client import query
from ....tools.fountain_document import (
    FORCED_SCENE_HEADING_RE,
    SCENE_HEADING_RE,
    SCENE_NUMBER_TAIL_RE,
    ScriptElement,
    parse_document,
)
from ....utils.lru_cache import LRUCache

_PARSE_CACHE: LRUCache[str, list[ScriptElement]] = LRUCache(maxsize=256)


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _parse(text: str) -> list[ScriptElement]:
    return _PARSE_CACHE.get_or_compute(text, lambda: parse_document(text))


def get_raw_fountain(version_id: str) -> str | None:
    rows = query(
        "SELECT raw_fountain FROM greenlight.script_versions WHERE version_id = %(vid)s LIMIT 1",
        {"vid": version_id},
    )
    return rows[0][0] if rows else None


def _scene_line_ranges(lines: list[str]) -> list[tuple[int, int]]:
    """(start_line, end_line_exclusive) per scene heading, in document order.

    Scene k's range spans its heading line through the line before the next
    heading (or EOF) — internal blank lines included, so slicing is lossless.
    """
    ranges: list[tuple[int, int]] = []
    start: int | None = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if SCENE_HEADING_RE.match(stripped) or FORCED_SCENE_HEADING_RE.match(stripped):
            if start is not None:
                ranges.append((start, i))
            start = i
    if start is not None:
        ranges.append((start, len(lines)))
    return ranges


def get_scenes(version_id: str) -> list[dict]:
    """Parsed-on-demand scene list with full scene text.

    Scene text is sliced from the raw fountain line-for-line (not rebuilt from
    parsed elements), so user whitespace — blank lines between dialogue
    exchanges, action beats, etc. — survives the commit/reload round trip.
    """
    raw = get_raw_fountain(version_id)
    if raw is None:
        return []
    elements = _parse(raw)
    lines = raw.split("\n")
    ranges = _scene_line_ranges(lines)
    headings = [el for el in elements if el.type == "scene_heading"]

    scenes: list[dict] = []
    seen: set[int] = set()
    for idx, el in enumerate(headings):
        if el.scene_number in seen:
            continue
        seen.add(el.scene_number)
        display = SCENE_NUMBER_TAIL_RE.sub("", el.text).strip()
        if idx < len(ranges):
            start, end = ranges[idx]
            text = "\n".join(lines[start:end]).strip("\n")
        else:
            # heading-count mismatch (e.g. heading consumed by title page) —
            # degrade to element text rather than a wrong slice
            text = el.text
        scenes.append({"num": el.scene_number, "heading": display, "text": text})
    return scenes


def get_scene_text(version_id: str, scene_number: int) -> str | None:
    scenes = get_scenes(version_id)
    for sc in scenes:
        if sc["num"] == scene_number:
            return sc["text"]
    return None


def replace_scene(base_text: str, scene_number: int, new_scene_text: str) -> str:
    """Return base_text with scene N's block replaced by new_scene_text.

    Line-range splice: every scene outside the edited one is kept verbatim
    (no whitespace normalization); the edited scene lands as typed/dictated.
    """
    lines = base_text.split("\n")
    ranges = _scene_line_ranges(lines)
    if scene_number < 1 or scene_number > len(ranges):
        raise ValueError(f"Scene {scene_number} not found")

    start, end = ranges[scene_number - 1]
    prefix = "\n".join(lines[:start]).strip("\n")
    suffix = "\n".join(lines[end:]).strip("\n")
    cleaned = new_scene_text.strip()

    parts = [p for p in (prefix, cleaned, suffix) if p]
    return "\n\n".join(parts)


def _version_elements(version_id: str) -> list[ScriptElement]:
    raw = get_raw_fountain(version_id)
    if raw is None:
        return []
    return _parse(raw)


def diff_elements(a: list[ScriptElement], b: list[ScriptElement]) -> list[dict]:
    """Element-level diff between two ordered element lists."""
    da, db = [asdict(e) for e in a], [asdict(e) for e in b]
    changes: list[dict] = []
    max_len = max(len(da), len(db))
    for i in range(max_len):
        ea = da[i] if i < len(da) else None
        eb = db[i] if i < len(db) else None
        ta = ea["text"] if ea else ""
        tb = eb["text"] if eb else ""
        typea = ea["type"] if ea else ""
        typeb = eb["type"] if eb else ""
        if ea is None:
            changes.append({"ordinal": i, "change": "added", "after_type": typeb, "after": tb})
        elif eb is None:
            changes.append({"ordinal": i, "change": "removed", "before_type": typea, "before": ta})
        elif ta != tb or typea != typeb:
            changes.append(
                {
                    "ordinal": i,
                    "change": "modified",
                    "before_type": typea,
                    "after_type": typeb,
                    "before": ta,
                    "after": tb,
                }
            )
    return changes
