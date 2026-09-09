import re
from dataclasses import dataclass, field

from ._fountain_common import (
    CHARACTER_CUE_MAX_LEN,
    CHARACTER_CUE_RE,
    DUAL_DIALOGUE_PATTERN,
    INTERRUPTION_PATTERN,
    SCENE_HEADING_RE,
)

PARENTHETICAL_TAG_MAP: dict[str, str] = {
    "whispering": "[whispers]",
    "whispers": "[whispers]",
    "quietly": "[whispers]",
    "softly": "[whispers]",
    "muttering": "[whispers]",
    "shouting": "[shouting]",
    "shouts": "[shouting]",
    "yelling": "[shouting]",
    "yells": "[shouting]",
    "screaming": "[shouting]",
    "angry": "[angry]",
    "angrily": "[angry]",
    "furious": "[angry]",
    "sarcastic": "[sarcastic]",
    "sardonically": "[sarcastic]",
    "dry": "[sarcastic]",
    "tired": "[tired]",
    "exhausted": "[tired]",
    "breathless": "[tired]",
    "out of breath": "[tired]",
    "panicked": "[panicked]",
    "terrified": "[panicked]",
    "scared": "[panicked]",
    "laughing": "[laughs]",
    "laughs": "[laughs]",
    "chuckling": "[laughs]",
    "crying": "[crying]",
    "sobbing": "[crying]",
    "fast": "[very fast]",
    "quickly": "[very fast]",
    "slowly": "[slow]",
    "pause": "[pause]",
    "beat": "[pause]",
}

ACTION_LINE_RE = re.compile(r"^[^\s]")

NARRATOR_NAME = "NARRATOR"


@dataclass
class Parenthetical:
    raw: str
    tags: list[str] = field(default_factory=list)


def parse_parenthetical(text: str) -> Parenthetical:
    clean = text.strip().strip("()")
    lower = clean.lower()
    tags = []
    for key, tag in PARENTHETICAL_TAG_MAP.items():
        if key in lower:
            if tag not in tags:
                tags.append(tag)
    if not tags:
        tags.append(f"[{clean}]")
    return Parenthetical(raw=clean, tags=tags)


@dataclass
class DialogueTurn:
    speaker: str
    text: str
    parenthetical: Parenthetical | None = None
    is_interrupted: bool = False
    is_dual_dialogue: bool = False
    post_action_line: str = ""
    post_action_word_count: int = 0
    estimated_duration_ms: int = 0
    is_narration: bool = False


@dataclass
class ParsedScene:
    scene_id: str
    heading: str
    turns: list[DialogueTurn] = field(default_factory=list)
    characters: list[str] = field(default_factory=list)


def parse_scene(text: str, scene_id: str = "", include_narration: bool = False) -> ParsedScene:
    lines = text.splitlines()
    scene = ParsedScene(scene_id=scene_id, heading="")
    current_speaker = None
    current_parenthetical = None
    current_lines: list[str] = []
    is_dual = False

    def flush_turn():
        nonlocal current_speaker, current_parenthetical, current_lines, is_dual
        if current_speaker and current_lines:
            text_content = "\n".join(current_lines).strip()
            interrupted = bool(INTERRUPTION_PATTERN.search(text_content))
            turn = DialogueTurn(
                speaker=current_speaker,
                text=text_content,
                parenthetical=current_parenthetical,
                is_interrupted=interrupted,
                is_dual_dialogue=is_dual,
            )
            scene.turns.append(turn)
            if current_speaker not in scene.characters:
                scene.characters.append(current_speaker)
        current_speaker = None
        current_parenthetical = None
        current_lines = []
        is_dual = False

    def add_narration(raw: str):
        if not raw.strip():
            return
        scene.turns.append(
            DialogueTurn(
                speaker=NARRATOR_NAME,
                text=raw.strip(),
                is_narration=True,
            )
        )
        if NARRATOR_NAME not in scene.characters:
            scene.characters.append(NARRATOR_NAME)

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if SCENE_HEADING_RE.match(stripped):
            flush_turn()
            scene.heading = stripped
            if include_narration:
                add_narration(stripped)
            i += 1
            continue

        if DUAL_DIALOGUE_PATTERN.search(stripped):
            is_dual = True
            i += 1
            continue

        char_match = CHARACTER_CUE_RE.match(stripped)
        if char_match and len(stripped) <= CHARACTER_CUE_MAX_LEN and stripped.isupper():
            flush_turn()
            current_speaker = char_match.group(1).strip()
            i += 1
            continue

        if current_speaker and stripped.startswith("(") and stripped.endswith(")"):
            current_parenthetical = parse_parenthetical(stripped)
            i += 1
            continue

        if current_speaker and stripped:
            current_lines.append(stripped)
            i += 1
            continue

        if current_speaker and not stripped and current_lines:
            action_line = ""
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines):
                next_line = lines[j].strip()
                if not CHARACTER_CUE_RE.match(next_line) or not next_line.isupper():
                    if not SCENE_HEADING_RE.match(next_line):
                        action_line = next_line
            if action_line:
                turn = scene.turns[-1] if scene.turns else None
                if turn and turn.speaker == current_speaker:
                    pass
                flush_turn()
                if scene.turns:
                    scene.turns[-1].post_action_line = action_line
                    scene.turns[-1].post_action_word_count = len(action_line.split())
            else:
                flush_turn()
            i += 1
            continue

        flush_turn()
        if include_narration and stripped:
            add_narration(stripped)
        i += 1

    flush_turn()

    for turn in scene.turns:
        word_count = len(turn.text.split())
        base_ms = word_count * 280
        if turn.parenthetical and "[very fast]" in turn.parenthetical.tags:
            base_ms = int(base_ms * 0.7)
        elif turn.parenthetical and "[slow]" in turn.parenthetical.tags:
            base_ms = int(base_ms * 1.3)
        turn.estimated_duration_ms = max(base_ms, 500)

    return scene


def calculate_gap_ms(turn: DialogueTurn) -> int:
    if turn.is_interrupted or turn.is_dual_dialogue:
        return 50
    if turn.post_action_word_count > 0:
        gap = turn.post_action_word_count * 250
        return min(max(gap, 250), 5000)
    return 250
