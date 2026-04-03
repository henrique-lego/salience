# Content resolution – follow URLs, reconstruct threads, extract article text
from __future__ import annotations

import hashlib
import logging
import re

import httpx

from salience.models import ContentSource, RawBookmark, ResolvedBookmark

logger = logging.getLogger(__name__)

# Minimum word count for content to be considered substantial
THIN_CONTENT_THRESHOLD = 200

# Timeout for HTTP requests
REQUEST_TIMEOUT = 15.0


async def resolve_bookmarks(bookmarks: list[RawBookmark]) -> list[ResolvedBookmark]:
    """Resolve content for a list of bookmarks concurrently."""
    async with httpx.AsyncClient(
        timeout=REQUEST_TIMEOUT,
        follow_redirects=True,
        headers={"User-Agent": "Salience/0.1"},
    ) as client:
        results = []
        for bookmark in bookmarks:
            resolved = await _resolve_single(bookmark, client)
            results.append(resolved)
        return results


async def _resolve_single(
    bookmark: RawBookmark, client: httpx.AsyncClient
) -> ResolvedBookmark:
    """Resolve content for a single bookmark."""
    # Priority: URL content > tweet text
    if bookmark.urls:
        return await _resolve_url(bookmark, client)

    return _resolve_tweet(bookmark)


async def _resolve_url(
    bookmark: RawBookmark, client: httpx.AsyncClient
) -> ResolvedBookmark:
    """Fetch and extract content from the first URL in the bookmark."""
    url = bookmark.urls[0]
    logger.debug("Resolving URL: %s", url)

    try:
        response = await client.get(url)
        response.raise_for_status()
        content = _extract_text(response.text)

        word_count = len(content.split())
        if word_count < THIN_CONTENT_THRESHOLD:
            logger.warning("Thin content from %s (%d words)", url, word_count)

        return ResolvedBookmark(
            raw=bookmark,
            resolved_content=content,
            content_source=ContentSource.URL,
            resolved_url=str(response.url),
            content_hash=_hash_content(content),
        )
    except (httpx.HTTPError, httpx.TimeoutException) as e:
        logger.warning("Failed to fetch %s: %s. Falling back to tweet text.", url, e)
        return _resolve_tweet(bookmark, resolved_url=url)


def _resolve_tweet(
    bookmark: RawBookmark, resolved_url: str | None = None
) -> ResolvedBookmark:
    """Use the tweet text as the resolved content."""
    return ResolvedBookmark(
        raw=bookmark,
        resolved_content=bookmark.text,
        content_source=ContentSource.TWEET,
        resolved_url=resolved_url,
        content_hash=_hash_content(bookmark.text),
    )


def _extract_text(html: str) -> str:
    """Extract readable text from HTML content.

    Simple extraction – strips tags and collapses whitespace. No heavy dependencies.
    """
    # Remove script and style blocks
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)

    # Remove HTML comments
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)

    # Convert common block elements to newlines
    text = re.sub(r"<(?:p|div|h[1-6]|li|br|tr)[^>]*>", "\n", text, flags=re.IGNORECASE)

    # Strip remaining tags
    text = re.sub(r"<[^>]+>", "", text)

    # Decode common HTML entities
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&quot;", '"')
    text = text.replace("&#39;", "'")
    text = text.replace("&nbsp;", " ")

    # Collapse whitespace
    text = re.sub(r"\n\s*\n", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)

    return text.strip()


def _hash_content(content: str) -> str:
    """Generate a SHA-256 hash of the first 1000 characters for dedup."""
    normalized = content[:1000].lower().strip()
    return hashlib.sha256(normalized.encode()).hexdigest()
