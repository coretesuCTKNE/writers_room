"""Seed bible_facts from public-domain fixture characters.

Usage:
    uv run python -m src.greenlight.db.seed.seed_bible            # auto-detect latest script
    uv run python -m src.greenlight.db.seed.seed_bible <script_id>
"""

import sys
from uuid import uuid4

from greenlight.db.client import get_ch_client, query

FIXTURE_FACTS = {
    "JOHNNY": [
        ("relationship", "Brother of Barbara", 1),
        ("personality", "Calm and detached under pressure, teases his sister", 1),
        ("secret", "Skeptical of the threat; underestimates the figures outside", 1),
        ("motivation", "Get Barbara safely inside and board up the house", 1),
    ],
    "BARBARA": [
        ("relationship", "Sister of Johnny", 1),
        ("personality", "Frightened, increasingly unhinged by the ordeal", 1),
        ("physical_trait", "Wears a coat; recently suffered a head injury at the cemetery", 1),
        ("secret", "Witnessed Johnny killed by the figure at the car", 1),
    ],
}


def detect_script_id() -> str | None:
    rows = query("SELECT id, title FROM greenlight.scripts ORDER BY created_at DESC LIMIT 5")
    for sid, title in rows:
        if any(k in title.lower() for k in ("night", "living", "notld")):
            return sid
    return rows[0][0] if rows else None


def main() -> None:
    script_id = sys.argv[1] if len(sys.argv) > 1 else detect_script_id()
    if not script_id:
        print("No scripts in DB. Upload one first via /api/scripts/upload.")
        sys.exit(1)

    existing_rows = query(
        "SELECT count() FROM greenlight.bible_facts WHERE script_id = %(sid)s",
        {"sid": script_id},
    )
    existing = int(existing_rows[0][0]) if existing_rows else 0
    if existing > 0:
        print(f"Script {script_id} already has {existing} bible facts. Skipping.")
        return

    rows: list[dict] = []
    for character, facts in FIXTURE_FACTS.items():
        for category, claim, page in facts:
            fact_id = f"{character.lower()}-{uuid4().hex[:8]}"
            rows.append(
                {
                    "script_id": script_id,
                    "character_id": character,
                    "fact_id": fact_id,
                    "category": category,
                    "claim": claim,
                    "source_page": int(page),
                }
            )

    get_ch_client().insert(
        "greenlight.bible_facts",
        [
            [
                r["script_id"],
                r["character_id"],
                r["fact_id"],
                r["category"],
                r["claim"],
                r["source_page"],
            ]
            for r in rows
        ],
        column_names=[
            "script_id",
            "character_id",
            "fact_id",
            "category",
            "claim",
            "source_page",
        ],
    )

    print(f"Seeded {len(rows)} bible_facts rows for script {script_id}:")
    for character in FIXTURE_FACTS:
        print(f"  - {character}")


if __name__ == "__main__":
    main()
