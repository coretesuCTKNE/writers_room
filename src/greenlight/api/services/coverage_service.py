"""Coverage service: LLM-powered screenplay reader via Vertex AI."""

import json
import logging
import re

from google.genai import types

from ...config import settings
from ...utils.genai_client import get_genai_client, is_llm_available

logger = logging.getLogger(__name__)

COVERAGE_MODEL = settings.coverage_model

READER_INSTRUCTION = """You are a senior script reader for a major studio.
Produce professional coverage of the submitted screenplay.

Return ONLY a JSON object with these keys:
{
  "verdict": "PASS" | "CONSIDER" | "RECOMMEND",
  "logline": "one sentence capturing the core dramatic premise",
  "synopsis": "3-5 paragraph plot summary",
  "comments": {
    "plot": "analysis of structure, pacing, stakes",
    "character": "depth, arcs, distinctiveness",
    "dialogue": "naturalism, subtext, voice consistency",
    "structure": "three-act shape, transitions, momentum",
    "marketability": "genre fit, audience, comparable films"
  },
  "analyst_notes": "2-3 sentences of the most actionable notes"
}

Be specific — cite scene numbers and character names. Never vague.
Every note must be actionable.

SCREENPLAY:
"""

_json_block_re = re.compile(r"\{.*\}", re.DOTALL)


async def generate_coverage(script_text: str) -> dict:
    """Run reader pass on Vertex. Returns parsed coverage dict or raises."""
    client = get_genai_client(key="coverage")

    response = await client.aio.models.generate_content(
        model=COVERAGE_MODEL,
        contents=READER_INSTRUCTION + "\n" + script_text[:120_000],
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )

    raw = response.text or ""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = _json_block_re.search(raw)
        if match:
            return json.loads(match.group(0))
        raise


def is_coverage_available() -> bool:
    return is_llm_available()
