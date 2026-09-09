"""Tests for vocabulary_engine.py — pure functions, no I/O."""

from greenlight.tools.vocabulary_engine import (
    capitalize_first_appearance,
    check_stoplist_collisions,
    detect_commands,
    extract_vocabulary,
    fountain_insert,
    rank_characters,
    seed_seen_names,
    strip_list_artifacts,
)


class TestStripListArtifacts:
    def test_strips_numbered_items(self):
        assert strip_list_artifacts("1. Go to the store") == "Go to the store"
        assert strip_list_artifacts("2. Come back") == "Come back"

    def test_strips_bullets(self):
        assert strip_list_artifacts("- Buy milk") == "Buy milk"
        assert strip_list_artifacts("* Buy eggs") == "Buy eggs"
        assert strip_list_artifacts("• Buy bread") == "Buy bread"

    def test_preserves_mid_line_numbers(self):
        assert strip_list_artifacts("I bought 1. five items") == "I bought 1. five items"

    def test_multiline(self):
        text = "1. First item\n- Second item\nThird item"
        assert strip_list_artifacts(text) == "First item\nSecond item\nThird item"

    def test_empty_string(self):
        assert strip_list_artifacts("") == ""

    def test_whitespace_only(self):
        assert strip_list_artifacts("   \n  ") == ""


class TestExtractVocabulary:
    SAMPLE = """INT. COFFEE SHOP - NIGHT

SARAH sits alone with cold coffee.

SARAH
(quietly)
You said you'd call.

JOE
I know what I said.

CUT TO:

EXT. PARKING LOT - CONTINUOUS

Joe follows her into the rain.
"""

    def test_returns_screenplay_terms(self):
        terms, names = extract_vocabulary(self.SAMPLE)
        assert "INT." in terms
        assert "EXT." in terms
        assert "CUT TO:" in terms

    def test_extracts_character_names(self):
        terms, names = extract_vocabulary(self.SAMPLE)
        assert "SARAH" in names
        assert "JOE" in names

    def test_character_names_in_vocabulary(self):
        terms, names = extract_vocabulary(self.SAMPLE)
        upper_terms = [t.upper() for t in terms]
        assert "SARAH" in upper_terms
        assert "JOE" in upper_terms

    def test_deduplicates(self):
        terms, _ = extract_vocabulary(self.SAMPLE)
        assert len(terms) == len(set(t.upper() for t in terms))

    def test_capped_at_100(self):
        # Generate a script with many unique terms
        lines = ["INT. ROOM - NIGHT"] + [f"CHARACTER_{i}\nLine {i}" for i in range(200)]
        terms, _ = extract_vocabulary("\n".join(lines))
        assert len(terms) <= 100


class TestRankCharacters:
    SAMPLE = """INT. OFFICE - DAY

SARAH
Hello there.

JOE
Hi SARAH.

SARAH
How are you?

JOE
Good thanks.

SARAH
Great.
"""

    def test_ranks_by_frequency(self):
        names = ["SARAH", "JOE"]
        ranked = rank_characters(self.SAMPLE, names)
        assert ranked[0] == "SARAH"  # 3 lines vs 2

    def test_unknown_characters_excluded(self):
        ranked = rank_characters(self.SAMPLE, ["UNKNOWN"])
        assert "UNKNOWN" not in ranked or ranked.count("UNKNOWN") == 0


class TestSeedSeenNames:
    def test_present_name_seen(self):
        seen = seed_seen_names("SARAH sits alone.", ["SARAH", "JOE"])
        assert seen == {"SARAH"}

    def test_case_insensitive(self):
        seen = seed_seen_names("sarah sits alone.", ["SARAH"])
        assert seen == {"SARAH"}

    def test_word_boundary_only(self):
        assert seed_seen_names("sarahs house", ["SARAH"]) == set()

    def test_empty_text_sees_nothing(self):
        assert seed_seen_names("", ["SARAH"]) == set()


class TestCheckStoplistCollisions:
    def test_collisions_detected(self):
        assert check_stoplist_collisions(["Grace", "Bob"]) == ["Grace"]

    def test_no_collisions(self):
        assert check_stoplist_collisions(["Bob", "Mary Jane"]) == []

    def test_multi_word_never_collides(self):
        assert check_stoplist_collisions(["Mary Jane"]) == []

    def test_empty_list(self):
        assert check_stoplist_collisions([]) == []


class TestCapitalizeFirstAppearance:
    def test_first_occurrence_capped(self):
        text, seen = capitalize_first_appearance(
            "sarah walks in. Sarah sits down.", ["SARAH"], set()
        )
        assert text.startswith("SARAH")
        assert "SARAH" in seen

    def test_already_seen_not_capped(self):
        text, seen = capitalize_first_appearance("sarah walks in.", ["SARAH"], {"SARAH"})
        assert text == "sarah walks in."

    def test_stoplist_name_skipped(self):
        text, _ = capitalize_first_appearance(
            "he will grant her request.", ["Will", "Grant"], set()
        )
        assert text == "he will grant her request."

    def test_multi_word_always_caps(self):
        text, seen = capitalize_first_appearance("mary jane walks in.", ["MARY JANE"], set())
        assert "MARY JANE" in text

    def test_word_boundary_only(self):
        text, _ = capitalize_first_appearance("sarahs house is nice.", ["SARAH"], set())
        # "sarahs" should NOT become "SARAHs" — word boundary
        assert text == "sarahs house is nice."


class TestDetectCommands:
    def test_deletion_tail(self):
        result = detect_commands("scratch that")
        assert len(result.commands) == 1
        assert result.commands[0]["action"] == "delete"
        assert result.commands[0]["scope"] == "last_segment"

    def test_deletion_scratch_it(self):
        result = detect_commands("scratch it")
        assert result.commands[0]["action"] == "delete"

    def test_deletion_last_sentence(self):
        result = detect_commands("delete last sentence")
        assert result.commands[0]["scope"] == "last_sentence"

    def test_compound_character_with_dialogue(self):
        result = detect_commands("character SALLY parenthetical laughing dialogue I agree")
        assert result.compound is True
        assert len(result.commands) == 2
        assert result.commands[0]["action"] == "character"
        assert result.commands[0]["value"] == "SALLY"
        assert result.commands[1]["action"] == "parenthetical"
        assert result.dialogue == "I agree"

    def test_compound_character_only(self):
        result = detect_commands("character JOHN")
        assert result.compound is True
        assert result.commands[0]["action"] == "character"
        assert result.commands[0]["value"] == "JOHN"
        assert result.dialogue is None

    def test_compound_is_connector(self):
        result = detect_commands("character is MARY dialogue hello")
        assert result.commands[0]["value"] == "MARY"
        assert result.dialogue == "hello"

    def test_scene_heading(self):
        result = detect_commands("new scene interior coffee shop night")
        assert result.commands[0]["action"] == "scene_heading"
        assert "INT." in result.commands[0]["value"]
        assert "COFFEE SHOP" in result.commands[0]["value"]
        assert "NIGHT" in result.commands[0]["value"]

    def test_scene_heading_smart_rephrase(self):
        # SMART mode + vocab biasing may emit an already-formatted heading
        result = detect_commands("New scene. INT. COFFEE SHOP - NIGHT.")
        assert result.commands[0]["action"] == "scene_heading"
        assert result.commands[0]["value"] == "INT. COFFEE SHOP - NIGHT"

        result = detect_commands("New scene, EXT. park day.")
        assert result.commands[0]["action"] == "scene_heading"
        assert result.commands[0]["value"] == "EXT. PARK - DAY"

    def test_action_mode(self):
        result = detect_commands("action")
        assert result.commands[0]["action"] == "action"

    def test_parenthetical(self):
        result = detect_commands("parenthetical beat")
        assert result.commands[0]["action"] == "parenthetical"
        assert result.commands[0]["value"] == "(beat)"

    def test_transition(self):
        result = detect_commands("transition fade to black")
        assert result.commands[0]["action"] == "transition"
        assert "FADE TO BLACK" in result.commands[0]["value"]

    def test_new_line(self):
        result = detect_commands("new line")
        assert result.commands[0]["action"] == "new_line"

    def test_new_paragraph(self):
        result = detect_commands("new paragraph")
        assert result.commands[0]["action"] == "new_paragraph"

    def test_writer_note(self):
        result = detect_commands("writer's note check timeline")
        assert result.commands[0]["action"] == "writer_note"
        assert "check timeline" in result.commands[0]["value"]

    def test_plain_prose_returns_empty(self):
        result = detect_commands("Sarah walks into the room and sits down.")
        assert result.commands == []
        assert result.dialogue is None

    def test_list_artifact_before_command(self):
        result = detect_commands("1. New scene interior office night")
        assert result.commands[0]["action"] == "scene_heading"

    def test_mid_sentence_deletion_not_triggered(self):
        result = detect_commands("please delete last sentence of the email")
        assert result.commands == []

    def test_compound_punctuation_collate(self):
        result = detect_commands("character SALLY, parenthetical laughing, dialogue I agree")
        assert result.commands[0]["value"] == "SALLY"
        assert result.dialogue == "I agree"

    def test_bounded_name_stops_at_lowercase(self):
        result = detect_commands("character JOHN walks into the room")
        # Should NOT match — "walks" is lowercase, stops the name run
        assert result.commands == []
        assert result.dialogue is None


class TestFountainInsert:
    def test_scene_heading(self):
        assert (
            fountain_insert({"action": "scene_heading", "value": "INT. OFFICE - DAY"})
            == "\n\nINT. OFFICE - DAY\n\n"
        )

    def test_character(self):
        assert fountain_insert({"action": "character", "value": "SARAH"}) == "\n\nSARAH\n"

    def test_parenthetical(self):
        assert fountain_insert({"action": "parenthetical", "value": "(beat)"}) == "\n(beat)\n"

    def test_transition(self):
        assert (
            fountain_insert({"action": "transition", "value": "FADE TO BLACK."})
            == "\n\nFADE TO BLACK.\n\n"
        )

    def test_new_line(self):
        assert fountain_insert({"action": "new_line"}) == "\n"

    def test_new_paragraph(self):
        assert fountain_insert({"action": "new_paragraph"}) == "\n\n"

    def test_writer_note(self):
        assert (
            fountain_insert({"action": "writer_note", "value": "[[Note: check timeline]]"})
            == "[[Note: check timeline]]"
        )

    def test_delete_returns_empty(self):
        assert fountain_insert({"action": "delete", "scope": "last_segment"}) == ""
