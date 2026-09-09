import asyncio
import io
import logging
import wave

from google.genai import types

from ..config import AUDIO_DIR, settings
from ..db.client import get_ch_client, query
from ..utils.genai_client import get_genai_client, has_vertex_credentials, is_llm_available
from .audio_store import store_audio
from .fountain_parser import DialogueTurn
from .voice_casting import VoiceAssignment, turn_hash

logger = logging.getLogger(__name__)

SEMAPHORE_LIMIT = 5
TTS_MODEL = settings.tts_model
SAMPLE_RATE = 24000

TAG_STYLE_PROMPTS = {
    "[whispers]": "in a soft whisper",
    "[shouting]": "shouting loudly",
    "[angry]": "in an angry, furious tone",
    "[sarcastic]": "sarcastically",
    "[tired]": "tired and out of breath",
    "[panicked]": "in a panicked, terrified voice",
    "[laughs]": "with laughter in the voice",
    "[crying]": "while sobbing",
    "[very fast]": "very quickly",
    "[slow]": "slowly",
}


def _get_client():
    return get_genai_client(location=settings.tts_cloud_location, key="tts")


def is_tts_available() -> bool:
    """Cheap availability probe: Vertex credentials OR API key configured."""
    return is_llm_available() and (bool(settings.google_api_key) or has_vertex_credentials())


def build_style_prompt(text: str, tags: list[str]) -> str:
    styles = [TAG_STYLE_PROMPTS[t] for t in tags if t in TAG_STYLE_PROMPTS]
    if not styles:
        return text
    joined = ", ".join(styles)
    return f"Say {joined}: {text}"


def _pcm_to_wav(pcm_data: bytes) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm_data)
    return buf.getvalue()


async def generate_turn_audio(
    turn: DialogueTurn,
    voice: VoiceAssignment,
    semaphore: asyncio.Semaphore,
) -> str | None:
    tags = turn.parenthetical.tags if turn.parenthetical else []
    th = turn_hash(turn.text, voice.voice_id, tags)

    cached = query(
        "SELECT audio_url FROM greenlight.tts_turn_cache "
        "WHERE turn_hash = %(h)s AND voice_id = %(v)s",
        {"h": th, "v": voice.voice_id},
    )
    if cached:
        logger.debug(f"Cache hit for {turn.speaker}: {cached[0][0]}")
        return cached[0][0]

    async with semaphore:
        try:
            filename = f"{th}_{voice.voice_id}.wav"
            filepath = AUDIO_DIR / filename

            contents = build_style_prompt(turn.text, tags)
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    _get_client().models.generate_content,
                    model=TTS_MODEL,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        response_modalities=["AUDIO"],
                        speech_config=types.SpeechConfig(
                            voice_config=types.VoiceConfig(
                                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                    voice_name=voice.voice_id
                                )
                            )
                        ),
                    ),
                ),
                timeout=settings.tts_call_timeout_seconds or None,
            )

            part = (
                response.candidates[0].content.parts[0]
                if response.candidates and response.candidates[0].content.parts
                else None
            )
            pcm = part.inline_data.data if part and part.inline_data else None
            if not pcm:
                logger.error(f"TTS returned no audio for {turn.speaker}")
                return None

            filepath.write_bytes(_pcm_to_wav(pcm))
            audio_url = store_audio(filepath)

            try:
                get_ch_client().command(
                    "INSERT INTO greenlight.tts_turn_cache "
                    "(turn_hash, voice_id, audio_url) "
                    "VALUES (%(h)s, %(v)s, %(u)s)",
                    {"h": th, "v": voice.voice_id, "u": audio_url},
                )
            except Exception as e:
                logger.warning(f"Failed to cache turn: {e}", exc_info=True)

            logger.info(
                f"Generated audio for {turn.speaker}: {audio_url} ({filepath.stat().st_size} bytes)"
            )
            return audio_url

        except Exception as e:
            logger.error(f"TTS failed for {turn.speaker}: {e}")
            return None


async def generate_table_read(
    turns: list[DialogueTurn],
    voices: dict[str, VoiceAssignment],
) -> list[str | None]:
    semaphore = asyncio.Semaphore(SEMAPHORE_LIMIT)
    tasks: list[asyncio.Task] = []
    for turn in turns:
        voice = voices.get(turn.speaker)
        if not voice:
            logger.warning(f"No voice for {turn.speaker}, skipping")

            async def _none() -> None:
                return None

            tasks.append(asyncio.create_task(_none()))
            continue
        tasks.append(asyncio.create_task(generate_turn_audio(turn, voice, semaphore)))

    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [r if isinstance(r, str) else None for r in results]
