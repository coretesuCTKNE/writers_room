"""Pure story statistics from parsed Fountain elements.

Feeds the Grafana Story Ops dashboard (see dev_plans/06-grafana-story-ops.md):
per-scene dialogue/action split, setting, time of day, characters; and
whole-document counters persisted on script_versions.
"""

from ._fountain_common import scene_setting, scene_time_of_day
from .fountain_document import SCENE_NUMBER_TAIL_RE, ScriptElement

# Industry rule of thumb: one screenplay page is roughly 55 lines.
PAGE_LINES = 55


def _words(text: str) -> int:
    return len(text.split())


def _display_heading(text: str) -> str:
    return SCENE_NUMBER_TAIL_RE.sub("", text).strip()


def compute_scene_stats(elements: list[ScriptElement]) -> list[dict]:
    """Per-scene stats in document order. One entry per scene_heading element."""
    stats: list[dict] = []
    current: dict | None = None
    for el in elements:
        if el.type == "scene_heading":
            if current is not None:
                stats.append(current)
            current = {
                "scene_number": el.scene_number,
                "heading": _display_heading(el.text),
                "setting": scene_setting(el.text),
                "time_of_day": scene_time_of_day(el.text),
                "dialogue_lines": 0,
                "action_lines": 0,
                "dialogue_words": 0,
                "action_words": 0,
                "characters": [],
            }
            continue
        if current is None:
            continue
        if el.type == "dialogue":
            current["dialogue_lines"] += 1
            current["dialogue_words"] += _words(el.text)
        elif el.type == "action":
            current["action_lines"] += 1
            current["action_words"] += _words(el.text)
        elif el.type == "character" and el.character_name:
            if el.character_name not in current["characters"]:
                current["characters"].append(el.character_name)
    if current is not None:
        stats.append(current)
    return stats


def document_stats(elements: list[ScriptElement]) -> dict:
    """Whole-document counters for the version row.

    words counts dialogue + action only — headings, notes, and transitions are
    formatting, not prose. pages is a line-based estimate.
    """
    scenes = compute_scene_stats(elements)
    dialogue_words = sum(s["dialogue_words"] for s in scenes)
    action_words = sum(s["action_words"] for s in scenes)
    non_empty_lines = sum(1 for el in elements if el.text.strip())
    return {
        "scenes": len(scenes),
        "words": dialogue_words + action_words,
        "dialogue_words": dialogue_words,
        "action_words": action_words,
        "pages": max(1, round(non_empty_lines / PAGE_LINES)),
    }
