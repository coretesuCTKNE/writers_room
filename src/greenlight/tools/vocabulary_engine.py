"""Dictation vocabulary builder + command detection engine.

Pure functions — no I/O, no LLM calls.  Imports regex patterns from
``_fountain_common.py`` (single source of truth) and adds dictation-specific
command/compound/deletion patterns used by the Gemini Live relay loop.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ._fountain_common import CHARACTER_CUE_RE, SCENE_HEADING_RE

# ---------------------------------------------------------------------------
# Custom vocabulary for Gemini Live input_audio_transcription.custom_vocabulary
# ---------------------------------------------------------------------------

SCREENPLAY_TERMS: list[str] = [
    # Scene headings
    "INT.",
    "EXT.",
    "INT. OR EXT.",
    "STUDIO.",
    # Transitions
    "CUT TO:",
    "FADE IN:",
    "FADE OUT.",
    "FADE TO BLACK.",
    "DISSOLVE TO:",
    "SMASH CUT TO:",
    "MATCH CUT TO:",
    "JUMP CUT TO:",
    "WIPE TO:",
    "IRIS IN:",
    "IRIS OUT:",
    # Common screenplay terms
    "CONTINUOUS",
    "CONT'D",
    "O.S.",
    "O.C.",
    "V.O.",
    # Character cue markers (when spoken as commands)
    "CHARACTER",
    "DIALOGUE",
    "PARENTHETICAL",
    "ACTION",
    "SCENE HEADING",
    "TRANSITION",
    # Command trigger words
    "NEW SCENE",
    "NEW LINE",
    "NEW PARAGRAPH",
    "SCENE DIRECTION",
    "CUT",
    "FADE",
    # Voice-editing triggers
    "SCRATCH THAT",
    # Writer's note trigger
    "WRITER'S NOTE",
]

# ---------------------------------------------------------------------------
# Common-word stoplist — single-word character names that collide with
# high-frequency English function words, verbs, or nouns.  NOT auto-capped
# in action prose.  Multi-word names always cap; short non-colliding names
# (Bob, Tom, Sam, Dan, Joe, Max, Ray) cap normally.
# ---------------------------------------------------------------------------

FUNCTION_WORD_STOPLIST = frozenset(
    """
    a an the he she it is are was were be been being
    will would can could shall should may might must
    do does did have has had of on in at to for with
    by from you we they i me him her us them and or
    but not so as if then than nor yet
    grant rose chase bill mark jack pat sue rob
    run walk love hope grace faith joy
    """.split()
)

# ---------------------------------------------------------------------------
# Command detection patterns
# ---------------------------------------------------------------------------

COMMANDS = [
    # "new scene interior coffee shop day" → scene heading. SMART mode + vocab
    # biasing may rephrase to "New scene. INT. COFFEE SHOP - NIGHT." — allow
    # punctuation after "scene" and literal INT./EXT. locations.
    (
        r"(?i)^new\s+scene\s*[\.,]?\s*(?:heading\s+)?"
        r"(interior|exterior|int\.?\s*or\s*ext\.?|int\.|ext\.|studio\.?)\s+"
        r"(.+?)(?:\s+(?:at\s+)?"
        r"(morning|afternoon|evening|night|dawn|dusk|day|continuous|early\s+morning|late\s+night|cont'd?))?\s*\.?\s*$",
        "scene_heading",
    ),
    # "action" / "scene direction" → action mode
    (r"(?i)^(?:action|scene\s+direction)\s*\.?\s*$", "action"),
    # "parenthetical beat" / "parenthetical (laughing)" → parenthetical
    (r"(?i)^parenthetical\s+[\(]?([^)]+)[\)]?\s*\.?\s*$", "parenthetical"),
    # "transition fade to black" → transition
    (r"(?i)^transition\s+(.+?)\s*\.?\s*$", "transition"),
    # "new line" → line break
    (r"(?i)^new\s+line\s*\.?\s*$", "new_line"),
    # "new paragraph" / "new block" → paragraph break
    (r"(?i)^new\s+(?:paragraph|block)\s*\.?\s*$", "new_paragraph"),
    # "writer's note check timeline" → Fountain note
    (r"""(?i)^(?:writer'?s?\s+note|note\s+to\s+self)\s+(.+?)\s*\.?\s*$""", "writer_note"),
]

# Compound: "character [is] SALLY [parenthetical laughing] [dialogue I agree]"
# Name bounded to 1–3 tokens: first any case, subsequent MUST start uppercase.
# `(?-i:[A-Z])` case-locks the continuation test inside the `(?i)` head.
COMPOUND_CHARACTER_RE = re.compile(
    r"(?i)^character\s+(?:is\s+)?"
    r"(?P<name>[A-Za-z][\w.'-]*(?:\s+(?-i:[A-Z])[\w.'-]*){0,2})"
    r"(?:(?:,?\s+)parenthetical\s+\(?(?P<beat>[^)]+?)\)?)?"
    r"(?:(?:,?\s+)dialogue\s+(?P<dialogue>.+?))?"
    r"\s*\.?\s*$"
)

# Deletion triggers — must be segment-final
DELETE_SCOPE_MAP: dict[str, str] = {
    "scratch that": "last_segment",
    "scratch it": "last_segment",
    "delete last sentence": "last_sentence",
    "delete last line": "last_line",
    "clear last block": "last_block",
    "delete last block": "last_block",
}

DEL_TAIL_RE = re.compile(
    r"(?i)(?:^|\s+)(scratch\s+that|scratch\s+it|delete\s+last\s+(?:sentence|line)|"
    r"(?:clear|delete)\s+last\s+block)\s*\.?\s*$"
)

SCENE_LOCATION_MAP: dict[str, str] = {
    "interior": "INT.",
    "exterior": "EXT.",
    "int or ext": "INT. OR EXT.",
    "int. or ext.": "INT. OR EXT.",
    "int or ext.": "INT. OR EXT.",
    "studio": "STUDIO.",
}

SCENE_TIME_MAP: dict[str, str] = {
    "morning": "MORNING",
    "afternoon": "AFTERNOON",
    "evening": "EVENING",
    "night": "NIGHT",
    "dawn": "DAWN",
    "dusk": "DUSK",
    "day": "DAY",
    "continuous": "CONTINUOUS",
    "early morning": "EARLY MORNING",
    "late night": "LATE NIGHT",
    "cont'd": "CONT'D",
    "cont": "CONT'D",
}

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class CommandResult:
    """detect_commands() output.

    commands:  structured commands to emit (each {action, value[, scope]})
    dialogue:  leftover prose from a compound character line, emitted as a
               normal final transcript AFTER the commands (frontend inserts in
               dialogue mode — no new action type needed)
    compound:  True when commands+dialogue came from a single compound utterance.
               Frontend pushes ONE UndoEntry before executing all sub-inserts
               (character + parenthetical + dialogue) so ``scratch that`` reverts
               the whole utterance atomically — not per-sub-command.
    """

    commands: list[dict] = field(default_factory=list)
    dialogue: str | None = None
    compound: bool = False


# ---------------------------------------------------------------------------
# Pure functions
# ---------------------------------------------------------------------------


def strip_list_artifacts(text: str) -> str:
    """Remove leading numbered/bullet artifacts Smart mode sometimes adds.

    Known trade-off (documented): spoken dialogue that legitimately STARTS
    with a numbered/bullet token ("1. First rule of fight club") loses that
    prefix.  Acceptable for Fountain block style — writers re-speak or retype
    when the number matters.  Never strips mid-line; only a leading token per
    line.
    """
    lines = []
    for line in text.splitlines():
        line = re.sub(r"^\s*\d+\.\s+", "", line)  # "1. text" → "text"
        line = re.sub(r"^\s*[-*•]\s+", "", line)  # "- text" / "• text" → "text"
        lines.append(line)
    return "\n".join(lines).strip()


def extract_vocabulary(script_text: str) -> tuple[list[str], list[str]]:
    """Extract custom vocabulary + character names from a Fountain screenplay.

    Returns (full_terms, character_names), deduplicated, capped at 100 terms.
    """
    terms: list[str] = list(SCREENPLAY_TERMS)
    character_names: list[str] = []

    for line in script_text.splitlines():
        stripped = line.strip()

        # Scene headings first — CHARACTER_CUE_RE is all-caps and would
        # otherwise swallow headings ("INT. DINER - NIGHT") as character names
        if SCENE_HEADING_RE.match(stripped):
            terms.append(stripped.upper())
            continue

        # Character cues: all-caps line (optionally with parenthetical)
        cue_m = CHARACTER_CUE_RE.match(stripped)
        if cue_m:
            name = cue_m.group(1).strip()
            if name and name.upper() == name and len(name) > 1:
                character_names.append(name)
                terms.append(name)
            continue

    # Deduplicate preserving order, cap at 100
    seen: set[str] = set()
    deduped: list[str] = []
    for t in terms:
        key = t.upper()
        if key not in seen:
            seen.add(key)
            deduped.append(t)
    return deduped[:100], character_names


def rank_characters(script_text: str, character_names: list[str]) -> list[str]:
    """Count dialogue-line frequency per character, return sorted by frequency.

    Characters not already in ``character_names`` (from cues) are ignored.
    Returns list ordered most-frequent-first, capped at
    ``settings.dictation_shortlist_size`` (imported at call time to stay pure).
    """
    from ..config import settings

    # Build a set of known character names (case-insensitive)
    known: dict[str, str] = {}  # upper → original
    for name in character_names:
        known[name.upper()] = name

    # Count lines following a character cue (skip scene headings — the
    # all-caps cue regex matches them too)
    freq: dict[str, int] = {}
    for line in script_text.splitlines():
        stripped = line.strip()
        if SCENE_HEADING_RE.match(stripped):
            continue
        cue_m = CHARACTER_CUE_RE.match(stripped)
        if cue_m:
            name_key = cue_m.group(1).strip().upper()
            if name_key in known:
                freq[name_key] = freq.get(name_key, 0) + 1

    # Sort by frequency descending
    sorted_names = sorted(freq.keys(), key=lambda k: freq[k], reverse=True)
    return [known[k] for k in sorted_names[: settings.dictation_shortlist_size]]


def check_stoplist_collisions(character_names: list[str]) -> list[str]:
    """Return single-word character names that collide with FUNCTION_WORD_STOPLIST."""
    return [
        name
        for name in character_names
        if " " not in name and name.lower() in FUNCTION_WORD_STOPLIST
    ]


def seed_seen_names(text: str, character_names: list[str]) -> set[str]:
    """Names already present (case-insensitive, word-boundary) in ``text`` are
    treated as introduced — first-appearance caps skip them.

    Scope matters: pass the TEXT OF THE SCENE BEING DICTATED, not the whole
    script. Seeding from the whole script marks every known name as seen and
    silently disables first-appearance capitalization entirely.
    """
    seen: set[str] = set()
    for name in character_names:
        if re.search(r"\b" + re.escape(name) + r"\b", text, re.IGNORECASE):
            seen.add(name.upper())
    return seen


def capitalize_first_appearance(
    text: str,
    character_names: list[str],
    already_seen: set[str],
) -> tuple[str, set[str]]:
    """Uppercase first occurrence of each unseen character name in ACTION text.

    Stoplist guard: single-word names in FUNCTION_WORD_STOPLIST are skipped
    (never auto-capped).  Multi-word names always cap.  Short names NOT in
    the stoplist (Bob, Tom, Sam, Dan, Joe, Max, Ray) still cap.

    Returns (text, updated_already_seen_set).
    """
    result = text
    updated = set(already_seen)

    for name in character_names:
        name_upper = name.upper()
        if name_upper in updated:
            continue

        # Stoplist guard: single-word names in the stoplist are skipped
        if " " not in name and name.lower() in FUNCTION_WORD_STOPLIST:
            continue

        # Case-insensitive word-boundary match for first occurrence
        pattern = re.compile(r"\b" + re.escape(name) + r"\b", re.IGNORECASE)
        m = pattern.search(result)
        if m:
            result = result[: m.start()] + name_upper + result[m.end() :]
            updated.add(name_upper)

    return result, updated


def detect_commands(transcript: str) -> CommandResult:
    """Parse one finalized utterance → commands (+ optional dialogue leftover).

    Order: deletion-tail → compound → simple COMMANDS → plain prose.
    """
    text = strip_list_artifacts(transcript.strip())

    # 1) Trailing deletion modifier
    del_m = DEL_TAIL_RE.search(text)
    if del_m:
        scope = DELETE_SCOPE_MAP[del_m.group(1).lower()]
        return CommandResult(commands=[{"action": "delete", "scope": scope, "value": ""}])

    # 2) Compound character line (sole character-matching path)
    m = COMPOUND_CHARACTER_RE.match(text)
    if m:
        commands = []
        name_raw = (m.group("name") or "").strip().rstrip(".,;:!?")
        if name_raw:
            name = re.sub(r"\s{2,}", " ", name_raw).upper()
            commands.append({"action": "character", "value": name})
        if m.group("beat"):
            beat = m.group("beat").strip().lower().rstrip(".,")
            commands.append({"action": "parenthetical", "value": f"({beat})"})
        dialogue = None
        if m.group("dialogue"):
            dialogue = strip_list_artifacts(m.group("dialogue").strip())
        return CommandResult(commands=commands, dialogue=dialogue, compound=True)

    # 3) Simple one-shot commands
    for pattern, action in COMMANDS:
        match = re.match(pattern, text)
        if match:
            if action == "scene_heading":
                loc_raw = match.group(1).lower()
                location = SCENE_LOCATION_MAP.get(loc_raw, loc_raw.upper())
                place = match.group(2).strip().rstrip("-").strip().upper()
                time_raw = match.group(3)
                timeofday = (
                    SCENE_TIME_MAP.get(time_raw.lower(), time_raw.upper()) if time_raw else None
                )
                value = f"{location} {place}" + (f" - {timeofday}" if timeofday else "")
                return CommandResult(commands=[{"action": "scene_heading", "value": value}])
            elif action == "character":
                name = match.group(1).strip().rstrip(".,").upper()
                return CommandResult(commands=[{"action": "character", "value": name}])
            elif action == "parenthetical":
                text_v = match.group(1).strip().lower().rstrip(".,")
                return CommandResult(commands=[{"action": "parenthetical", "value": f"({text_v})"}])
            elif action == "transition":
                name = match.group(1).strip().upper()
                if not name.endswith((".", ":")):
                    name += "."
                return CommandResult(commands=[{"action": "transition", "value": name}])
            elif action == "writer_note":
                note = strip_list_artifacts(match.group(1).strip())
                return CommandResult(
                    commands=[{"action": "writer_note", "value": f"[[Note: {note}]]"}]
                )
            else:
                return CommandResult(commands=[{"action": action, "value": ""}])
            # every branch above returns — single match per utterance

    return CommandResult(commands=[])


def fountain_insert(command: dict) -> str:
    """Return Fountain text for a single dictation command.

    Maps command action → Fountain formatting.  Does NOT handle delete
    (frontend-side only) or action mode switch (caller tracks mode state).
    """
    action = command["action"]
    value = command.get("value", "")

    if action == "scene_heading":
        return f"\n\n{value}\n\n"
    elif action == "character":
        return f"\n\n{value}\n"
    elif action == "parenthetical":
        return f"\n{value}\n"
    elif action == "transition":
        return f"\n\n{value}\n\n"
    elif action == "new_line":
        return "\n"
    elif action == "new_paragraph":
        return "\n\n"
    elif action == "writer_note":
        return value  # inline at cursor
    else:
        return ""
