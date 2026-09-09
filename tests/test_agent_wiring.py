"""Chunk 3: agent wiring — tools attached to agents, context injection.

Deterministic tests only (no live LLM call): the ADK Runner needs Vertex
credentials that aren't present in the test env, so we verify the wiring that
doesn't require a model round-trip.
"""


def _tools(agent) -> list:
    """Narrow the loosely-typed ADK `tools` field to typed FunctionTools."""
    from google.adk.tools.function_tool import FunctionTool

    return [t for t in agent.tools if isinstance(t, FunctionTool)]


class TestAgentToolsWired:
    def test_each_agent_attaches_its_tools(self):
        from greenlight.agents.analytics import analytics
        from greenlight.agents.bible import bible
        from greenlight.agents.rewrite import rewrite

        bible_tool_names = {t.name for t in _tools(bible)}
        assert {"list_bible_facts", "add_bible_fact", "delete_bible_fact"} <= bible_tool_names
        assert {"list_characters", "list_scenes"} <= bible_tool_names

        analytics_tool_names = {t.name for t in _tools(analytics)}
        assert {"query_clickhouse", "script_stats", "coverage_history"} <= analytics_tool_names

        rewrite_tool_names = {t.name for t in _tools(rewrite)}
        assert {"get_coverage", "get_coverage_notes", "list_scenes"} <= rewrite_tool_names

    def test_agent_tools_have_declarations(self):
        from greenlight.agents.bible import bible
        from greenlight.agents.rewrite import rewrite

        for tool in _tools(bible) + _tools(rewrite):
            decl = tool._get_declaration()
            assert decl.name == tool.name

    def test_tools_for_is_cached_and_stable(self):
        from greenlight.agents.tools import tools_for

        a = tools_for("bible")
        b = tools_for("bible")
        assert a is b
        assert tools_for("unknown_agent") == []


class TestContextInjection:
    def test_empty_without_script_id(self):
        from greenlight.api.services.agent_runner import _build_context

        assert _build_context("", "") == ""
        assert _build_context("", "s1") == ""

    def test_includes_script_and_scene(self):
        from greenlight.api.services.agent_runner import _build_context

        ctx = _build_context("script-abc", "scene-1")
        assert "script-abc" in ctx
        assert "scene-1" in ctx
        assert "script_id" in ctx

    def test_unknown_script_title_falls_back(self):
        from greenlight.api.services.agent_runner import _build_context

        ctx = _build_context("definitely-not-a-real-script", "")
        assert "(unknown)" in ctx

    def test_script_title_lookup_graceful(self):
        from greenlight.api.services.agent_runner import _script_title

        assert _script_title("") == ""
        assert _script_title("definitely-not-a-real-script") == ""
