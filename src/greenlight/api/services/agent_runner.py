"""Agent runner: wraps ADK Runner, emits AgentEvent to in-process broker."""

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

from ...agents.analytics import analytics
from ...agents.bible import bible
from ...agents.rewrite import rewrite
from ...agents.showrunner import showrunner
from ...config import settings
from ...db.client import query
from .agent_output import record_agent_run

logger = logging.getLogger(__name__)

# ADK's Runner constructs its own genai.Client() from environment only, ignoring
# the project's pydantic settings. Seed the env from config so agent model calls
# authenticate the same way the rest of the app does (Vertex + ADC / API key).
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", settings.google_genai_use_vertexai)
if settings.google_cloud_project:
    os.environ.setdefault("GOOGLE_CLOUD_PROJECT", settings.google_cloud_project)
if settings.google_api_key:
    os.environ.setdefault("GOOGLE_API_KEY", settings.google_api_key)

AGENTS = {
    "showrunner": showrunner,
    "bible": bible,
    "analytics": analytics,
    "rewrite": rewrite,
}


def _script_title(script_id: str) -> str:
    """Best-effort script title lookup. Returns '' if the script is unknown."""
    if not script_id:
        return ""
    try:
        rows = query(
            "SELECT title FROM greenlight.scripts WHERE id = %(id)s",
            {"id": script_id},
        )
    except Exception as e:  # pragma: no cover - depends on environment
        logger.warning(f"script title lookup failed for {script_id}: {e}")
        return ""
    return rows[0][0] if rows else ""


def _build_context(script_id: str, scene_id: str) -> str:
    """Assemble the script context block so agent tools target the right rows."""
    if not script_id:
        return ""
    title = _script_title(script_id)
    lines = [
        "CONTEXT — you are operating on the following script:",
        f"- script_id: {script_id}",
        f"- title: {title or '(unknown)'}",
    ]
    if scene_id:
        lines.append(f"- scene_id (target scene): {scene_id}")
    lines.append("Use script_id in every tool call. load existing facts/coverage before judging.")
    return "\n".join(lines)


@dataclass
class AgentEvent:
    agent: str
    status: str  # "running" | "completed" | "error"
    message: str = ""
    ts: float = field(default_factory=time.time)
    result: Any = None


class AgentBroker:
    """In-process pub/sub for agent events. Frontend subscribes via /ws/agents."""

    def __init__(self, max_queue_size: int = 100):
        self.max_queue_size = max_queue_size
        self._subscribers: list[asyncio.Queue] = []
        self._lock = asyncio.Lock()

    async def subscribe(self) -> asyncio.Queue:
        async with self._lock:
            q: asyncio.Queue = asyncio.Queue(maxsize=self.max_queue_size)
            self._subscribers.append(q)
            return q

    async def unsubscribe(self, q: asyncio.Queue) -> None:
        async with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    async def publish(self, event: AgentEvent) -> None:
        async with self._lock:
            subs = list(self._subscribers)
        for q in subs:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning(
                    f"agent broker: dropping event for slow subscriber (qsize={q.qsize()})"
                )


broker = AgentBroker()


_RUNNERS: dict[str, Any] = {}
_RUNNER_LOCK = asyncio.Lock()


async def _get_runner(agent_name: str) -> Any:
    """Memoize Runner per agent. Eliminates per-call cold start (5-10s)."""
    if agent_name in _RUNNERS:
        return _RUNNERS[agent_name]
    async with _RUNNER_LOCK:
        if agent_name in _RUNNERS:
            return _RUNNERS[agent_name]
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService

        session_service = InMemorySessionService()
        _RUNNERS[agent_name] = Runner(
            agent=AGENTS[agent_name],
            app_name="greenlight",
            session_service=session_service,
        )
        return _RUNNERS[agent_name]


async def run_agent(
    agent_name: str,
    prompt: str,
    context: dict | None = None,
    script_id: str = "",
    scene_id: str = "",
) -> dict:
    """Run a named agent with the given prompt. Emits events to broker.

    If script_id is provided, a context block is injected into the prompt so the
    agent's tools target the right script, and the result is persisted to the
    agent_runs table. Returns dict with agent result or error info.
    """
    if agent_name not in AGENTS:
        return {"error": f"Unknown agent: {agent_name}"}

    await broker.publish(AgentEvent(agent=agent_name, status="running"))

    start = time.time()
    try:
        runner = await _get_runner(agent_name)

        session = await runner.session_service.create_session(
            app_name="greenlight",
            user_id="local",
            session_id=f"run_{agent_name}_{int(start * 1000)}",
        )

        from google.genai import types

        context_block = _build_context(script_id, scene_id)
        full_prompt = f"{context_block}\n\n{prompt}" if context_block else prompt

        user_msg = types.Content(
            role="user",
            parts=[types.Part.from_text(text=full_prompt)],
        )

        final_response = None
        async for event in runner.run_async(
            user_id="local",
            session_id=session.id,
            new_message=user_msg,
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        final_response = part.text

        elapsed = time.time() - start
        result = {
            "agent": agent_name,
            "response": final_response or "",
            "elapsed_s": round(elapsed, 2),
        }

        record_agent_run(
            agent=agent_name,
            script_id=script_id,
            scene_id=scene_id,
            status="completed",
            prompt=prompt,
            result=result,
            elapsed_s=elapsed,
        )

        await broker.publish(
            AgentEvent(
                agent=agent_name,
                status="completed",
                message=f"Completed in {elapsed:.1f}s",
                result=result,
            )
        )

        return result

    except Exception as e:
        elapsed = time.time() - start
        error_msg = f"{agent_name} failed after {elapsed:.1f}: {e}"
        logger.error(error_msg, exc_info=True)

        record_agent_run(
            agent=agent_name,
            script_id=script_id,
            scene_id=scene_id,
            status="error",
            prompt=prompt,
            result={"error": str(e)},
            elapsed_s=elapsed,
        )

        await broker.publish(
            AgentEvent(
                agent=agent_name,
                status="error",
                message=error_msg,
            )
        )

        return {"agent": agent_name, "error": str(e), "elapsed_s": round(elapsed, 2)}
