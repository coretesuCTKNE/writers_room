"""Chunk 2: agent output persistence (agent_runs) — real ClickHouse, no LLM."""

import time
import uuid

import pytest

import greenlight.api.services.agent_output as ao
from greenlight.db.client import command


@pytest.fixture
def script_id() -> str:
    return str(uuid.uuid4())


def _cleanup(sid: str):
    command(
        "DELETE FROM greenlight.agent_runs WHERE script_id = %(sid)s",
        {"sid": sid},
    )
    time.sleep(2.0)


class TestRecordAgentRun:
    def test_record_and_list(self, script_id):
        rid = ao.record_agent_run(
            "bible",
            script_id=script_id,
            scene_id="s1",
            prompt="check continuity",
            result={"facts": [{"claim": "stoic"}]},
            elapsed_s=1.25,
        )
        try:
            runs = ao.list_agent_runs(script_id)
            assert len(runs) == 1
            r = runs[0]
            assert r["run_id"] == rid
            assert r["agent"] == "bible"
            assert r["scene_id"] == "s1"
            assert r["prompt"] == "check continuity"
            assert r["result"]["facts"][0]["claim"] == "stoic"
            assert r["elapsed_s"] == 1.25
            assert r["status"] == "completed"
        finally:
            _cleanup(script_id)

    def test_record_string_result(self, script_id):
        ao.record_agent_run("rewrite", script_id=script_id, result="rewritten fountain text")
        try:
            run = ao.latest_agent_run(script_id, "rewrite")
            assert run is not None
            assert run["result"] == "rewritten fountain text"
        finally:
            _cleanup(script_id)

    def test_record_none_result(self, script_id):
        ao.record_agent_run("analytics", script_id=script_id, result=None)
        try:
            run = ao.latest_agent_run(script_id, "analytics")
            assert run is not None
            assert run["result"] == {}
        finally:
            _cleanup(script_id)

    def test_record_error_status(self, script_id):
        ao.record_agent_run(
            "bible",
            script_id=script_id,
            status="error",
            result={"error": "boom"},
        )
        try:
            run = ao.latest_agent_run(script_id, "bible")
            assert run is not None
            assert run["status"] == "error"
            assert run["result"]["error"] == "boom"
        finally:
            _cleanup(script_id)


class TestQueryAgentRuns:
    def test_latest_agent_run_none_when_missing(self, script_id):
        assert ao.latest_agent_run(script_id, "bible") is None

    def test_list_orders_newest_first(self, script_id):
        ao.record_agent_run("bible", script_id=script_id, scene_id="s1")
        ao.record_agent_run("bible", script_id=script_id, scene_id="s2")
        ao.record_agent_run("analytics", script_id=script_id)
        try:
            all_runs = ao.list_agent_runs(script_id)
            agents = [r["agent"] for r in all_runs]
            assert agents == ["analytics", "bible", "bible"]

            bible = ao.list_agent_runs(script_id, agent="bible")
            assert len(bible) == 2
            assert all(r["agent"] == "bible" for r in bible)

            limited = ao.list_agent_runs(script_id, limit=2)
            assert len(limited) == 2
        finally:
            _cleanup(script_id)
