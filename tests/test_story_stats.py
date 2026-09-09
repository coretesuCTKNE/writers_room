"""Pure-function tests for story stats + scene heading anatomy.

No DB — these cover the math the Grafana Story Ops dashboard relies on
(dev_plans/06-grafana-story-ops.md).
"""

from greenlight.tools._fountain_common import scene_setting, scene_time_of_day
from greenlight.tools.fountain_document import parse_document
from greenlight.tools.story_stats import compute_scene_stats, document_stats

SAMPLE = """INT. ROOM A - NIGHT

ALICE
Hello there.

Bob enters the room slowly.

BOB
Hi Alice. Ready?

EXT. YARD - DAY

Alice and Bob walk out.

EST. CITY SKYLINE - DAWN
"""


class TestHeadingAnatomy:
    def test_settings(self):
        assert scene_setting("INT. INTERROGATION ROOM - NIGHT") == "INT"
        assert scene_setting("EXT. ALLEY - DAY") == "EXT"
        assert scene_setting("INT/EXT. CAR - NIGHT") == "INT/EXT"
        assert scene_setting("I/E. CAR - DAY") == "I/E"
        assert scene_setting("EST. CITY - DAY") == "EST"
        assert scene_setting("LATER THAT NIGHT") == ""

    def test_time_of_day(self):
        assert scene_time_of_day("INT. X - NIGHT") == "NIGHT"
        assert scene_time_of_day("EXT. X - DAY") == "DAY"
        assert scene_time_of_day("EXT. X - CONTINUOUS") == "CONTINUOUS"
        assert scene_time_of_day("EXT. X - MOMENTS LATER") == "MOMENTS LATER"
        assert scene_time_of_day("INT. X - DAWN") == "DAWN"
        assert scene_time_of_day("INT. X") == ""
        # 'DAY' inside a word must not match
        assert scene_time_of_day("INT. YESTERDAY - OFFICE") == ""


class TestSceneStats:
    def test_two_scenes(self):
        stats = compute_scene_stats(parse_document(SAMPLE))
        assert len(stats) == 3
        first, second, third = stats

        assert first["setting"] == "INT"
        assert first["time_of_day"] == "NIGHT"
        assert first["dialogue_lines"] == 2
        assert first["dialogue_words"] == 5  # "Hello there." + "Hi Alice. Ready?"
        assert first["action_lines"] == 1
        assert first["action_words"] == 5
        assert first["characters"] == ["ALICE", "BOB"]

        assert second["setting"] == "EXT"
        assert second["time_of_day"] == "DAY"
        assert second["dialogue_lines"] == 0
        assert second["action_words"] == 5
        assert second["characters"] == []

        assert third["setting"] == "EST"
        assert third["time_of_day"] == "DAWN"

    def test_scene_numbers_sequential(self):
        stats = compute_scene_stats(parse_document(SAMPLE))
        assert [s["scene_number"] for s in stats] == [1, 2, 3]

    def test_heading_scene_number_tail_stripped(self):
        stats = compute_scene_stats(parse_document("INT. A - NIGHT #1#\n\nAction.\n"))
        assert stats[0]["heading"] == "INT. A - NIGHT"

    def test_empty_document(self):
        assert compute_scene_stats(parse_document("")) == []


class TestDocumentStats:
    def test_counts(self):
        doc = document_stats(parse_document(SAMPLE))
        assert doc["scenes"] == 3
        assert doc["dialogue_words"] == 5
        assert doc["action_words"] == 10
        assert doc["words"] == 15
        assert doc["pages"] >= 1

    def test_pages_estimate_scales(self):
        big = ("INT. A - NIGHT\n\nSome action line here.\n\nBOB\nTalk.\n\n" * 60).strip()
        doc = document_stats(parse_document(big))
        assert doc["pages"] > 1

    def test_empty_document_minimums(self):
        doc = document_stats(parse_document(""))
        assert doc == {
            "scenes": 0,
            "words": 0,
            "dialogue_words": 0,
            "action_words": 0,
            "pages": 1,
        }
