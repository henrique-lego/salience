# Obsidian markdown formatting with entity linking
from __future__ import annotations

import re

from salience.models import Brief, RankedDigest


def format_digest(
    ranked: RankedDigest,
    interest_signals: str,
    entities: dict[str, str],
    tag_vocab: dict[str, list[str]],
) -> str:
    """Format the complete digest as Obsidian-compatible markdown."""
    parts = [
        _frontmatter(ranked),
        f"# Salience Digest – {ranked.date}\n",
        _summary_line(ranked),
    ]

    if ranked.act:
        parts.append("\n## Act on these\n")
        for brief in ranked.act:
            parts.append(_format_brief(brief, entities, tag_vocab))

    if ranked.park:
        parts.append("\n## Park\n")
        for brief in ranked.park:
            parts.append(_format_brief_short(brief))

    if ranked.learn:
        parts.append("\n## Learning backlog\n")
        for brief in ranked.learn:
            parts.append(_format_brief(brief, entities, tag_vocab))

    if ranked.discard:
        parts.append("\n## Discarded\n")
        for brief in ranked.discard:
            parts.append(_format_brief_short(brief))

    if interest_signals:
        parts.append(f"\n## Interest signals\n\n{interest_signals}\n")

    content = "\n".join(parts)
    return _apply_entity_links(content, entities)


def _frontmatter(ranked: RankedDigest) -> str:
    return (
        "---\n"
        "type: salience-digest\n"
        f"date: {ranked.date}\n"
        f"bookmarks_processed: {ranked.bookmarks_processed}\n"
        f"window: {ranked.window_start} to {ranked.window_end}\n"
        "---\n"
    )


def _summary_line(ranked: RankedDigest) -> str:
    act_count = len(ranked.act)
    park_count = len(ranked.park)
    learn_count = len(ranked.learn)
    discard_count = len(ranked.discard)
    total = ranked.bookmarks_processed
    return (
        f"> {total} bookmarks processed · "
        f"{act_count} worth your attention · "
        f"{park_count} parked · "
        f"{learn_count} to learn · "
        f"{discard_count} discarded\n"
    )


def _format_brief(
    brief: Brief, entities: dict[str, str], tag_vocab: dict[str, list[str]]
) -> str:
    """Format a full brief for act/learn sections."""
    tags = _map_domains_to_tags(brief.domains, tag_vocab)
    tag_str = " ".join(f"#{t}" for t in tags) if tags else ""

    parts = [
        f"### {brief.title}\n",
        f"**Source:** {brief.source}",
        f"**Domains:** {', '.join(brief.domains)}",
        f"**Intent:** {brief.intent.value}",
    ]

    if brief.is_cluster:
        parts.append(f"**Sources in cluster:** {brief.member_count}")

    parts.append(f"\n#### What this is\n{brief.what_this_is}")
    parts.append(f"\n#### What it means for you\n{brief.what_it_means}")
    parts.append(
        f"\n#### Suggested action\n"
        f"**{brief.suggested_action.value.capitalize()}** – {brief.action_detail}"
    )

    if brief.connections:
        connections_str = " · ".join(brief.connections)
        parts.append(f"\n#### Connections\n{connections_str}")

    if tag_str:
        parts.append(f"\n{tag_str}")

    return "\n".join(parts) + "\n"


def _format_brief_short(brief: Brief) -> str:
    """Format a brief one-liner for park/discard sections."""
    return (
        f"- **{brief.title}** – {brief.what_this_is} "
        f"*({brief.suggested_action.value})*\n"
    )


def _map_domains_to_tags(
    domains: list[str], tag_vocab: dict[str, list[str]]
) -> list[str]:
    """Map bookmark domains to the closest tags from the configured vocabulary."""
    all_tags = []
    for tags in tag_vocab.values():
        all_tags.extend(tags)

    matched: list[str] = []
    for domain in domains:
        domain_words = domain.lower().replace("-", " ").split()
        for tag in all_tags:
            if tag in matched:
                continue
            tag_words = tag.lower().replace("-", " ").split()
            if _words_overlap(domain_words, tag_words):
                matched.append(tag)
    return matched


def _words_overlap(a_words: list[str], b_words: list[str]) -> bool:
    """Check if any word from a shares a stem with any word from b.

    Uses prefix matching (min 4 chars) to handle plural/singular variations.
    """
    for aw in a_words:
        for bw in b_words:
            if aw == bw:
                return True
            # Prefix match for stemming (agent/agents, automate/automation)
            min_len = min(len(aw), len(bw))
            if min_len >= 4 and (aw.startswith(bw[:4]) or bw.startswith(aw[:4])):
                return True
    return False


def _apply_entity_links(content: str, entities: dict[str, str]) -> str:
    """Apply wikilinks for first occurrence of each entity per section.

    Sections are delimited by ## headers. Only links to existing entities
    (no dead links).
    """
    if not entities:
        return content

    sections = re.split(r"(^## .+$)", content, flags=re.MULTILINE)
    result_parts = []

    for section in sections:
        linked_in_section: set[str] = set()

        for slug, display_name in entities.items():
            if slug in linked_in_section:
                continue

            # Match display name (case-insensitive, word boundary)
            pattern = re.compile(
                rf"\b({re.escape(display_name)})\b", re.IGNORECASE
            )
            match = pattern.search(section)
            if match:
                # Replace first occurrence only
                replacement = f"[[{slug}|{display_name}]]"
                section = section[:match.start()] + replacement + section[match.end():]
                linked_in_section.add(slug)

        result_parts.append(section)

    return "".join(result_parts)
