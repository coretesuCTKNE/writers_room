"""Shared Fountain regex patterns. Single source of truth for scene/character/etc.

Imported by both fountain_parser.py (parse_scene) and fountain_document.py
(parse_document). Kept narrow — only patterns that MUST match across both.
"""

import re

SCENE_HEADING_RE = re.compile(
    r"^(INT\.|EXT\.|INT/EXT\.|I/E\.|EST\.)\s+.+",
    re.IGNORECASE,
)

# Loose variant for classifying raw (non-Fountain) text: tolerates missing dots
# and no space after the prefix, e.g. "INT DOORWAY", "ext.road - night".
LOOSE_SCENE_HEADING_RE = re.compile(
    r"^(INT|EXT|INT/EXT|I/E|EST)[.\s/?-]",
    re.IGNORECASE,
)

CHARACTER_CUE_RE = re.compile(r"^([A-Z][A-Z\s'.\-#\^]*?)(\(.*?\))?\s*$")

# Max length of an all-caps line still treated as a character cue. The scene
# parser and the document parser must classify cues identically — share this
# instead of per-file magic numbers.
CHARACTER_CUE_MAX_LEN = 50

# All-caps standalone transition, e.g. "CUT TO:", "SMASH CUT TO:"
CAPS_TRANSITION_RE = re.compile(r"^[A-Z][A-Z0-9 (),.'\-]*TO:$")

STANDALONE_TRANSITIONS = {"FADE IN:", "FADE IN", "FADE OUT.", "FADE OUT", "THE END"}

INTERRUPTION_PATTERN = re.compile(r"--\s*$")

DUAL_DIALOGUE_PATTERN = re.compile(r"\^\s*$")

PARENTHETICAL_RE = re.compile(r"^\((.+)\)$")

# Scene heading anatomy: INT/EXT prefix and trailing time-of-day token.
SETTING_PREFIX_RE = re.compile(r"^(INT/EXT|I/E|INT|EXT|EST)[.\s/-]", re.IGNORECASE)
TIME_OF_DAY_TOKENS = (
    "CONTINUOUS",
    "CONT",
    "MOMENTS LATER",
    "LATER",
    "DAWN",
    "DUSK",
    "MORNING",
    "AFTERNOON",
    "EVENING",
    "NIGHT",
    "DAY",
)
TIME_OF_DAY_RE = re.compile(
    r"[ \-]+(" + "|".join(TIME_OF_DAY_TOKENS) + r")\s*$",
    re.IGNORECASE,
)


def scene_setting(heading: str) -> str:
    """Normalized INT/EXT prefix from a scene heading ('' if unparseable)."""
    m = SETTING_PREFIX_RE.match(heading.strip())
    return m.group(1).upper().replace(" ", "") if m else ""


def scene_time_of_day(heading: str) -> str:
    """Normalized trailing time-of-day token from a heading ('' if absent)."""
    m = TIME_OF_DAY_RE.search(heading.strip())
    return m.group(1).upper() if m else ""
