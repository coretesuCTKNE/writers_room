from greenlight.tools.bible_monitor import BibleFact, check_canon


class TestBibleMonitor:
    def test_sibling_violation_detected(self):
        snapshot = {
            "DETECTIVE": [
                BibleFact(fact_id="1", category="personality", claim="Is an only child"),
            ]
        }
        violation = check_canon("I'll call my brother.", "DETECTIVE", snapshot)
        assert violation is not None
        assert (
            "sibling" in violation["violation"].lower()
            or "brother" in violation["violation"].lower()
        )

    def test_no_violation_clean_text(self):
        snapshot = {
            "DETECTIVE": [
                BibleFact(fact_id="1", category="personality", claim="Is an only child"),
            ]
        }
        violation = check_canon("I'll call my lawyer.", "DETECTIVE", snapshot)
        assert violation is None

    def test_unknown_character_no_violation(self):
        snapshot = {
            "DETECTIVE": [
                BibleFact(fact_id="1", category="personality", claim="Is an only child"),
            ]
        }
        violation = check_canon("I'll call my brother.", "UNKNOWN", snapshot)
        assert violation is None

    def test_empty_snapshot(self):
        violation = check_canon("Any text.", "DETECTIVE", {})
        assert violation is None

    def test_marriage_violation(self):
        snapshot = {
            "SARAH": [
                BibleFact(fact_id="2", category="relationship", claim="Married to Mike"),
            ]
        }
        violation = check_canon("I've been single for years.", "SARAH", snapshot)
        assert violation is not None

    def test_claim_with_pipe_does_not_corrupt(self):
        """Regression: claim containing | must not corrupt parse (pipe-delim era bug)."""
        snapshot = {
            "BOB": [
                BibleFact(fact_id="3", category="hobby", claim="Owns a cat | dog | parrot"),
            ]
        }
        violation = check_canon("hi there", "BOB", snapshot)
        assert violation is None

        violation = check_canon("I have only one sibling, my brother.", "BOB", snapshot)
        assert violation is None

    def test_claim_with_colon(self):
        """Regression: claim containing : must not corrupt parse."""
        snapshot = {
            "ALICE": [
                BibleFact(fact_id="4", category="origin", claim="Born in São Paulo: coastal city"),
            ]
        }
        violation = check_canon("hello world", "ALICE", snapshot)
        assert violation is None
