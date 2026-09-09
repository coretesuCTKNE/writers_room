"""Grafana MCP toolset for the analytics (story-ops coach) agent.

Attaches the open-source Grafana MCP server (mcp-grafana) over stdio when
GRAFANA_STACK_URL + GRAFANA_SERVICE_ACCOUNT_TOKEN are configured. The agent
then gets Grafana's tool categories at runtime (dashboards, Prometheus, Loki,
alerting, incidents, annotations, ClickHouse datasources) — the Grafana
hackathon track's checked requirement: the agent actively uses the Grafana
stack through MCP.

Unattended-safe: service-account token auth, no browser OAuth. The hosted
mcp.grafana.com endpoint (OAuth 2.1) is the interactive alternative but cannot
run headless, so OSS mode is the default.

Env guard keeps local dev and pytest unaffected: no stack URL or token means
no toolset, and the analytics agent runs with its ClickHouse FunctionTools
only (tests/test_agent_wiring.py relies on that).
"""

import logging

from ..config import settings

logger = logging.getLogger(__name__)

_GRAFANA_MCP_TOOLS = [
    "search_dashboards",
    "get_dashboard_by_uid",
    "get_dashboard_summary",
    "list_datasources",
    "query_clickhouse",
    "alerting_manage_rules",
    "list_incidents",
    "create_annotation",
    "get_annotations",
    "generate_deeplink",
]


# Minimal category set: everything the coach uses, nothing else. Fewer
# registered tools = faster server boot + smaller tools/list handshake.
# NOTE: default enabled-tools omits the clickhouse category entirely — it must
# always be listed here explicitly.
_MCP_ARGS = [
    "mcp-grafana",
    "--enabled-tools",
    "search,dashboard,datasource,annotations,alerting,incident,navigation,clickhouse",
]


def grafana_toolset():
    """MCPToolset wired to Grafana, or None when unconfigured.

    Tool names that don't exist on the server are ignored by the filter, so
    mismatches between hosted/OSS tool surfaces degrade gracefully.
    """
    if not (settings.grafana_stack_url and settings.grafana_service_token):
        return None
    try:
        from google.adk.tools.mcp_tool import McpToolset
        from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
        from mcp import StdioServerParameters
    except ImportError as e:  # pragma: no cover - depends on installed extras
        logger.warning(f"Grafana MCP unavailable: {e}")
        return None

    return McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command="uvx",
                args=_MCP_ARGS,
                env={
                    "GRAFANA_URL": settings.grafana_stack_url,
                    "GRAFANA_SERVICE_ACCOUNT_TOKEN": settings.grafana_service_token,
                },
            ),
        ),
        tool_filter=_GRAFANA_MCP_TOOLS,
        # Avoid clashing with the direct query_clickhouse FunctionTool; also
        # makes Grafana-origin calls obvious in transcripts.
        tool_name_prefix="grafana_",
    )
