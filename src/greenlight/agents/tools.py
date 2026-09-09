"""Deterministic agent tools: real functions over ClickHouse.

These are pure, sync, LLM-invocable helpers wrapping db/client.py. They are
used by the ADK agents via FunctionTool to give the LLM real read/write access
to script data (bible facts, scenes, characters, coverage) and to persist
agent outputs.

Each tool is written so it can be unit-tested against real ClickHouse with no
LLM involved. All return plain JSON-serializable values.
"""

import re
import uuid
from datetime import date, datetime

from ..db.client import command, insert, query

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
BIBLE_CATEGORIES_SET = set(BIBLE_CATEGORIES)

# Allow only read-only statements to keep the generic analytics tool safe.
_SELECT_RE = re.compile(r"^\s*SELECT\b", re.IGNORECASE)
_FORBIDDEN_RE = re.compile(
    # write keywords + INTO (blocks SELECT ... INTO OUTFILE / INTO FORMAT)
    r"\b(INSERT|UPDATE|DELETE|ALTER|DROP|CREATE|TRUNCATE|GRANT|INTO|OUTFILE|FORMAT)\b"
    # metadata/schema exfiltration
    r"|\b(system|information_schema)\."
    # table functions that read files or hit the network (SSRF/exfil)
    r"|\b(file|url|s3|remote|remotetable|mysql|postgresql)\s*\(",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Bible agent tools
# ---------------------------------------------------------------------------


def list_bible_facts(script_id: str, character_id: str | None = None) -> list[dict]:
    """List continuity facts for a script, optionally filtered by character."""
    params: dict = {"sid": script_id}
    sql = """
        SELECT fact_id, character_id, category, claim, source_page
        FROM greenlight.bible_facts
        WHERE script_id = %(sid)s
    """
    if character_id:
        sql += " AND character_id = %(cid)s"
        params["cid"] = character_id
    sql += " ORDER BY character_id, fact_id"
    rows = query(sql, params)
    return [
        {
            "fact_id": r[0],
            "character_id": r[1],
            "category": r[2],
            "claim": r[3],
            "source_page": r[4],
        }
        for r in rows
    ]


def add_bible_fact(
    script_id: str,
    character_id: str,
    category: str,
    claim: str,
    source_page: int = 0,
) -> dict:
    """Record a new continuity fact for a script character. Returns the new fact."""
    if category not in BIBLE_CATEGORIES_SET:
        return {"error": f"category must be one of: {', '.join(BIBLE_CATEGORIES)}"}
    if not claim or not claim.strip():
        return {"error": "claim is required and cannot be empty"}
    fact_id = str(uuid.uuid4())
    insert(
        "bible_facts",
        [
            {
                "script_id": script_id,
                "character_id": character_id,
                "fact_id": fact_id,
                "category": category,
                "claim": claim.strip(),
                "source_page": int(source_page or 0),
            }
        ],
    )
    return {
        "fact_id": fact_id,
        "script_id": script_id,
        "character_id": character_id,
        "category": category,
        "claim": claim.strip(),
        "source_page": int(source_page or 0),
    }


def delete_bible_fact(script_id: str, fact_id: str) -> dict:
    """Remove a continuity fact by id (post-contradiction resolution)."""
    command(
        "DELETE FROM greenlight.bible_facts WHERE script_id = %(sid)s AND fact_id = %(fid)s",
        {"sid": script_id, "fid": fact_id},
    )
    return {"deleted_fact_id": fact_id, "script_id": script_id}


def list_characters(script_id: str) -> list[dict]:
    """List characters known for a script."""
    rows = query(
        """
        SELECT character_id, name, role, register
        FROM greenlight.characters
        WHERE script_id = %(sid)s
        ORDER BY name
        """,
        {"sid": script_id},
    )
    return [{"character_id": r[0], "name": r[1], "role": r[2], "register": r[3]} for r in rows]


def list_scenes(script_id: str) -> list[dict]:
    """List scene headings in script order."""
    rows = query(
        """
        SELECT scene_id, heading, ordinal, page
        FROM greenlight.scenes
        WHERE script_id = %(sid)s
        ORDER BY ordinal
        """,
        {"sid": script_id},
    )
    return [{"scene_id": r[0], "heading": r[1], "ordinal": r[2], "page": r[3]} for r in rows]


# ---------------------------------------------------------------------------
# Analytics agent tools
# ---------------------------------------------------------------------------


def query_clickhouse(sql: str, bindings: dict | None = None) -> list | dict:
    """Run a read-only SQL SELECT against the greenlight database.

    Use explicit %(name)s bindings for any values. Only SELECT statements are
    allowed; anything else is rejected. Returns list of rows or an error dict.
    """
    if not _SELECT_RE.match(sql):
        return {"error": "only SELECT statements are allowed"}
    if _FORBIDDEN_RE.search(sql):
        return {"error": "statement contains a disallowed keyword"}
    try:
        client_rows = query(sql, bindings or {})
    except Exception as e:  # pragma: no cover - depends on environment
        return {"error": f"query failed: {e}"}
    # ADK JSON-serializes tool results; ClickHouse returns datetime/date/Decimal
    # objects that json.dumps rejects — normalize everything to primitives.
    return [
        [
            v.isoformat()
            if isinstance(v, (datetime, date))
            else str(v)
            if not isinstance(v, (str, int, float, bool, type(None)))
            else v
            for v in r
        ]
        for r in client_rows
    ]


def script_stats(script_id: str) -> dict:
    """Aggregate counts for a script: scenes, characters, bible facts, coverage."""
    scenes = query(
        "SELECT count() FROM greenlight.scenes WHERE script_id = %(sid)s",
        {"sid": script_id},
    )[0][0]
    characters = query(
        "SELECT count() FROM greenlight.characters WHERE script_id = %(sid)s",
        {"sid": script_id},
    )[0][0]
    facts = query(
        "SELECT count() FROM greenlight.bible_facts WHERE script_id = %(sid)s",
        {"sid": script_id},
    )[0][0]
    coverage_rows = query(
        """
        SELECT count(), countIf(verdict = 'PASS'), countIf(verdict = 'CONSIDER'),
               countIf(verdict = 'RECOMMEND')
        FROM greenlight.coverage WHERE script_id = %(sid)s
        """,
        {"sid": script_id},
    )[0]
    return {
        "script_id": script_id,
        "scene_count": scenes,
        "character_count": characters,
        "bible_fact_count": facts,
        "coverage_count": coverage_rows[0],
        "coverage_breakdown": {
            "pass": coverage_rows[1],
            "consider": coverage_rows[2],
            "recommend": coverage_rows[3],
        },
    }


def coverage_history(script_id: str, limit: int = 3) -> list[dict]:
    """Recent coverage verdicts + scores for a script (newest first)."""
    rows = query(
        """
        SELECT verdict, logline, scores, toString(created_at)
        FROM greenlight.coverage
        WHERE script_id = %(sid)s
        ORDER BY created_at DESC
        LIMIT %(lim)s
        """,
        {"sid": script_id, "lim": int(limit)},
    )
    return [
        {
            "verdict": r[0],
            "logline": r[1],
            "scores": r[2],
            "created_at": r[3],
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Coverage/notes tools (used by rewrite + bible agents)
# ---------------------------------------------------------------------------


def get_coverage(script_id: str) -> dict:
    """Latest coverage verdict, logline, note counts by severity."""
    rows = query(
        """
        SELECT coverage_id, verdict, logline, analyst_notes, toString(created_at)
        FROM greenlight.coverage
        WHERE script_id = %(sid)s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        {"sid": script_id},
    )
    if not rows:
        return {"error": "no coverage found for this script"}
    r = rows[0]
    severity_rows = query(
        """
        SELECT severity, count()
        FROM greenlight.notes
        WHERE coverage_id = %(cid)s
        GROUP BY severity
        """,
        {"cid": r[0]},
    )
    return {
        "coverage_id": r[0],
        "verdict": r[1],
        "logline": r[2],
        "analyst_notes": r[3],
        "created_at": r[4],
        "note_counts": {s: c for s, c in severity_rows},
        "script_id": script_id,
    }


def get_coverage_notes(script_id: str, severity: str | None = None) -> list[dict]:
    """Coverage notes for a script, optionally filtered by severity."""
    params: dict = {"sid": script_id}
    sql = """
        SELECT notes.note_id, notes.scene_id, notes.severity, notes.message,
               notes.span, coverage.verdict
        FROM greenlight.notes
        JOIN greenlight.coverage ON coverage.coverage_id = notes.coverage_id
        WHERE coverage.script_id = %(sid)s
    """
    if severity:
        sql += " AND notes.severity = %(sev)s"
        params["sev"] = severity
    sql += " ORDER BY notes.note_id"
    rows = query(sql, params)
    return [
        {
            "note_id": r[0],
            "scene_id": r[1],
            "severity": r[2],
            "message": r[3],
            "span": r[4],
            "verdict": r[5],
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# FunctionTool registry: binds the deterministic functions to ADK tools.
# Builds lazily so importing this module never constructs ADK objects.
# ---------------------------------------------------------------------------


def _build_tools(functions: list) -> list:
    from google.adk.tools.function_tool import FunctionTool

    return [FunctionTool(fn) for fn in functions]


# agent name -> plain functions to wrap. Construction is deferred to tools_for()
_TOOL_FNS: dict[str, list] = {
    "bible": [
        list_bible_facts,
        add_bible_fact,
        delete_bible_fact,
        list_characters,
        list_scenes,
        get_coverage,
        get_coverage_notes,
    ],
    "analytics": [
        query_clickhouse,
        script_stats,
        coverage_history,
        list_scenes,
    ],
    "rewrite": [
        get_coverage,
        get_coverage_notes,
        list_scenes,
    ],
}

_TOOLS_CACHE: dict[str, list] = {}


def tools_for(agent_name: str) -> list:
    """Return the FunctionTool list for an agent (cached, lazily built)."""
    if agent_name in _TOOLS_CACHE:
        return _TOOLS_CACHE[agent_name]
    fns = _TOOL_FNS.get(agent_name, [])
    built = _build_tools(fns)
    _TOOLS_CACHE[agent_name] = built
    return built
