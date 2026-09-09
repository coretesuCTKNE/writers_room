import io
import logging
from pathlib import Path

from pydub import AudioSegment

from .audio_store import load_audio_bytes
from .fountain_parser import DialogueTurn, calculate_gap_ms

logger = logging.getLogger(__name__)

SILENCE_MIN_MS = 250
SILENCE_MAX_MS = 5000


def _load_or_silence(audio_url: str | None, duration_ms: int = 1000) -> AudioSegment:
    data = load_audio_bytes(audio_url)
    if data:
        try:
            return AudioSegment.from_file(io.BytesIO(data), format="wav")
        except Exception as e:
            logger.warning(f"Failed to load {audio_url}: {e}", exc_info=True)
    return AudioSegment.silent(duration=duration_ms)


def _stitch_turns(
    turns: list[DialogueTurn],
    audio_urls: list[str | None],
    *,
    skip_speaker: str | None = None,
) -> AudioSegment:
    """Combine per-turn audio (or silence) into a single AudioSegment.

    skip_speaker: if set, that speaker's turns become silence (for backing tracks
    where the user records their own line).
    """
    combined = AudioSegment.silent(duration=500)

    for i, (turn, audio_url) in enumerate(zip(turns, audio_urls)):
        if skip_speaker and turn.speaker == skip_speaker:
            combined += AudioSegment.silent(duration=turn.estimated_duration_ms)
        else:
            segment = _load_or_silence(audio_url, turn.estimated_duration_ms)
            combined += segment

        if i < len(turns) - 1:
            gap_ms = calculate_gap_ms(turn)
            combined += AudioSegment.silent(duration=gap_ms)

    combined += AudioSegment.silent(duration=1000)
    return combined


def _export(combined: AudioSegment, output_path: str) -> str:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    combined.export(str(output), format="wav")
    return str(output)


def stitch_table_read(
    turns: list[DialogueTurn],
    audio_urls: list[str | None],
    output_path: str = "generated_audio/table_read.wav",
) -> str:
    combined = _stitch_turns(turns, audio_urls)
    output = _export(combined, output_path)
    logger.info(f"Table read stitched: {len(turns)} turns → {output} ({len(combined)}ms)")
    return output


def stitch_backing_track(
    turns: list[DialogueTurn],
    audio_urls: list[str | None],
    user_character: str,
    output_path: str = "generated_audio/backing_track.wav",
) -> str:
    combined = _stitch_turns(turns, audio_urls, skip_speaker=user_character)
    output = _export(combined, output_path)
    logger.info(f"Backing track stitched: {len(turns)} turns (user={user_character}) → {output}")
    return output
