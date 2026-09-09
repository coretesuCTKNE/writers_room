from greenlight.tools.fountain_parser import (
    calculate_gap_ms,
    parse_parenthetical,
    parse_scene,
)

SAMPLE_SCENE = """INT. INTERROGATION ROOM - NIGHT

DETECTIVE
(whispering)
Where were you last night?

SUSPECT
I don't have to answer that--

DETECTIVE
You do. Now tell me.

The Detective walks to the window, lighting a cigarette, staring at the rain.

LAWYER
My client is done talking.
"""


class TestParseParenthetical:
    def test_known_tag(self):
        p = parse_parenthetical("(whispering)")
        assert "[whispers]" in p.tags
        assert p.raw == "whispering"

    def test_unknown_tag_fallback(self):
        p = parse_parenthetical("(beat)")
        assert len(p.tags) == 1

    def test_multiple_tags(self):
        p = parse_parenthetical("(whispering, panicked)")
        assert "[whispers]" in p.tags
        assert "[panicked]" in p.tags


class TestParseScene:
    def test_heading(self):
        scene = parse_scene(SAMPLE_SCENE, "test")
        assert scene.heading == "INT. INTERROGATION ROOM - NIGHT"

    def test_characters_detected(self):
        scene = parse_scene(SAMPLE_SCENE, "test")
        assert "DETECTIVE" in scene.characters
        assert "SUSPECT" in scene.characters
        assert "LAWYER" in scene.characters

    def test_turn_count(self):
        scene = parse_scene(SAMPLE_SCENE, "test")
        assert len(scene.turns) >= 3

    def test_parenthetical_attached(self):
        scene = parse_scene(SAMPLE_SCENE, "test")
        detective_turns = [t for t in scene.turns if t.speaker == "DETECTIVE"]
        first = detective_turns[0]
        assert first.parenthetical is not None
        assert "[whispers]" in first.parenthetical.tags

    def test_interruption_detected(self):
        scene = parse_scene(SAMPLE_SCENE, "test")
        suspect_turns = [t for t in scene.turns if t.speaker == "SUSPECT"]
        assert any(t.is_interrupted for t in suspect_turns)

    def test_estimated_duration_positive(self):
        scene = parse_scene(SAMPLE_SCENE, "test")
        for turn in scene.turns:
            assert turn.estimated_duration_ms >= 500


class TestCalculateGap:
    def test_minimum_gap(self):
        from greenlight.tools.fountain_parser import DialogueTurn

        turn = DialogueTurn(speaker="A", text="Hello.")
        gap = calculate_gap_ms(turn)
        assert gap == 250

    def test_interruption_gap(self):
        from greenlight.tools.fountain_parser import DialogueTurn

        turn = DialogueTurn(speaker="A", text="Hello--", is_interrupted=True)
        gap = calculate_gap_ms(turn)
        assert gap == 50

    def test_action_line_gap(self):
        from greenlight.tools.fountain_parser import DialogueTurn

        turn = DialogueTurn(
            speaker="A",
            text="Hello.",
            post_action_line="He walks to the window.",
            post_action_word_count=5,
        )
        gap = calculate_gap_ms(turn)
        assert gap == 1250

    def test_gap_capped_at_5000(self):
        from greenlight.tools.fountain_parser import DialogueTurn

        turn = DialogueTurn(
            speaker="A",
            text="Hello.",
            post_action_line="word " * 50,
            post_action_word_count=50,
        )
        gap = calculate_gap_ms(turn)
        assert gap == 5000


class TestEmptyScene:
    def test_empty_text(self):
        scene = parse_scene("", "empty")
        assert len(scene.turns) == 0
        assert scene.characters == []

    def test_action_only(self):
        scene = parse_scene("The sun sets over the horizon.", "action")
        assert len(scene.turns) == 0


class TestNarrator:
    NARR_SCENE = """INT. INTERROGATION ROOM - NIGHT

The Detective walks to the window, staring at the rain.

DETECTIVE
Where were you last night?

The Detective lights a cigarette.

SUSPECT
I don't have to answer that.
"""

    def test_default_no_narration(self):
        scene = parse_scene(self.NARR_SCENE, "test")
        assert "NARRATOR" not in scene.characters
        assert not any(t.is_narration for t in scene.turns)

    def test_include_narration_adds_narrator(self):
        scene = parse_scene(self.NARR_SCENE, "test", include_narration=True)
        assert "NARRATOR" in scene.characters
        nar = [t for t in scene.turns if t.is_narration]
        assert len(nar) >= 3

    def test_narration_voices_heading_and_action(self):
        scene = parse_scene(self.NARR_SCENE, "test", include_narration=True)
        texts = [t.text for t in scene.turns if t.is_narration]
        assert "INT. INTERROGATION ROOM - NIGHT" in texts
        assert "walks to the window" in " ".join(texts)
        assert "lights a cigarette" in " ".join(texts)

    def test_narration_turns_ordered(self):
        scene = parse_scene(self.NARR_SCENE, "test", include_narration=True)
        markers = [(t.speaker, t.text.split()[0]) for t in scene.turns]
        assert markers[0] == ("NARRATOR", "INT.")
        assert any(s == "NARRATOR" for s, _ in markers)

    def test_narrator_duration_positive(self):
        scene = parse_scene(self.NARR_SCENE, "test", include_narration=True)
        for t in scene.turns:
            assert t.estimated_duration_ms >= 500
