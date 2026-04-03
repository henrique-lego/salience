# Deep evaluation of bookmarks and clusters using Claude
from __future__ import annotations

import asyncio
import json
import logging
import re
from pathlib import Path

import anthropic

from salience.config.models import SalienceConfig
from salience.models import (
    BookmarkCluster,
    Brief,
    ClassifiedBookmark,
    Intent,
    SuggestedAction,
)

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"

# Concurrency limit for parallel evaluations
MAX_CONCURRENT = 5


def _load_prompt(name: str) -> str:
    """Load a prompt template from the prompts directory."""
    return (PROMPTS_DIR / name).read_text()


def _build_single_message(bookmark: ClassifiedBookmark, context: str) -> str:
    """Build the user message for evaluating a single bookmark."""
    parts = [
        "## Bookmark",
        f"**Author:** @{bookmark.resolved.raw.author_username}",
        f"**Tweet:** {bookmark.resolved.raw.text}",
        f"**Source:** {bookmark.resolved.content_source.value}",
    ]
    if bookmark.resolved.resolved_url:
        parts.append(f"**URL:** {bookmark.resolved.resolved_url}")
    parts.append(f"**Domains:** {', '.join(bookmark.domains)}")
    parts.append(f"**Intent:** {bookmark.intent.value}")

    if bookmark.framings:
        parts.append("\n**Additional framings:**")
        for framing in bookmark.framings:
            parts.append(f"- {framing}")

    parts.append(f"\n## Resolved Content\n{bookmark.resolved.resolved_content}")

    if context:
        parts.append(f"\n## User Context\n{context}")

    return "\n".join(parts)


def _build_cluster_message(cluster: BookmarkCluster, context: str) -> str:
    """Build the user message for evaluating a cluster of bookmarks."""
    parts = [
        f"## Cluster: {cluster.cluster_title}",
        f"**Shared domains:** {', '.join(cluster.shared_domains)}",
        f"**Members:** {len(cluster.members)}",
    ]

    for i, member in enumerate(cluster.members, 1):
        parts.append(f"\n### Source {i}")
        parts.append(f"**Author:** @{member.resolved.raw.author_username}")
        parts.append(f"**Tweet:** {member.resolved.raw.text}")
        if member.resolved.resolved_url:
            parts.append(f"**URL:** {member.resolved.resolved_url}")
        parts.append(f"\n{member.resolved.resolved_content}")

    if context:
        parts.append(f"\n## User Context\n{context}")

    return "\n".join(parts)


def _extract_json_object(raw_text: str) -> dict[str, object]:
    """Extract a JSON object from Claude's response, handling various formats."""
    # Direct parse
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        pass

    # Code blocks
    for match in re.findall(r"```(?:json)?\s*\n?(.*?)```", raw_text, re.DOTALL):
        try:
            return json.loads(match.strip())
        except json.JSONDecodeError:
            continue

    # Bare JSON object anywhere in text
    brace_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group())
        except json.JSONDecodeError:
            pass

    logger.error("Failed to extract JSON from response: %s", raw_text[:300])
    return {}


def _parse_brief(raw_text: str, is_cluster: bool = False) -> Brief:
    """Parse Claude's JSON response into a Brief."""
    data = _extract_json_object(raw_text)

    return Brief(
        title=data.get("title", "Untitled"),
        source=data.get("source", ""),
        domains=data.get("domains", []),
        intent=Intent(data.get("intent", "learn")),
        what_this_is=data.get("what_this_is", ""),
        what_it_means=data.get("what_it_means", ""),
        suggested_action=SuggestedAction(data.get("suggested_action", "park")),
        action_detail=data.get("action_detail", ""),
        connections=data.get("connections", []),
        is_cluster=is_cluster,
        member_count=data.get("member_count", 1),
    )


async def evaluate_single(
    bookmark: ClassifiedBookmark,
    context: str,
    config: SalienceConfig,
) -> Brief:
    """Evaluate a single bookmark using the configured model (Sonnet)."""
    system_prompt = _load_prompt("evaluate_single.md")
    user_message = _build_single_message(bookmark, context)

    client = anthropic.AsyncAnthropic(
        api_key=config.anthropic.auth_token,
        base_url=config.anthropic.base_url,
    )

    response = await client.messages.create(
        model=config.models.evaluate_single,
        max_tokens=2048,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )

    brief = _parse_brief(response.content[0].text, is_cluster=False)
    brief.source = (
        f"@{bookmark.resolved.raw.author_username} · "
        f"{bookmark.resolved.raw.created_at.strftime('%Y-%m-%d')}"
    )
    brief.domains = bookmark.domains
    brief.intent = bookmark.intent
    return brief


async def evaluate_cluster(
    cluster: BookmarkCluster,
    context: str,
    config: SalienceConfig,
) -> Brief:
    """Evaluate a bookmark cluster using the configured model (Opus)."""
    system_prompt = _load_prompt("evaluate_cluster.md")
    user_message = _build_cluster_message(cluster, context)

    client = anthropic.AsyncAnthropic(
        api_key=config.anthropic.auth_token,
        base_url=config.anthropic.base_url,
    )

    response = await client.messages.create(
        model=config.models.evaluate_cluster,
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )

    brief = _parse_brief(response.content[0].text, is_cluster=True)
    brief.domains = cluster.shared_domains
    brief.member_count = len(cluster.members)
    return brief


async def evaluate_all(
    items: list[ClassifiedBookmark | BookmarkCluster],
    contexts: dict[str, str],
    config: SalienceConfig,
) -> list[Brief]:
    """Evaluate all items concurrently with a concurrency limit."""
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    async def _eval_with_limit(
        item: ClassifiedBookmark | BookmarkCluster,
    ) -> Brief:
        async with semaphore:
            item_id = _get_item_id(item)
            context = contexts.get(item_id, "")

            if isinstance(item, BookmarkCluster):
                logger.info(
                    "Evaluating cluster '%s' (%d members) with %s",
                    item.cluster_title,
                    len(item.members),
                    config.models.evaluate_cluster,
                )
                return await evaluate_cluster(item, context, config)
            else:
                logger.info(
                    "Evaluating bookmark '%s' with %s",
                    item.resolved.raw.id,
                    config.models.evaluate_single,
                )
                return await evaluate_single(item, context, config)

    briefs = await asyncio.gather(*[_eval_with_limit(item) for item in items])
    logger.info("Evaluated %d items", len(briefs))
    return list(briefs)


def _get_item_id(item: ClassifiedBookmark | BookmarkCluster) -> str:
    """Get a unique identifier for an item."""
    if isinstance(item, BookmarkCluster):
        return f"cluster_{item.cluster_title}"
    return item.resolved.raw.id
