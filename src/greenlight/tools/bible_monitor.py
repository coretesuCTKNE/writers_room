import logging
from dataclasses import asdict, dataclass

from ..db.client import query

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BibleFact:
    fact_id: str
    category: str
    claim: str
    page: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


def check_canon(
    transcript: str,
    speaker: str,
    bible_snapshot: dict[str, list[BibleFact]],
) -> dict | None:
    """Check transcript against bible facts. Returns violation dict or None."""
    if speaker not in bible_snapshot:
        return None

    transcript_lower = transcript.lower()

    for fact in bible_snapshot[speaker]:
        claim_lower = fact.claim.lower()
        if "only child" in claim_lower and any(
            phrase in transcript_lower for phrase in ["my brother", "my sister", "my sibling"]
        ):
            return {
                "rule_id": fact.fact_id,
                "category": fact.category,
                "violation": f"Character claims to have siblings but bible states: {fact.claim}",
                "suggested_fix": "Remove sibling reference or adjust dialogue.",
            }

        if "married to" in claim_lower:
            spouse = fact.claim.split("married to")[-1].strip()
            if f"ex-{spouse.lower()}" in transcript_lower or "single" in transcript_lower:
                return {
                    "rule_id": fact.fact_id,
                    "category": fact.category,
                    "violation": f"Character claims to be single but bible states: {fact.claim}",
                    "suggested_fix": f"Reference spouse {spouse} or clarify context.",
                }

    return None


def build_bible_snapshot(script_id: str) -> dict[str, list[BibleFact]]:
    """Load bible facts for script into in-memory snapshot keyed by character."""
    rows = query(
        "SELECT character_id, fact_id, category, claim, source_page "
        "FROM greenlight.bible_facts WHERE script_id = %(sid)s",
        {"sid": script_id},
    )
    snapshot: dict[str, list[BibleFact]] = {}
    for character_id, fact_id, category, claim, page in rows:
        snapshot.setdefault(character_id, []).append(
            BibleFact(
                fact_id=fact_id,
                category=category,
                claim=claim,
                page=int(page or 0),
            )
        )
    return snapshot
