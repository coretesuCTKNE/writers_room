"""One-time backfill: register orphan audio files in generated_audio_assets.

Skips per-turn TTS cache files (tracked in tts_turn_cache) — those are
building blocks, not stand-alone assets. Everything else gets a row with
an inferred purpose from its filename prefix.

Usage:
    uv run python src/greenlight/db/seed/backfill_assets.py [--dry-run]
"""

import sys
import uuid
from pathlib import Path

from greenlight.db.client import get_ch_client, query

AUDIO_DIR = Path("generated_audio")

PREFIX_PURPOSES = {
    "table_read_": "table_read",
    "backing_track_": "backing_track",
}


def main() -> None:
    dry_run = "--dry-run" in sys.argv

    tracked: set[str] = set()
    cache_rows = query(
        "SELECT audio_url FROM greenlight.tts_turn_cache",
    )
    for row in cache_rows:
        tracked.add(Path(row[0]).name)

    existing_rows = query("SELECT audio_url FROM greenlight.generated_audio_assets")
    existing_names = {Path(r[0]).name for r in existing_rows}

    orphans: list[tuple[Path, str]] = []
    for filepath in sorted(AUDIO_DIR.glob("*.wav")):
        if filepath.name in tracked or filepath.name in existing_names:
            continue
        purpose = "scratch_track"
        for prefix, p in PREFIX_PURPOSES.items():
            if filepath.name.startswith(prefix):
                purpose = p
                break
        orphans.append((filepath, purpose))

    if not orphans:
        print("No orphan audio files. Nothing to backfill.")
        return

    print(f"{'[dry-run] ' if dry_run else ''}Found {len(orphans)} orphan file(s):")
    rows: list[dict] = []
    for filepath, purpose in orphans:
        size_kb = filepath.stat().st_size // 1024
        print(f"  {purpose:20s} {filepath.name} ({size_kb} KB)")
        rows.append(
            {
                "asset_id": str(uuid.uuid4()),
                "script_id": "",
                "scene_id": "",
                "purpose": purpose,
                "audio_url": f"/generated_audio/{filepath.name}",
            }
        )

    if dry_run:
        return

    get_ch_client().insert(
        "greenlight.generated_audio_assets",
        [
            [r["asset_id"], r["script_id"], r["scene_id"], r["purpose"], r["audio_url"]]
            for r in rows
        ],
        column_names=["asset_id", "script_id", "scene_id", "purpose", "audio_url"],
    )

    total_rows = query("SELECT count() FROM greenlight.generated_audio_assets")
    print(f"Backfilled {len(rows)} rows. Library total: {total_rows[0][0]}.")


if __name__ == "__main__":
    main()
