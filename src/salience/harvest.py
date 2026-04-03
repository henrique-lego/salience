# Bookmark fetching from X API v2 with identity deduplication
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

import tweepy

from salience.auth import get_valid_access_token
from salience.config.models import SalienceConfig, XApiConfig
from salience.models import RawBookmark

logger = logging.getLogger(__name__)


def _load_ledger(path: Path) -> dict[str, dict[str, str]]:
    """Load processed bookmark IDs from the ledger file."""
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def save_ledger(ledger: dict[str, dict[str, str]], path: Path) -> None:
    """Write the processed ledger back to disk."""
    with open(path, "w") as f:
        json.dump(ledger, f, indent=2)


def _build_client(x_api: XApiConfig) -> tweepy.Client:
    """Create a tweepy Client with OAuth 2.0 user context for bookmark access."""
    access_token = get_valid_access_token(x_api.client_id)
    return tweepy.Client(
        access_token,
        wait_on_rate_limit=True,
    )


def _parse_bookmark(tweet: tweepy.Tweet, users_by_id: dict[str, tweepy.User]) -> RawBookmark:
    """Convert a tweepy Tweet object into a RawBookmark."""
    author = users_by_id.get(str(tweet.author_id))
    urls: list[str] = []
    if tweet.entities and "urls" in tweet.entities:
        for url_entity in tweet.entities["urls"]:
            expanded = url_entity.get("expanded_url", url_entity.get("url", ""))
            # Skip X/Twitter self-referencing URLs (quote tweets, etc.)
            if expanded and not _is_twitter_url(expanded):
                urls.append(expanded)

    referenced_ids: list[str] = []
    if tweet.referenced_tweets:
        for ref in tweet.referenced_tweets:
            referenced_ids.append(str(ref.id))

    return RawBookmark(
        id=str(tweet.id),
        text=tweet.text,
        author_username=author.username if author else "unknown",
        author_name=author.name if author else "unknown",
        created_at=tweet.created_at or datetime.now(),
        urls=urls,
        referenced_tweet_ids=referenced_ids,
        like_count=tweet.public_metrics.get("like_count", 0) if tweet.public_metrics else 0,
        retweet_count=(
            tweet.public_metrics.get("retweet_count", 0) if tweet.public_metrics else 0
        ),
    )


def _is_twitter_url(url: str) -> bool:
    """Check if a URL points to X/Twitter itself."""
    return any(domain in url for domain in ["twitter.com", "x.com", "t.co"])


def fetch_bookmarks(
    config: SalienceConfig,
    since: datetime | None = None,
) -> list[RawBookmark]:
    """Fetch new bookmarks from X API, skipping already-processed ones.

    Returns only bookmarks not present in the processed ledger.
    Optionally filters by date if `since` is provided.
    """
    client = _build_client(config.x_api)
    ledger = _load_ledger(config.processed_ledger_path)

    bookmarks: list[RawBookmark] = []
    users_by_id: dict[str, tweepy.User] = {}
    pagination_token: str | None = None

    logger.info("Fetching bookmarks for user %s", config.x_api.user_id)

    while True:
        response = client.get_bookmarks(
            max_results=100,
            pagination_token=pagination_token,
            tweet_fields=["created_at", "entities", "referenced_tweets", "public_metrics"],
            user_fields=["username", "name"],
            expansions=["author_id"],
        )

        if not response.data:
            break

        # Build user lookup from includes
        if response.includes and "users" in response.includes:
            for user in response.includes["users"]:
                users_by_id[str(user.id)] = user

        for tweet in response.data:
            tweet_id = str(tweet.id)

            # Identity dedup: skip already-processed bookmarks
            if tweet_id in ledger:
                logger.debug("Skipping already-processed bookmark %s", tweet_id)
                continue

            bookmark = _parse_bookmark(tweet, users_by_id)

            # Date filter if requested
            if since and bookmark.created_at < since:
                continue

            bookmarks.append(bookmark)

        # Pagination
        meta = response.meta or {}
        pagination_token = meta.get("next_token")
        if not pagination_token:
            break

    logger.info(
        "Fetched %d new bookmarks (skipped %d already processed)", len(bookmarks), len(ledger)
    )
    return bookmarks


def mark_processed(
    bookmarks: list[RawBookmark],
    digest_date: str,
    config: SalienceConfig,
) -> None:
    """Add bookmarks to the processed ledger."""
    ledger = _load_ledger(config.processed_ledger_path)
    for bookmark in bookmarks:
        ledger[bookmark.id] = {
            "processed_at": datetime.now().isoformat(),
            "digest_date": digest_date,
        }
    save_ledger(ledger, config.processed_ledger_path)
    logger.info("Marked %d bookmarks as processed", len(bookmarks))
