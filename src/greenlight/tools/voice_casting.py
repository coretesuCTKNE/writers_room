import hashlib
import logging
from dataclasses import dataclass

from ..db.client import get_ch_client, query

logger = logging.getLogger(__name__)

GEMINI_VOICES = {
    "puck": {"id": "Puck", "style": "upbeat, witty male", "gender": "Male"},
    "charon": {"id": "Charon", "style": "informative, deep male", "gender": "Male"},
    "fenrir": {"id": "Fenrir", "style": "excitable, intense male", "gender": "Male"},
    "orus": {"id": "Orus", "style": "firm, authoritative male", "gender": "Male"},
    "iapetus": {"id": "Iapetus", "style": "clear, composed male", "gender": "Male"},
    "umbriel": {"id": "Umbriel", "style": "easy-going, calm male", "gender": "Male"},
    "kore": {"id": "Kore", "style": "firm, confident female", "gender": "Female"},
    "leda": {"id": "Leda", "style": "youthful, energetic female", "gender": "Female"},
    "aoede": {"id": "Aoede", "style": "breezy, warm female", "gender": "Female"},
    "zephyr": {"id": "Zephyr", "style": "bright, airy female", "gender": "Female"},
    "gacrux": {"id": "Gacrux", "style": "mature, grounded female", "gender": "Female"},
    "sulafat": {"id": "Sulafat", "style": "warm, welcoming female", "gender": "Female"},
    "vindemiatrix": {
        "id": "Vindemiatrix",
        "style": "gentle, nurturing female",
        "gender": "Female",
    },
}

DEFAULT_VOICES = ["kore", "puck", "charon", "leda", "orus"]

VOICE_ID_TO_KEY = {v["id"]: k for k, v in GEMINI_VOICES.items()}


@dataclass
class VoiceAssignment:
    character_name: str
    voice_id: str
    base_pitch: float = 1.0
    base_speed: float = 1.0


def build_voice_casting(
    characters: list[str],
    script_id: str,
    preferences: dict[str, str] | None = None,
) -> list[VoiceAssignment]:
    assignments = []
    prefs = preferences or {}

    for i, character in enumerate(characters):
        if character in prefs and prefs[character] in GEMINI_VOICES:
            voice_id = GEMINI_VOICES[prefs[character]]["id"]
        else:
            key = DEFAULT_VOICES[i % len(DEFAULT_VOICES)]
            voice_id = GEMINI_VOICES[key]["id"]

        assignment = VoiceAssignment(
            character_name=character,
            voice_id=voice_id,
        )
        assignments.append(assignment)

        try:
            client = get_ch_client()
            client.command(
                "INSERT INTO greenlight.voice_casting "
                "(script_id, character_name, gemini_voice_id, base_pitch, base_speed) "
                "VALUES (%(sid)s, %(name)s, %(vid)s, 1.0, 1.0)",
                {"sid": script_id, "name": character, "vid": voice_id},
            )
        except Exception as e:
            logger.warning(f"Failed to persist voice casting for {character}: {e}", exc_info=True)

    return assignments


def get_voice_casting(script_id: str) -> dict[str, VoiceAssignment]:
    rows = query(
        "SELECT character_name, "
        "argMax(gemini_voice_id, updated_at), "
        "argMax(base_pitch, updated_at), "
        "argMax(base_speed, updated_at) "
        "FROM greenlight.voice_casting WHERE script_id = %(sid)s "
        "GROUP BY character_name",
        {"sid": script_id},
    )
    return {
        r[0]: VoiceAssignment(
            character_name=r[0],
            voice_id=r[1],
            base_pitch=r[2],
            base_speed=r[3],
        )
        for r in rows
    }


def get_voice_preferences(script_id: str) -> dict[str, str]:
    """Saved casting as {character: GEMINI_VOICES key} for UI prefill."""
    saved = get_voice_casting(script_id)
    return {
        name: VOICE_ID_TO_KEY[a.voice_id]
        for name, a in saved.items()
        if a.voice_id in VOICE_ID_TO_KEY
    }


def turn_hash(text: str, voice_id: str, tags: list[str]) -> str:
    content = f"{text}|{voice_id}|{''.join(sorted(tags))}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]
