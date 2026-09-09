"""Seed Story Ops demo data into the configured ClickHouse (dev_plans/06, G1).

Builds a realistic drafting history for a synthetic public-domain-style
screenplay: 12 scenes, 5 characters, varied INT/EXT + DAY/NIGHT. Eight
versions spread over the past 6 days grow scene coverage, each with word/page
counts and per-scene stats, plus a writing goal (words, due Sep 9) and the
active-session pointer. Character presence is deliberately uneven (BEN absent
mid-script) so the presence-gap panel has something to show.

Direct inserts are the seed-script convention (seed_bible.py); runtime app code
never touches these tables outside script_repo.

Usage:
    uv run python src/greenlight/db/seed/seed_story_ops_demo.py
"""

import sys
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from greenlight.api.services.script_repo.state import set_active  # noqa: E402
from greenlight.db.client import insert  # noqa: E402
from greenlight.tools.fountain_document import parse_document  # noqa: E402
from greenlight.tools.story_stats import compute_scene_stats, document_stats  # noqa: E402

SCRIPT_ID = "demo_night_of_living_dead"
BRANCH_ID = str(uuid.uuid4())

C = """
INT. FARMHOUSE KITCHEN - DAY

Barbara sets a small table clock on the mantel. Johnny drapes his coat over a chair and scowls at the ceiling.

JOHNNY
We're here, we visited, can we go now?

BARBARA
Ten more minutes. She looks forward to this.

JOHNNY
She looks forward to the cemetery. That's a fact worth writing down.
""".strip()

D1 = """
EXT. CEMETERY HILL - DAY

A wide gray sky. Barbara carries a wreath of chrysanthemums up the slope. Johnny follows, hands in pockets, kicking stones.

JOHNNY
They're coming to get you, Barbara.

BARBARA
Stop it.

JOHNNY
(ghoulish)
They're coming for you, Barbara.
""".strip()

D2 = """
EXT. CEMETERY HILL - CONTINUOUS

A lone figure stumbles between the headstones, arms out, mouth slack. Johnny circles the strange man, playing for the crowd of none.

JOHNNY
He's coming to get you, too.

The strange man seizes Johnny's wrist. They struggle. Johnny falls, striking his head on a gravestone.
""".strip()

D3 = """
INT. FARMHOUSE PARLOR - NIGHT

Barbara bolts the door, breathing hard. Dust sheets hang over the furniture like standing ghosts. Through the window, the strange man crosses the yard in stiff, deliberate steps.

BARBARA
(whispering)
The phone. There has to be a phone.
""".strip()

D4 = """
INT. FARMHOUSE PARLOR - NIGHT

Ben wedges a crowbar under the front door and drives it home with a hammer blow. He glances at Barbara, huddled by the mantel clock.

BEN
Don't worry. We can hold this place. It has doors, windows. Everything a house is supposed to have.
""".strip()

D5 = """
INT. FARMHOUSE PARLOR - NIGHT

Harry emerges from the cellar, flashlight in hand. He squints at the boarded windows, at Ben's barricade, at the crowbar.

HARRY
You're wasting your time. Downstairs is the only place that makes sense. Walls, one door, no windows.

BEN
Those things turn over cars. You think a cellar door stops them?
""".strip()

D6 = """
EXT. FARMHOUSE PORCH - NIGHT

The truck engine coughs, catches, dies. Ben leans out the driver window and pounds the wheel. Shapes converge from the treeline, slow and inevitable.

BEN
Come on. Come on, you son of a...
""".strip()

D7 = """
INT. FARMHOUSE KITCHEN - NIGHT

Helen arranges canned goods on the counter like ammunition. Harry counts them twice. Outside, knuckles drag along the porch boards.

HELEN
Forty cans. Maybe fifty with the pantry.

HARRY
That's not food for a siege, that's a picnic.
""".strip()

D8 = """
INT. FARMHOUSE PARLOR - NIGHT

Barbara watches the mantel clock tick. Her fingers still rest on the chrysanthemum wreath, now wilted on the arm of a chair. Ben drags a bookcase across the window.

BARBARA
(softly)
He was only teasing. He was always teasing.
""".strip()

D9 = """
INT. FARMHOUSE CELLAR - DAWN

A bare bulb. The family huddles around a battery radio. Static resolves into a voice.

RADIO (V.O.)
...authorities in the eastern sector report the situation remains contained...
""".strip()

D10 = """
EXT. FARMHOUSE YARD - DAWN

Posse men with rifles move through the tall grass in a sweep line. Smoke hangs over the barn. A dog barks somewhere near the road.
""".strip()

D11 = """
EXT. COUNTRY ROAD - DAY

Ben's truck sits where it stalled, doors open. Wind moves the tall grass in slow waves. Nothing else moves at all.
""".strip()

D12 = """
INT. FARMHOUSE PARLOR - DAY

Sunlight knifes through the boarded windows. The mantel clock still ticks, keeping time for no one. On the floor, the wilted chrysanthemums.
""".strip()

SCENES = [C, D1, D2, D3, D4, D5, D6, D7, D8, D9, D10, D11, D12]


def seed() -> None:
    n = len(SCENES)
    print(f"synthetic script: {n} scenes")

    insert(
        "scripts",
        [
            {
                "id": SCRIPT_ID,
                "title": "Night of the Living Dead — Story Ops Demo",
                "author": "demo-writer",
                "draft": 2,
                "genre": "Horror",
            }
        ],
    )

    # 8 checkpoints over the past 6 days: grow scene coverage, final = polish pass
    checkpoints = [3, 5, 6, 8, 10, 11, n, n]
    now = datetime.utcnow()
    version_ids: list[str] = []
    for i, scene_count in enumerate(checkpoints):
        scene_count = min(scene_count, n)
        text = "\n\n".join(SCENES[:scene_count]) + "\n"
        elements = parse_document(text)
        doc = document_stats(elements)
        vid = str(uuid.uuid4())
        version_ids.append(vid)
        # Even 6-day spread: day 6-... down to day 0, plus i hours so same-day
        # checkpoints keep a stable intra-day order (added, not subtracted).
        created = now - timedelta(days=6 - i * 6 / (len(checkpoints) - 1)) + timedelta(hours=i)
        message = (
            "Final polish pass — draft 2"
            if i == len(checkpoints) - 1
            else f"Draft checkpoint: {scene_count}/{n} scenes"
        )
        insert(
            "script_versions",
            [
                {
                    "version_id": vid,
                    "script_id": SCRIPT_ID,
                    "branch_id": BRANCH_ID,
                    "parent_version_id": version_ids[i - 1] if i else "",
                    "message": message,
                    "author": "demo-writer",
                    "raw_fountain": text,
                    "content_hash": f"{i:04x}" + text[:8],
                    "word_count": doc["words"],
                    "page_count": doc["pages"],
                    "created_at": created,
                }
            ],
        )
        rows = compute_scene_stats(elements)
        if rows:
            insert(
                "scene_stats",
                [
                    {
                        "script_id": SCRIPT_ID,
                        "version_id": vid,
                        "scene_number": r["scene_number"],
                        "heading": r["heading"],
                        "setting": r["setting"],
                        "time_of_day": r["time_of_day"],
                        "dialogue_lines": r["dialogue_lines"],
                        "action_lines": r["action_lines"],
                        "dialogue_words": r["dialogue_words"],
                        "action_words": r["action_words"],
                        "characters": r["characters"],
                        "created_at": created,
                    }
                    for r in rows
                ],
            )

    insert(
        "script_branches",
        [
            {
                "branch_id": BRANCH_ID,
                "script_id": SCRIPT_ID,
                "name": "main",
                "head_version_id": version_ids[-1],
            }
        ],
    )
    insert(
        "writing_goals",
        [
            {
                "goal_id": str(uuid.uuid4()),
                "script_id": SCRIPT_ID,
                "metric": "words",
                "target": 900,
                "deadline": date(2026, 9, 9),
                "note": "Draft 2 to the room",
                "active": True,
            }
        ],
    )
    set_active(SCRIPT_ID, BRANCH_ID, version_ids[-1])
    print(f"seeded: {len(version_ids)} versions, branch main, goal 900 words by Sep 9")
    print(f"script_id: {SCRIPT_ID}")


if __name__ == "__main__":
    seed()
