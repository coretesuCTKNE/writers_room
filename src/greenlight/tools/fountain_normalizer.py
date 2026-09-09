"""Heuristic raw-text -> Fountain normalization (deterministic, no LLM).

Classifies lines from pdf text-layer dumps / plain .txt exports into Fountain
elements (scene heading / character cue / parenthetical / dialogue / transition
/ action) and re-emits them as canonical blank-line-separated blocks.

Already-fountain input is detected by parse result and passed through
untouched — only integrity stats/warnings are reported.
"""

import re
from dataclasses import asdict, dataclass, field

from ._fountain_common import (
    CAPS_TRANSITION_RE,
    LOOSE_SCENE_HEADING_RE,
    SCENE_HEADING_RE,
    STANDALONE_TRANSITIONS,
)
from .fountain_document import parse_document, render_document

# PDF page furniture: standalone page numbers ("12", "12.") — dropped.
PAGE_NOISE_RE = re.compile(r"^\d{1,3}\.?$")

# Title page keys recognized at the top of a document.
TITLE_LINE_RE = re.compile(
    r"^(TITLE|CREDIT|AUTHORS?|SOURCE|NOTES?|DRAFT DATE|DATE|CONTACT INFO|CONTACT|COPYRIGHT)"
    r"\s*:\s*(.*)$",
    re.IGNORECASE,
)
WRITTEN_BY_RE = re.compile(r"^(?:WRITTEN BY|BY)\s*:?\s*(.+)$", re.IGNORECASE)

# Cue with a paren extension: "JOHN (V.O.)", "SARAH (O.S.)", "DAVE (CONT'D)"
CUE_EXT_RE = re.compile(r"^(?P<name>[A-Z][A-Z0-9 .'\-&]*?)\s*\((?P<ext>[A-Z .'\-]+)\)\s*$")
CUE_PLAIN_RE = re.compile(r"^[A-Z][A-Z0-9 .'\-&]*$")

FORCED_PREFIXES = (".", "@", "!", ">", "#", "=", "[[")

# Dialogue runs end at third-person physical-action lines ("They kiss again.",
# "She turns to the window.") — the classic action-after-dialogue with no blank.
_ACTION_VERBS = (
    "kiss|kisses|kissing|nod|nods|nodded|smile|smiles|smiled|laugh|laughs|laughed|"
    "stare|stares|stared|turn|turns|turned|walk|walks|walked|leave|leaves|left|"
    "stand|stands|stood|sit|sits|sat|look|looks|looked|reach|reaches|reached|"
    "grab|grabs|grabbed|hug|hugs|hugged|pause|pauses|paused|react|reacts|reacted|"
    "sigh|sighs|sighed|gulp|gulps|gulped|cringe|cringes|cringed|glance|glances|"
    "glanced|cross|crosses|crossed|lean|leans|leaned|rise|rises|rose|fall|falls|"
    "fell|break|breaks|broke|erupt|erupts|erupted|exchange|exchanges|exchanged|"
    "share|shares|shared|grip|grips|gripped|touch|touches|touched|exit|exits|"
    "exited|enter|enters|entered|pull|pulls|pulled|push|pushes|pushed|chuckle|"
    "chuckles|chuckled|gasp|gasps|gasped|whisper|whispers|whispered|shout|shouts|"
    "shouted|stagger|staggers|staggered|lunge|lunges|lunged|freeze|freezes|"
    "frozen|beat"
)
DIALOGUE_EXIT_RE = re.compile(rf"^(He|She|They|It|Both|Everyone)\s+(?:{_ACTION_VERBS})\b.*[.!]$")
_KNOWN_NAME_ACTION_RE = re.compile(rf"^(?:{_ACTION_VERBS})\w*\b")

# PDF extraction artifacts: footnote stars, soft hyphens, nbsp, broken ligatures.
_TRAILING_STAR_RE = re.compile(r"[ \t]*\*+[ \t]*$")
_LONE_STAR_RE = re.compile(r"^\*+$")
_TILDE_DASH_RE = re.compile(r"\s*~\s*-\s*")


def _sanitize_text(raw: str) -> str:
    """Strip PDF text-layer junk so element detection sees clean lines."""
    t = raw.replace("\u00a0", " ").replace("\u00ad", "").replace("\ufeff", "")
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    t = _TILDE_DASH_RE.sub(" -- ", t)
    out = []
    for line in t.split("\n"):
        if _LONE_STAR_RE.match(line.strip()):
            continue
        out.append(_TRAILING_STAR_RE.sub("", line.rstrip()))
    return "\n".join(out)


_HEADING_PREFIX_RE = re.compile(r"^(INT/EXT|INT|EXT|I/E|EST)([.\s/-]*)(.*)$", re.IGNORECASE)


@dataclass
class NormalizationResult:
    fountain: str
    changed: bool
    confidence: float
    warnings: list[str] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)


def _canonical_heading(s: str) -> str:
    """Rewrite a loose heading to a form SCENE_HEADING_RE will match."""
    m = _HEADING_PREFIX_RE.match(s)
    if not m:
        return s
    prefix, rest = m.group(1).upper(), m.group(3).strip()
    if prefix == "INT/EXT":
        prefix = "INT./EXT."
    elif prefix in ("I/E", "EST"):
        prefix = f"{prefix}."
    else:
        prefix = f"{prefix}."
    return f"{prefix} {rest}".strip() if rest else prefix


def _is_heading(s: str) -> bool:
    return bool(LOOSE_SCENE_HEADING_RE.match(s) or SCENE_HEADING_RE.match(s))


def _is_transition(s: str) -> bool:
    return bool(CAPS_TRANSITION_RE.match(s)) or s.upper() in STANDALONE_TRANSITIONS


def _is_cue(s: str) -> bool:
    """ALL-CAPS standalone name (optionally with paren extension), not heading-ish."""
    if not s or len(s) > 35 or s.endswith((".", "!", "?", ",")):
        return False
    m = CUE_EXT_RE.match(s)
    if m:
        name = m.group("name").strip()
    elif CUE_PLAIN_RE.match(s):
        name = s
    else:
        return False
    if not any(c.isalpha() for c in name):
        return False
    if _is_heading(name) or name.upper().endswith(" TO"):
        return False
    if len(name.split()) > 4:
        return False
    return True


def _cue_name(s: str) -> str:
    """Display name of a cue line (strips paren extension, @ force, ^ dual tail)."""
    m = CUE_EXT_RE.match(s)
    name = m.group("name") if m else s
    return name.lstrip("@").rstrip("^").strip()


def _ends_dialogue(s: str, known_names: set[str]) -> bool:
    """True if a line inside a dialogue block is actually third-person action."""
    if not s or s.startswith('"'):
        return False
    if DIALOGUE_EXIT_RE.match(s):
        return True
    if not s.endswith((".", "!", "?")):
        return False
    upper = s.upper()
    for name in known_names:
        prefix = name.upper() + " "
        if upper.startswith(prefix) and _KNOWN_NAME_ACTION_RE.match(s[len(prefix) :]):
            return True
    return False


def _confidence(scene_headings: int, cues: int, dialogue_lines: int) -> float:
    if scene_headings == 0:
        return 0.15
    conf = 0.6 + min(scene_headings, 5) * 0.06
    if cues:
        conf += 0.1
    if dialogue_lines:
        conf += 0.05
    return round(min(conf, 0.95), 2)


def _stats_from(text: str) -> dict[str, int]:
    elements = parse_document(text)
    counts = {
        "scenes": 0,
        "cues": 0,
        "dialogue_lines": 0,
        "action_blocks": 0,
        "elements": len(elements),
    }
    for el in elements:
        if el.type == "scene_heading":
            counts["scenes"] += 1
        elif el.type == "character":
            counts["cues"] += 1
        elif el.type == "dialogue":
            counts["dialogue_lines"] += 1
        elif el.type == "action":
            counts["action_blocks"] += 1
    return counts


def classify_text(raw: str) -> NormalizationResult:
    """Force-classify arbitrary raw text into Fountain blocks.

    Blank lines in PDF/plain-text dumps are unreliable: some exports put one
    between EVERY visual line. So a blank line only ends a block when the next
    content line looks like a new element; otherwise hard-wrapped lines are
    merged back into the current paragraph / dialogue block.
    """
    lines = raw.splitlines()
    content_widths = sorted(len(x.strip()) for x in lines if x.strip())
    doc_width = content_widths[int(len(content_widths) * 0.9)] if content_widths else 0

    blocks: list[list[str]] = []
    current: list[str] = []
    current_kind = ""
    dropped_noise = 0
    seen_heading = False
    blank_since = False
    cue_names: set[str] = set()

    def flush() -> None:
        nonlocal current, current_kind
        if current:
            blocks.append(current)
        current = []
        current_kind = ""

    def start(kind: str, text: str) -> None:
        nonlocal current_kind
        flush()
        current.append(text)
        current_kind = kind

    i = 0
    while i < len(lines):
        s = lines[i].strip()
        i += 1

        if not s:
            blank_since = True
            continue

        if PAGE_NOISE_RE.match(s):
            dropped_noise += 1
            continue

        gap = blank_since
        blank_since = False

        title_m = None if seen_heading else TITLE_LINE_RE.match(s)
        wb_m = None if seen_heading else WRITTEN_BY_RE.match(s)
        forced = s[0] in FORCED_PREFIXES
        heading = _is_heading(s)
        transition = _is_transition(s)
        cue = _is_cue(s) and any(x.strip() for x in lines[i:])
        if (
            cue
            and current_kind == "action"
            and current
            and len(s.split()) > 1
            and current[-1][-1] not in '.!?:"]'
        ):
            cue = False  # hard-wrapped ALL-CAPS emphasis inside action, not a speaker

        new_element = forced or heading or transition or cue or title_m or wb_m

        if current and not new_element:
            last = current[-1]
            if current_kind == "dialogue":
                if _ends_dialogue(s, cue_names):
                    start("action", s)
                else:
                    current.append(s)
                continue
            if current_kind == "action" and (
                not gap or s[0].islower() or len(last) >= max(15, int(0.8 * doc_width))
            ):
                current.append(s)
                continue
            if current_kind == "title" and not gap:
                current.append(s)
                continue

        if title_m:
            if current_kind == "title":
                current.append(f"{title_m.group(1).title()}: {title_m.group(2)}".rstrip())
            else:
                start("title", f"{title_m.group(1).title()}: {title_m.group(2)}".rstrip())
            continue
        if wb_m:
            if (
                current_kind in ("action", "dialogue")
                and len(current) == 1
                and current[0] == current[0].upper()
                and len(current[0]) <= 40
            ):
                current[0] = f"Title: {current[0]}"
                current.append(f"Authors: {wb_m.group(1)}")
                current_kind = "title"
            else:
                if current_kind == "action":
                    flush()
                current.append(f"Authors: {wb_m.group(1)}")
                current_kind = "title"
            continue

        if forced:
            if s.startswith("@"):
                cue_names.add(_cue_name(s))
                start("dialogue", s)
            else:
                start("forced", s)
            continue

        if heading:
            seen_heading = True
            start("heading", _canonical_heading(s).upper())
            continue

        if transition:
            start("transition", s.upper())
            continue

        if cue:
            cue_names.add(_cue_name(s))
            start("dialogue", s)
            continue

        start("action", s)

    flush()

    fountain = "\n\n".join("\n".join(b) for b in blocks).strip() + "\n"
    stats = _stats_from(fountain)
    warnings: list[str] = []
    if dropped_noise:
        warnings.append(f"Removed {dropped_noise} page-number line(s)")
    if not stats["scenes"]:
        warnings.append("No scene headings found — document may not be a screenplay")
    if stats["cues"] and not stats["dialogue_lines"]:
        warnings.append("Character cues detected but no dialogue lines followed them")
    return NormalizationResult(
        fountain=fountain,
        changed=True,
        confidence=_confidence(stats["scenes"], stats["cues"], stats["dialogue_lines"]),
        warnings=warnings,
        stats=stats,
    )


def lint_fountain(text: str) -> list[dict]:
    """Integrity warnings for already-Fountain text. Line numbers are 1-based."""
    issues: list[dict] = []
    stats = _stats_from(text)
    if not stats["scenes"]:
        issues.append({"line": 1, "severity": "warn", "message": "No scene headings in document"})

    block: list[tuple[int, str]] = []
    cue_names_seen: set[str] = set()

    def check_block() -> None:
        if not block:
            return
        first_line, first = block[0]
        if SCENE_HEADING_RE.match(first) and first != first.upper():
            issues.append(
                {
                    "line": first_line,
                    "severity": "warn",
                    "message": "Scene heading should be ALL CAPS",
                }
            )
        if _is_cue(first) and not _is_transition(first):
            cue_names_seen.add(_cue_name(first))
            if len(block) == 1:
                issues.append(
                    {
                        "line": first_line,
                        "severity": "warn",
                        "message": "Blank line between character cue and dialogue",
                    }
                )
        if re.match(r"^\(.*\)$", first) and len(block) == 1:
            issues.append(
                {
                    "line": first_line,
                    "severity": "warn",
                    "message": "Blank line separates parenthetical from dialogue",
                }
            )
        if first[0].islower() and first[0] not in "#=>![(.@":
            issues.append(
                {
                    "line": first_line,
                    "severity": "warn",
                    "message": "Suspected wrapped paragraph — remove the blank line between blocks",
                }
            )
        for line_no, s in block[1:]:
            if SCENE_HEADING_RE.match(s):
                issues.append(
                    {
                        "line": line_no,
                        "severity": "warn",
                        "message": "Missing blank line before scene heading",
                    }
                )
            elif _is_cue(s):
                cue_names_seen.add(_cue_name(s))
                issues.append(
                    {
                        "line": line_no,
                        "severity": "warn",
                        "message": "Character cue mid-block — add a blank line before it",
                    }
                )
            elif _is_cue(first) and _ends_dialogue(s, cue_names_seen):
                issues.append(
                    {
                        "line": line_no,
                        "severity": "warn",
                        "message": "Action line inside dialogue — add a blank line before it",
                    }
                )

    for n, line in enumerate(text.splitlines(), start=1):
        s = line.strip()
        if not s:
            check_block()
            block = []
            continue
        block.append((n, s))
    check_block()
    return issues


def normalize_source(raw: str, *, force: bool = False) -> NormalizationResult:
    """Normalize uploaded source text to Fountain.

    Unless force=True, text that already parses with >=1 scene heading is
    returned unchanged with lint warnings only.
    """
    if not raw.strip():
        return NormalizationResult(
            fountain="",
            changed=False,
            confidence=0.0,
            warnings=["Document is empty"],
            stats=_stats_from(""),
        )

    cleaned = _sanitize_text(raw)
    stripped_junk = cleaned.strip() != raw.strip()

    if not force:
        base_stats = _stats_from(cleaned)
        if base_stats["scenes"] >= 1:
            issues = lint_fountain(cleaned)
            structural = [i for i in issues if "blank line" in i["message"].lower()]
            if not structural:
                return NormalizationResult(
                    fountain=cleaned if cleaned.endswith("\n") else cleaned + "\n",
                    changed=stripped_junk,
                    confidence=_confidence(
                        base_stats["scenes"], base_stats["cues"], base_stats["dialogue_lines"]
                    ),
                    warnings=[i["message"] for i in issues],
                    stats=base_stats,
                )

    result = classify_text(cleaned)
    if not result.changed or result.fountain.strip() == cleaned.strip():
        result.fountain = cleaned if cleaned.endswith("\n") else cleaned + "\n"
        result.changed = stripped_junk
    return result


def beautify_fountain(text: str) -> NormalizationResult:
    """Canonical blank-line reflow of already-Fountain text (lossless on reparsed)."""
    elements = parse_document(text)
    rendered = (
        render_document(
            [{"type": e.type, "text": e.text, "ordinal": i} for i, e in enumerate(elements)]
        ).strip()
        + "\n"
    )
    stats = _stats_from(rendered)
    return NormalizationResult(
        fountain=rendered,
        changed=rendered != text,
        confidence=_confidence(stats["scenes"], stats["cues"], stats["dialogue_lines"]),
        warnings=[i["message"] for i in lint_fountain(rendered)],
        stats=stats,
    )


def elements_as_dicts(text: str) -> list[dict]:
    """Parsed element dicts (for API responses)."""
    return [asdict(e) for e in parse_document(text)]
