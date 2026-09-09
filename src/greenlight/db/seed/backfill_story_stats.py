"""Backfill scene_stats + version word/page counts from raw_fountain.

script_versions.raw_fountain is the source of truth: every version can be
re-parsed and its stats recomputed. Version rows are re-inserted with the new
count columns — script_versions is ReplacingMergeTree keyed on
(script_id, branch_id, created_at, version_id), so the re-inserted row (same
key, newer insertion) wins on FINAL reads. No mutations.

Idempotent: skips work already done. Pass --force to recompute everything
(e.g. after changing the stats formulas).

Usage:
    uv run python src/greenlight/db/seed/backfill_story_stats.py [--force]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from greenlight.api.services.script_repo.state import persist_scene_stats  # noqa: E402
from greenlight.db.client import insert, query  # noqa: E402
from greenlight.tools.fountain_document import parse_document  # noqa: E402
from greenlight.tools.story_stats import document_stats  # noqa: E402


def backfill(force: bool = False) -> None:
    rows = query(
        """
        SELECT version_id, script_id, branch_id, parent_version_id, message, author,
               raw_fountain, content_hash, word_count, page_count, created_at
        FROM greenlight.script_versions FINAL
        ORDER BY created_at
        """
    )
    existing = {r[0] for r in query("SELECT DISTINCT version_id FROM greenlight.scene_stats")}
    print(f"versions: {len(rows)}, already with scene_stats: {len(existing)}")

    scenes_done = counts_done = 0
    for (
        vid,
        script_id,
        branch_id,
        parent,
        message,
        author,
        raw,
        content_hash,
        wc,
        pc,
        created_at,
    ) in rows:
        elements = parse_document(raw)
        doc = document_stats(elements)

        if force or vid not in existing:
            persist_scene_stats(script_id, vid, elements)
            scenes_done += 1

        if force or not (wc and pc):
            insert(
                "script_versions",
                [
                    {
                        "version_id": vid,
                        "script_id": script_id,
                        "branch_id": branch_id,
                        "parent_version_id": parent,
                        "message": message,
                        "author": author,
                        "raw_fountain": raw,
                        "content_hash": content_hash,
                        "word_count": doc["words"],
                        "page_count": doc["pages"],
                        "created_at": created_at,
                    }
                ],
            )
            counts_done += 1

    print(f"scene_stats versions persisted: {scenes_done}")
    print(f"version rows re-inserted with counts: {counts_done}")


if __name__ == "__main__":
    backfill(force="--force" in sys.argv)
