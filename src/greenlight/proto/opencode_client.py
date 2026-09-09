import json
import logging
import os
import subprocess
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

OPENCODE_URL = os.getenv("OPENCODE_URL", "http://localhost:4096")


@dataclass
class OpencodeResponse:
    text: str
    session_id: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    cost: float = 0.0
    tool_calls: list[dict] = field(default_factory=list)


def run(
    message: str,
    model: str | None = None,
    session: str | None = None,
    files: list[str] | None = None,
    timeout: int = 300,
) -> OpencodeResponse:
    cmd = [
        "opencode",
        "run",
        "--attach",
        OPENCODE_URL,
        "--format",
        "json",
    ]

    if model:
        cmd += ["--model", model]

    if session:
        cmd += ["--continue", "--session", session]

    if files:
        for f in files:
            cmd += ["--file", f]

    cmd.append(message)

    logger.info(f"opencode run: {message[:80]}...")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        logger.error(f"opencode run timed out after {timeout}s")
        return OpencodeResponse(text=f"[TIMEOUT after {timeout}s]")

    if result.returncode != 0:
        logger.error(f"opencode run failed: {result.stderr[:200]}")
        return OpencodeResponse(text=f"[ERROR: {result.stderr[:200]}]")

    text_parts: list[str] = []
    session_id = ""
    tokens_in = 0
    tokens_out = 0
    cost = 0.0
    tool_calls: list[dict] = []

    for line in result.stdout.strip().splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        event_type = event.get("type", "")
        part = event.get("part", {})

        if event_type == "text":
            text_parts.append(part.get("text", ""))

        if event_type == "step_finish":
            tokens = part.get("tokens", {})
            tokens_in += tokens.get("input", 0)
            tokens_out += tokens.get("output", 0)
            cost += part.get("cost", 0.0)
            session_id = part.get("sessionID", session_id)

        if event_type == "tool_call":
            tool_calls.append(
                {
                    "tool": part.get("tool", ""),
                    "input": part.get("input", {}),
                }
            )

        if event_type == "step_start":
            session_id = part.get("sessionID", session_id)

    return OpencodeResponse(
        text="".join(text_parts),
        session_id=session_id,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost=cost,
        tool_calls=tool_calls,
    )


def is_healthy() -> bool:
    try:
        import httpx

        r = httpx.get(f"{OPENCODE_URL}/session", timeout=5.0)
        return r.status_code == 200
    except Exception:
        return False
