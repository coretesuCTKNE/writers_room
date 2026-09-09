import re
from dataclasses import dataclass

from ._fountain_common import CHARACTER_CUE_MAX_LEN, CHARACTER_CUE_RE, SCENE_HEADING_RE

FORCED_SCENE_HEADING_RE = re.compile(r"^\.([A-Z].*)$", re.DOTALL)
TRANSITION_RE = re.compile(
    r"^(?:CUT|FADE OUT|FADE TO|DISSOLVE|SMASH CUT|MATCH CUT|WIPE)[A-Z ]*TO:? $|^FADE IN:? ?$|^FADE OUT\.?$",
    re.IGNORECASE,
)
GENERIC_TRANSITION_RE = re.compile(r"^[A-Z0-9 ()',.\-]+ TO:$")
TITLE_KEY_RE = re.compile(r"^([A-Za-z][A-Za-z ]{0,30}?):\s*(.*)$")
SECTION_RE = re.compile(r"^(#{1,6})\s+(.+)$")
SYNOPSIS_RE = re.compile(r"^=\s?(.+)$")
CENTERED_RE = re.compile(r"^>(.+[^<])<$", re.DOTALL)
NOTE_RE = re.compile(r"^\[\[(.*)\]\]$", re.DOTALL)
DUAL_CUE_TAIL_RE = re.compile(r"\s*\^\s*$")
SCENE_NUMBER_TAIL_RE = re.compile(r"\s*(#\d+[A-Za-z]?#)\s*$")

ELEMENT_TYPES = (
    "scene_heading",
    "action",
    "character",
    "parenthetical",
    "dialogue",
    "transition",
    "title_page",
    "note",
    "synopsis",
    "section",
    "centered",
)

DIALOGUE_BLOCK_TYPES = ("character", "parenthetical", "dialogue")


@dataclass
class ScriptElement:
    type: str
    text: str
    scene_number: int = 0
    character_name: str = ""
    ordinal: int = 0


def strip_boneyard(text: str) -> str:
    """Remove /* boneyard */ comment blocks (spec: never rendered)."""
    return re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)


def _clean_cue(stripped: str) -> tuple[str, bool]:
    """Return (display_name, is_dual) from a character cue line."""
    is_dual = stripped.rstrip().endswith("^")
    name = DUAL_CUE_TAIL_RE.sub("", stripped).lstrip("@").strip()
    return name, is_dual


def parse_title_page(lines: list[str]) -> tuple[list[ScriptElement], int]:
    """Parse a leading Title Page key/value block. Returns (elements, lines_consumed)."""
    first_content = 0
    while first_content < len(lines) and not lines[first_content].strip():
        first_content += 1
    if first_content >= len(lines):
        return [], len(lines)

    m = TITLE_KEY_RE.match(lines[first_content].strip())
    known_keys = {
        "title",
        "credit",
        "author",
        "authors",
        "source",
        "notes",
        "draft date",
        "date",
        "contact",
        "contact info",
        "copyright",
    }
    if not m or m.group(1).lower().strip() not in known_keys:
        return [], 0

    elements: list[ScriptElement] = []
    i = first_content
    current_key = ""
    buf: list[str] = []

    def flush() -> None:
        if current_key:
            elements.append(
                ScriptElement(
                    type="title_page",
                    text=f"{current_key}: {' '.join(buf)}".rstrip(),
                    character_name=current_key,
                )
            )

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            # blank inside title page only continues if next non-blank is an
            # indented continuation; otherwise title page ends
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines) and (lines[j].startswith(" ") or lines[j].startswith("\t")):
                flush()
                current_key = ""
                i = j
                continue
            break
        m = TITLE_KEY_RE.match(stripped)
        if m and m.group(1).lower().strip() in known_keys:
            flush()
            current_key = m.group(1).strip()
            buf = [m.group(2).strip()]
        elif current_key:
            buf.append(stripped)
        else:
            break
        i += 1

    flush()
    return elements, i


def parse_document(text: str) -> list[ScriptElement]:
    """Parse Fountain screenplay text into an ordered element list.

    Spec coverage: title page, scene headings (incl. forced '.'), scene numbers,
    transitions (generic + forced '>'), character cues (heuristic + forced '@',
    dual-dialogue '^' tolerated), parentheticals, dialogue, action (default +
    forced '!'), centered '>text<', sections '#', synopses '=', notes '[[]]',
    boneyards '/* */' (dropped).
    Element text is stored verbatim (markup included) for lossless round-trips.
    """
    text = strip_boneyard(text)
    lines = text.splitlines()

    elements: list[ScriptElement] = []
    title_elements, consumed = parse_title_page(lines)
    elements.extend(title_elements)

    scene_number = 0
    mode = "action"  # action | dialogue
    current_character = ""

    def add(el_type: str, line: str, character_name: str = "") -> None:
        nonlocal scene_number
        if el_type == "scene_heading":
            scene_number += 1
        elements.append(
            ScriptElement(
                type=el_type,
                text=line.strip(),
                scene_number=scene_number,
                character_name=character_name,
            )
        )

    i = consumed
    while i < len(lines):
        stripped = lines[i].strip()

        if not stripped:
            mode = "action"
            current_character = ""
            i += 1
            continue

        if stripped == "===" or stripped == ">>>":
            add("transition", stripped)
            i += 1
            continue

        if SECTION_RE.match(stripped):
            add("section", stripped)
            i += 1
            continue

        if SYNOPSIS_RE.match(stripped):
            add("synopsis", stripped)
            i += 1
            continue

        centered = CENTERED_RE.match(stripped)
        if centered:
            add("centered", stripped)
            i += 1
            continue

        note = NOTE_RE.match(stripped)
        if note:
            add("note", stripped, character_name=current_character if mode == "dialogue" else "")
            i += 1
            continue

        if SCENE_HEADING_RE.match(stripped) or FORCED_SCENE_HEADING_RE.match(stripped):
            add("scene_heading", stripped)
            mode = "action"
            current_character = ""
            i += 1
            continue

        if GENERIC_TRANSITION_RE.match(stripped) or stripped.upper() in (
            "FADE IN:",
            "FADE IN",
            "FADE OUT.",
            "FADE OUT",
            "THE END",
        ):
            add("transition", stripped)
            mode = "action"
            current_character = ""
            i += 1
            continue

        # forced transition: "> CUT TO:" (no closing '<')
        if stripped.startswith(">") and not stripped.endswith("<"):
            add("transition", stripped)
            mode = "action"
            current_character = ""
            i += 1
            continue

        # forced action
        if stripped.startswith("!"):
            add("action", stripped)
            i += 1
            continue

        # forced character cue
        if stripped.startswith("@"):
            name, _dual = _clean_cue(stripped)
            next_nonblank = _next_nonblank(lines, i)
            if next_nonblank:
                add("character", stripped, character_name=name)
                current_character = name
                mode = "dialogue"
            else:
                add("action", stripped)
            i += 1
            continue

        # uppercase heuristic cue (must be followed by content)
        is_upper = (
            stripped.isupper()
            and len(stripped) <= CHARACTER_CUE_MAX_LEN
            and CHARACTER_CUE_RE.match(stripped)
            and not SCENE_HEADING_RE.match(stripped)
            and not GENERIC_TRANSITION_RE.match(stripped)
        )
        if is_upper and _next_nonblank(lines, i):
            name, _dual = _clean_cue(stripped)
            add("character", stripped, character_name=name)
            current_character = name
            mode = "dialogue"
            i += 1
            continue

        if mode == "dialogue":
            if stripped.startswith("(") and stripped.endswith(")"):
                add("parenthetical", stripped, character_name=current_character)
            else:
                add("dialogue", stripped, character_name=current_character)
            i += 1
            continue

        add("action", stripped)
        i += 1

    for ordinal, el in enumerate(elements):
        el.ordinal = ordinal

    return elements


def _next_nonblank(lines: list[str], i: int) -> bool:
    for j in range(i + 1, len(lines)):
        if lines[j].strip():
            return True
    return False


def render_document(elements: list[dict]) -> str:
    """Render ordered element dicts back to fountain text.

    Consecutive character/parenthetical/dialogue elements stay in one block
    (no blank lines) so a reparse preserves the speaker association.
    """
    blocks: list[str] = []
    current_block: list[str] = []

    def flush() -> None:
        if current_block:
            blocks.append("\n".join(current_block))
            current_block.clear()

    for el in sorted(elements, key=lambda e: e["ordinal"]):
        if el["type"] in DIALOGUE_BLOCK_TYPES:
            # A new (non-dual) character cue starts its own block; without this,
            # consecutive dialogue exchanges would render glued together.
            if el["type"] == "character" and current_block and not el["text"].endswith("^"):
                flush()
            current_block.append(el["text"])
        else:
            flush()
            blocks.append(el["text"])
    flush()
    return "\n\n".join(blocks)


def summarize_scenes(elements: list[ScriptElement]) -> list[dict]:
    """Group elements into scenes for downstream persistence."""
    scenes: list[dict] = []
    current: dict | None = None
    for el in elements:
        if el.type == "scene_heading":
            display = SCENE_NUMBER_TAIL_RE.sub("", el.text).strip()
            current = {
                "heading": display,
                "ordinal": len(scenes),
                "characters": [],
                "element_count": 0,
            }
            scenes.append(current)
        elif current is not None:
            current["element_count"] += 1
            if (
                el.type == "character"
                and el.character_name
                and el.character_name not in current["characters"]
            ):
                current["characters"].append(el.character_name)
    return scenes
