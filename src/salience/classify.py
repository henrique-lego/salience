# First-pass classification of bookmarks using Claude Haiku
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import anthropic

from salience.config.models import SalienceConfig
from salience.models import ClassifiedBookmark, Depth, Intent, ResolvedBookmark

logger = logging.getLogger(__name__)

CLASSIFY_PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "classify.md"

# Max bookmarks per classification batch (keeps context manageable)
BATCH_SIZE = 20


def _load_prompt() -> str:
    """Load the classification system prompt from the prompts directory."""
    return CLASSIFY_PROMPT_PATH.read_text()


def _build_user_message(bookmarks: list[ResolvedBookmark]) -> str:
    """Build the user message with all bookmarks for batch classification."""
    entries = []
    for b in bookmarks:
        content_preview = b.resolved_content[:500]
        if len(b.resolved_content) > 500:
            content_preview += "..."

        entry = (
            f"ID: {b.raw.id}\n"
            f"Author: @{b.raw.author_username}\n"
            f"Tweet: {b.raw.text}\n"
            f"Source: {b.content_source.value}"
        )
        if b.resolved_url:
            entry += f"\nURL: {b.resolved_url}"
        entry += f"\nResolved content:\n{content_preview}"
        entries.append(entry)

    return "\n\n---\n\n".join(entries)


def _extract_json(raw_text: str) -> list[dict[str, object]]:
    """Extract a JSON array from Claude's response, handling various formats."""
    # Try direct parse first
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        pass

    # Try extracting from code blocks
    pattern = r"```(?:json)?\s*\n?(.*?)```"
    matches = re.findall(pattern, raw_text, re.DOTALL)
    for match in matches:
        try:
            return json.loads(match.strip())
        except json.JSONDecodeError:
            continue

    # Try finding a JSON array anywhere in the text
    bracket_match = re.search(r"\[.*\]", raw_text, re.DOTALL)
    if bracket_match:
        try:
            return json.loads(bracket_match.group())
        except json.JSONDecodeError:
            pass

    logger.error("Failed to extract JSON from response: %s", raw_text[:300])
    return []


def _parse_classification(
    raw_text: str, bookmarks: list[ResolvedBookmark]
) -> list[ClassifiedBookmark]:
    """Parse Claude's JSON response into ClassifiedBookmark objects."""
    bookmarks_by_id = {b.raw.id: b for b in bookmarks}
    classifications = _extract_json(raw_text)

    results = []
    for item in classifications:
        bookmark_id = str(item["id"])
        resolved = bookmarks_by_id.get(bookmark_id)
        if not resolved:
            logger.warning("Classification returned unknown bookmark ID: %s", bookmark_id)
            continue

        results.append(
            ClassifiedBookmark(
                resolved=resolved,
                domains=item.get("domains", []),
                intent=Intent(item.get("intent", "learn")),
                depth=Depth(item.get("depth", "surface")),
                summary=item.get("summary", ""),
            )
        )

    # Include any bookmarks that weren't in the classification response
    classified_ids = {str(item["id"]) for item in classifications}
    for b in bookmarks:
        if b.raw.id not in classified_ids:
            logger.warning(
                "Bookmark %s not in classification response, using defaults", b.raw.id
            )
            results.append(
                ClassifiedBookmark(
                    resolved=b,
                    domains=[],
                    intent=Intent.LEARN,
                    depth=Depth.SURFACE,
                    summary=b.raw.text[:100],
                )
            )

    return results


async def _classify_batch(
    bookmarks: list[ResolvedBookmark],
    config: SalienceConfig,
    client: anthropic.AsyncAnthropic,
    system_prompt: str,
) -> list[ClassifiedBookmark]:
    """Classify a single batch of bookmarks."""
    user_message = _build_user_message(bookmarks)

    response = await client.messages.create(
        model=config.models.classify,
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )

    raw_text = response.content[0].text
    return _parse_classification(raw_text, bookmarks)


async def classify_bookmarks(
    bookmarks: list[ResolvedBookmark], config: SalienceConfig
) -> list[ClassifiedBookmark]:
    """Classify bookmarks in batches to stay within context limits."""
    if not bookmarks:
        return []

    system_prompt = _load_prompt()

    client = anthropic.AsyncAnthropic(
        api_key=config.anthropic.auth_token,
        base_url=config.anthropic.base_url,
    )

    # Process in batches
    all_classified: list[ClassifiedBookmark] = []
    total_batches = (len(bookmarks) + BATCH_SIZE - 1) // BATCH_SIZE

    for i in range(0, len(bookmarks), BATCH_SIZE):
        batch = bookmarks[i : i + BATCH_SIZE]
        batch_num = (i // BATCH_SIZE) + 1
        logger.info(
            "Classifying batch %d/%d (%d bookmarks) with %s",
            batch_num,
            total_batches,
            len(batch),
            config.models.classify,
        )
        classified = await _classify_batch(batch, config, client, system_prompt)
        all_classified.extend(classified)

    logger.info("Classified %d bookmarks total", len(all_classified))
    return all_classified
