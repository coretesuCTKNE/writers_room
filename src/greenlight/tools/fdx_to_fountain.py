"""Deterministic Fountain .fdx (XML) -> Fountain text converter.

FDX is structured XML, so no heuristics are needed — Paragraph/@Type maps
directly onto Fountain element markup.
"""

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from ._fountain_common import SCENE_HEADING_RE
from .fountain_normalizer import _is_cue, _stats_from

FDX_DIALOGUE_TYPES = {"character", "parenthetical", "dialogue"}

TITLE_TYPE_KEYS = {
    "title": "Title",
    "credit": "Credit",
    "author(s)": "Authors",
    "authors": "Authors",
    "author": "Authors",
    "draft": "Draft date",
    "date": "Date",
    "contact": "Contact",
    "copyright": "Copyright",
    "source": "Source",
    "notes": "Notes",
}


@dataclass
class FdxResult:
    fountain: str
    confidence: float
    warnings: list[str] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)


class FdxError(ValueError):
    """Raised when the payload is not a Fountain FDX document."""


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child(el: ET.Element | None, name: str) -> ET.Element | None:
    if el is None:
        return None
    for c in el:
        if _local(c.tag) == name:
            return c
    return None


def _children(el: ET.Element | None, name: str) -> list[ET.Element]:
    if el is None:
        return []
    return [c for c in el if _local(c.tag) == name]


def _line_text(el: ET.Element) -> str:
    return "".join(el.itertext()).strip()


def _para_text(para: ET.Element) -> str:
    lines = [_line_text(ln) for ln in _children(para, "Line")]
    joined = " ".join(t for t in lines if t).strip()
    return joined or _line_text(para)


def _heading_markup(text: str) -> str:
    text = text.upper()
    if SCENE_HEADING_RE.match(text):
        return text
    return f".{text}" if not text.startswith(".") else text


def _character_markup(text: str) -> str:
    if text.startswith("@"):
        return text
    return text.upper() if _is_cue(text.upper()) else f"@{text.upper()}"


def convert_fdx(xml_text: str) -> FdxResult:
    """Convert Fountain FDX or Final Draft FDX XML to Fountain text.

    Raises FdxError on non-XML / unknown-schema input.
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        raise FdxError(f"XML parse error: {e}") from e

    if _local(root.tag) == "FinalDraft":
        body = [el for el in root.iter() if _local(el.tag) == "Paragraph"]
        return _assemble(body, [])
    if _local(root.tag) != "FountainScript":
        raise FdxError("Unrecognized FDX schema (root is neither FountainScript nor FinalDraft)")

    title_lines: list[str] = []
    title_page = _child(root, "TitlePage")
    if title_page is not None:
        for para in _children(title_page, "Paragraph"):
            ptype = (para.get("Type") or "").strip().lower()
            text = _para_text(para)
            key = TITLE_TYPE_KEYS.get(ptype)
            if key and text:
                title_lines.append(f"{key}: {text}")

    script = _child(root, "Script")
    if script is None:
        raise FdxError("FDX document has no <Script> body")
    return _assemble(_children(script, "Paragraph"), title_lines)


def _assemble(paras: list[ET.Element], title_lines: list[str]) -> FdxResult:
    warnings: list[str] = []
    blocks: list[list[str]] = []
    dialogue_block: list[str] | None = None

    def flush_dialogue() -> None:
        nonlocal dialogue_block
        if dialogue_block:
            blocks.append(dialogue_block)
        dialogue_block = None

    def emit(block: list[str]) -> None:
        flush_dialogue()
        blocks.append(block)

    if title_lines:
        emit(title_lines)

    for para in paras:
        ptype = (para.get("Type") or "").strip().lower()
        if not ptype:
            type_el = _child(para, "Type")
            if type_el is not None:
                ptype = _line_text(type_el).lower()
                para.remove(type_el)
        text = _para_text(para)
        if not text:
            continue

        if ptype == "boneyard":
            continue
        if ptype in TITLE_TYPE_KEYS and not blocks and not dialogue_block:
            emit([f"{TITLE_TYPE_KEYS[ptype]}: {text}"])
        elif ptype == "scene heading":
            emit([_heading_markup(text)])
        elif ptype in ("transition", "shot"):
            emit([text.upper()])
        elif ptype == "section":
            emit([f"## {text}"])
        elif ptype == "synopsis":
            emit([f"= {text}"])
        elif ptype == "note":
            emit([f"[[{text}]]"])
        elif ptype == "dual dialogue":
            cue, body = "", []
            for sp in _children(para, "Paragraph"):
                stype = (sp.get("Type") or "").strip().lower()
                stext = _para_text(sp)
                if not stext:
                    continue
                if stype == "character":
                    cue = cue or stext.upper()
                else:
                    body.append(stext)
            flush_dialogue()
            blocks.append([f"{cue or '@UNKNOWN'} ^", *body])
            warnings.append("Dual dialogue flattened to sequential turns")
        elif ptype in FDX_DIALOGUE_TYPES:
            head = _character_markup(text) if ptype == "character" else text
            if dialogue_block is None:
                dialogue_block = [head]
            else:
                dialogue_block.append(head)
        else:  # action / general
            flush_dialogue()
            blocks.append(text.split("\n"))

    flush_dialogue()

    fountain = "\n\n".join("\n".join(b) for b in blocks).strip() + "\n"
    stats = _stats_from(fountain)
    if not stats["scenes"]:
        warnings.append("No scene headings found in FDX body")
    return FdxResult(
        fountain=fountain,
        confidence=0.95 if stats["scenes"] else 0.3,
        warnings=warnings,
        stats=stats,
    )
