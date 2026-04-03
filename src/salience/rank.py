# Ranking and grouping of evaluated briefs using Claude Opus
from __future__ import annotations

import json
import logging
from pathlib import Path

import anthropic

from salience.config.models import SalienceConfig
from salience.models import Brief, RankedDigest

logger = logging.getLogger(__name__)

RANK_PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "rank.md"


async def rank_briefs(
    briefs: list[Brief],
    digest_date: str,
    config: SalienceConfig,
) -> RankedDigest:
    """Rank and group briefs into act/park/learn/discard categories."""
    if not briefs:
        return RankedDigest(
            date=digest_date,
            bookmarks_processed=0,
            window_start=digest_date,
            window_end=digest_date,
        )

    system_prompt = RANK_PROMPT_PATH.read_text()
    user_message = _build_rank_message(briefs)

    logger.info("Ranking %d briefs with %s", len(briefs), config.models.rank)

    client = anthropic.AsyncAnthropic(
        api_key=config.anthropic.auth_token,
        base_url=config.anthropic.base_url,
    )

    response = await client.messages.create(
        model=config.models.rank,
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )

    return _parse_ranking(response.content[0].text, briefs, digest_date)


def _build_rank_message(briefs: list[Brief]) -> str:
    """Build the user message with all briefs for ranking."""
    parts = []
    for i, brief in enumerate(briefs):
        parts.append(
            f"## Brief {i}\n"
            f"**Title:** {brief.title}\n"
            f"**Domains:** {', '.join(brief.domains)}\n"
            f"**Intent:** {brief.intent.value}\n"
            f"**What this is:** {brief.what_this_is}\n"
            f"**What it means:** {brief.what_it_means}\n"
            f"**Suggested action:** {brief.suggested_action.value}\n"
            f"**Action detail:** {brief.action_detail}\n"
            f"**Cluster:** {'yes' if brief.is_cluster else 'no'}"
        )
    return "\n\n".join(parts)


def _parse_ranking(
    raw_text: str, briefs: list[Brief], digest_date: str
) -> RankedDigest:
    """Parse Claude's ranking response into a RankedDigest."""
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        if "```json" in raw_text:
            start = raw_text.index("```json") + 7
            end = raw_text.index("```", start)
            data = json.loads(raw_text[start:end])
        else:
            logger.error("Failed to parse ranking response")
            # Fallback: put everything in "act"
            return RankedDigest(
                date=digest_date,
                bookmarks_processed=len(briefs),
                window_start=digest_date,
                window_end=digest_date,
                act=briefs,
            )

    act_indices = data.get("act", [])
    park_items = data.get("park", [])
    learn_indices = data.get("learn", [])
    discard_items = data.get("discard", [])

    def _safe_get(idx: int) -> Brief | None:
        if 0 <= idx < len(briefs):
            return briefs[idx]
        return None

    act = [b for i in act_indices if (b := _safe_get(i)) is not None]

    park = []
    for item in park_items:
        idx = item if isinstance(item, int) else item.get("index", -1)
        brief = _safe_get(idx)
        if brief:
            park.append(brief)

    learn = [b for i in learn_indices if (b := _safe_get(i)) is not None]

    discard = []
    for item in discard_items:
        idx = item if isinstance(item, int) else item.get("index", -1)
        brief = _safe_get(idx)
        if brief:
            discard.append(brief)

    return RankedDigest(
        date=digest_date,
        bookmarks_processed=len(briefs),
        window_start=digest_date,
        window_end=digest_date,
        act=act,
        park=park,
        learn=learn,
        discard=discard,
    )
