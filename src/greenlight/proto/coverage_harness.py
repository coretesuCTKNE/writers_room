import logging

from . import opencode_client

logger = logging.getLogger(__name__)

READER_PROMPT = """You are a senior script reader for a major Hollywood studio.
Produce professional coverage of the screenplay below.

COVERAGE FORMAT (follow exactly):

## Logline
One sentence capturing the core dramatic premise.

## Synopsis
3-5 paragraph summary of the plot.

## Comments

### Plot
Analysis of the story structure, pacing, stakes.

### Character
Depth, arcs, distinctiveness of characters.

### Dialogue
Naturalism, subtext, voice consistency.

### Structure
Three-act shape, scene transitions, momentum.

### Marketability
Genre fit, audience, comparable films.

## Script Health
Summarize grammar/formatting quality (passive voice, formatting compliance).

## Verdict
**PASS** | **CONSIDER** | **RECOMMEND** — with 2-3 sentence justification.

---

SCREENPLAY:
"""


def run_coverage(script_text: str) -> dict:
    message = READER_PROMPT + "\n\n" + script_text

    response = opencode_client.run(
        message=message,
        timeout=300,
    )

    coverage_text = response.text

    verdict = "CONSIDER"
    if "RECOMMEND" in coverage_text.upper():
        verdict = "RECOMMEND"
    elif "PASS" in coverage_text.upper().split("## VERDICT")[-1]:
        verdict = "PASS"

    return {
        "coverage_id": f"proto_{response.session_id}",
        "verdict": verdict,
        "coverage_text": coverage_text,
        "tokens_in": response.tokens_in,
        "tokens_out": response.tokens_out,
        "cost": response.cost,
        "source": "opencode_proto",
    }
