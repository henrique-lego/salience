# Three-tier deduplication and thematic clustering
from __future__ import annotations

import logging
from collections import defaultdict
from urllib.parse import urlparse, urlunparse

from salience.models import BookmarkCluster, ClassifiedBookmark

logger = logging.getLogger(__name__)

# Minimum shared domains for thematic clustering
MIN_SHARED_DOMAINS = 2


def cluster_bookmarks(
    bookmarks: list[ClassifiedBookmark],
) -> list[ClassifiedBookmark | BookmarkCluster]:
    """Group bookmarks by content overlap and thematic similarity.

    Three passes:
    1. Content dedup: merge bookmarks with same resolved URL or content hash
    2. Thematic clustering: group remaining by shared domains
    3. Pass-through: return unclustered bookmarks individually
    """
    if not bookmarks:
        return []

    # Pass 1: content dedup
    deduplicated = _content_dedup(bookmarks)
    logger.info("After content dedup: %d items (from %d)", len(deduplicated), len(bookmarks))

    # Pass 2: thematic clustering
    clusters, remaining = _thematic_cluster(deduplicated)
    logger.info(
        "After thematic clustering: %d clusters + %d individual", len(clusters), len(remaining)
    )

    # Combine: clusters + individual items
    result: list[ClassifiedBookmark | BookmarkCluster] = []
    result.extend(clusters)
    result.extend(remaining)
    return result


def _normalize_url(url: str) -> str:
    """Normalize a URL for dedup comparison.

    Strips query params (tracking, UTM), fragments, www prefix,
    and trailing slashes so different share links to the same
    article match as identical.
    """
    parsed = urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.rstrip("/")
    return urlunparse(("https", host, path, "", "", ""))


def _content_dedup(bookmarks: list[ClassifiedBookmark]) -> list[ClassifiedBookmark]:
    """Merge bookmarks that resolve to the same underlying content.

    Groups by normalized URL, then by content hash for URL-less bookmarks.
    Merged items preserve all unique framings (tweet commentary).
    """
    # Group by normalized URL
    by_url: dict[str, list[ClassifiedBookmark]] = defaultdict(list)
    no_url: list[ClassifiedBookmark] = []

    for b in bookmarks:
        url = b.resolved.resolved_url
        if url:
            by_url[_normalize_url(url)].append(b)
        else:
            no_url.append(b)

    # Within URL groups, merge duplicates
    merged: list[ClassifiedBookmark] = []
    for url, group in by_url.items():
        if len(group) == 1:
            merged.append(group[0])
        else:
            merged.append(_merge_group(group))

    # For items without URLs, group by content hash
    by_hash: dict[str, list[ClassifiedBookmark]] = defaultdict(list)
    for b in no_url:
        by_hash[b.resolved.content_hash].append(b)

    for content_hash, group in by_hash.items():
        if len(group) == 1:
            merged.append(group[0])
        else:
            merged.append(_merge_group(group))

    return merged


def _merge_group(group: list[ClassifiedBookmark]) -> ClassifiedBookmark:
    """Merge multiple bookmarks into one, preserving unique framings."""
    primary = group[0]

    # Collect unique tweet texts as framings
    framings = []
    for b in group:
        tweet_text = b.resolved.raw.text
        if tweet_text not in framings:
            framings.append(tweet_text)

    # Merge domains from all members
    all_domains: list[str] = []
    seen_domains: set[str] = set()
    for b in group:
        for d in b.domains:
            if d not in seen_domains:
                all_domains.append(d)
                seen_domains.add(d)

    merged = ClassifiedBookmark(
        resolved=primary.resolved,
        domains=all_domains,
        intent=primary.intent,
        depth=primary.depth,
        summary=primary.summary,
        framings=framings,
    )

    logger.debug(
        "Merged %d bookmarks into one (URL: %s)", len(group), primary.resolved.resolved_url
    )
    return merged


def _thematic_cluster(
    bookmarks: list[ClassifiedBookmark],
) -> tuple[list[BookmarkCluster], list[ClassifiedBookmark]]:
    """Group bookmarks with significant domain overlap into clusters."""
    used: set[str] = set()
    clusters: list[BookmarkCluster] = []

    # Compare all pairs for domain overlap
    for i, a in enumerate(bookmarks):
        if a.resolved.raw.id in used:
            continue
        group = [a]
        shared = set(a.domains)

        for b in bookmarks[i + 1 :]:
            if b.resolved.raw.id in used:
                continue
            overlap = shared & set(b.domains)
            if len(overlap) >= MIN_SHARED_DOMAINS:
                group.append(b)
                shared = shared & set(b.domains)

        if len(group) >= 2:
            cluster = BookmarkCluster(
                members=group,
                shared_domains=sorted(shared),
                cluster_title=" + ".join(sorted(shared)[:3]),
            )
            clusters.append(cluster)
            for b in group:
                used.add(b.resolved.raw.id)

    # Remaining unclustered bookmarks
    remaining = [b for b in bookmarks if b.resolved.raw.id not in used]
    return clusters, remaining
