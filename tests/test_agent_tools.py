"""Chunk 1: deterministic agent tools (agents/tools.py) — real ClickHouse, no LLM."""

import time
import uuid

import pytest

from greenlight.agents import tools
from greenlight.db.client import command, insert

BIBLE_CATEGORIES = (
    "personality",
    "relationship",
    "backstory",
    "world_rule",
    "timeline",
    "physical_trait",
    "motivation",
    "secret",
)


@pytest.fixture
def script_id() -> str:
    return str(uuid.uuid4())


def _delete_bible_facts(sid: str):
    command(
        "DELETE FROM greenlight.bible_facts WHERE script_id = %(sid)s",
        {"sid": sid},
    )


def _delete_coverage(sid: str):
    command(
        "DELETE FROM greenlight.coverage WHERE script_id = %(sid)s",
        {"sid": sid},
    )


class TestBibleFactTools:
    def test_add_and_list_round_trip(self, script_id):
        cid = "CH_DETECTIVE"
        fact = tools.add_bible_fact(script_id, cid, "personality", "Stoic under pressure", 3)
        assert "fact_id" in fact
        assert fact["character_id"] == cid

        try:
            facts = tools.list_bible_facts(script_id)
            assert len(facts) == 1
            assert facts[0]["claim"] == "Stoic under pressure"
            assert facts[0]["category"] == "personality"
            assert facts[0]["source_page"] == 3

            filtered = tools.list_bible_facts(script_id, character_id=cid)
            assert len(filtered) == 1
            assert tools.list_bible_facts(script_id, character_id="OTHER_CHAR") == []
        finally:
            _delete_bible_facts(script_id)

    def test_add_rejects_unknown_category(self, script_id):
        res = tools.add_bible_fact(script_id, "CH", "nonsense", "claim")
        assert "error" in res
        assert "category" in res["error"]

    def test_add_rejects_empty_claim(self, script_id):
        res = tools.add_bible_fact(script_id, "CH", "personality", "   ")
        assert "error" in res

    def test_all_categories_accepted(self, script_id):
        for cat in BIBLE_CATEGORIES:
            fact = tools.add_bible_fact(script_id, "CH", cat, f"fact for {cat}")
            assert "fact_id" in fact, cat
        _delete_bible_facts(script_id)

    def test_delete_bible_fact(self, script_id):
        fact = tools.add_bible_fact(script_id, "CH", "timeline", "arrives day 2")
        res = tools.delete_bible_fact(script_id, fact["fact_id"])
        assert res["deleted_fact_id"] == fact["fact_id"]
        time.sleep(2.0)
        assert tools.list_bible_facts(script_id) == []


class TestLookupTools:
    def test_list_characters_empty(self, script_id):
        assert tools.list_characters(script_id) == []

    def test_list_scenes_empty(self, script_id):
        assert tools.list_scenes(script_id) == []


class TestAnalyticsTools:
    def test_script_stats_empty(self, script_id):
        st = tools.script_stats(script_id)
        assert st["script_id"] == script_id
        assert st["scene_count"] == 0
        assert st["character_count"] == 0
        assert st["bible_fact_count"] == 0
        assert st["coverage_count"] == 0
        assert {"pass", "consider", "recommend"} <= set(st["coverage_breakdown"])

    def test_script_stats_counts_bible_facts(self, script_id):
        tools.add_bible_fact(script_id, "CH1", "personality", "a")
        tools.add_bible_fact(script_id, "CH2", "motivation", "b")
        try:
            st = tools.script_stats(script_id)
            assert st["bible_fact_count"] == 2
        finally:
            _delete_bible_facts(script_id)

    def test_query_clickhouse_select_only(self, script_id):
        res = tools.query_clickhouse("DELETE FROM greenlight.scripts")
        assert "error" in res

    def test_query_clickhouse_rejects_write_keyword(self, script_id):
        res = tools.query_clickhouse("SELECT * FROM greenlight.scripts; DROP TABLE scripts")
        assert "error" in res

    def test_query_clickhouse_rejects_into_outfile(self, script_id):
        res = tools.query_clickhouse("SELECT 1 INTO OUTFILE '/tmp/x.csv'")
        assert "error" in res

    def test_query_clickhouse_rejects_system_tables(self, script_id):
        res = tools.query_clickhouse("SELECT name FROM system.tables")
        assert "error" in res

    def test_query_clickhouse_rejects_url_function(self, script_id):
        res = tools.query_clickhouse("SELECT url('http://evil.example')")
        assert "error" in res

    def test_query_clickhouse_runs_select(self, script_id):
        res = tools.query_clickhouse(
            "SELECT count() FROM greenlight.bible_facts WHERE script_id = %(s)s",
            {"s": script_id},
        )
        assert isinstance(res, list)
        assert res and isinstance(res[0], list)


class TestCoverageTools:
    def test_get_coverage_missing(self, script_id):
        assert "error" in tools.get_coverage(script_id)

    def test_get_coverage_and_note_counts(self, script_id):
        cov_id = str(uuid.uuid4())
        insert(
            "coverage",
            [
                {
                    "coverage_id": cov_id,
                    "script_id": script_id,
                    "verdict": "CONSIDER",
                    "logline": "line",
                    "synopsis": "syn",
                    "scores": "{}",
                    "analyst_notes": "tighten act 2",
                }
            ],
        )
        insert(
            "notes",
            [
                {"coverage_id": cov_id, "scene_id": "s1", "severity": "major", "message": "pacing"},
                {"coverage_id": cov_id, "scene_id": "s1", "severity": "minor", "message": "typo"},
            ],
        )
        try:
            gc = tools.get_coverage(script_id)
            assert gc["verdict"] == "CONSIDER"
            assert gc["note_counts"] == {"major": 1, "minor": 1}
            assert gc["analyst_notes"] == "tighten act 2"
        finally:
            _delete_coverage(script_id)

    def test_get_coverage_notes_and_severity_filter(self, script_id):
        cov_id = str(uuid.uuid4())
        insert(
            "coverage",
            [
                {
                    "coverage_id": cov_id,
                    "script_id": script_id,
                    "verdict": "PASS",
                    "logline": "l",
                    "synopsis": "s",
                    "scores": "{}",
                    "analyst_notes": "",
                }
            ],
        )
        insert(
            "notes",
            [
                {"coverage_id": cov_id, "scene_id": "s1", "severity": "major", "message": "m1"},
                {"coverage_id": cov_id, "scene_id": "s1", "severity": "minor", "message": "m2"},
            ],
        )
        try:
            all_notes = tools.get_coverage_notes(script_id)
            assert len(all_notes) == 2
            majors = tools.get_coverage_notes(script_id, severity="major")
            assert len(majors) == 1
            assert majors[0]["message"] == "m1"
        finally:
            _delete_coverage(script_id)
