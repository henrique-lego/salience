# Shared data models for the Salience pipeline
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ContentSource(str, Enum):
    """How the bookmark's content was resolved."""

    URL = "url"
    THREAD = "thread"
    TWEET = "tweet"


class Intent(str, Enum):
    """Why the user likely bookmarked this."""

    CHALLENGE = "challenge"
    ADOPT = "adopt"
    LEARN = "learn"
    INSPIRE = "inspire"


class Depth(str, Enum):
    """Whether the underlying content is substantial or surface-level."""

    SUBSTANTIAL = "substantial"
    SURFACE = "surface"


class SuggestedAction(str, Enum):
    """What to do with this bookmark."""

    ADOPT = "adopt"
    EVALUATE = "evaluate"
    LEARN = "learn"
    PARK = "park"
    DISCARD = "discard"


@dataclass
class RawBookmark:
    """A bookmark as fetched from the X API, before content resolution."""

    id: str
    text: str
    author_username: str
    author_name: str
    created_at: datetime
    urls: list[str] = field(default_factory=list)
    referenced_tweet_ids: list[str] = field(default_factory=list)
    like_count: int = 0
    retweet_count: int = 0


@dataclass
class ResolvedBookmark:
    """A bookmark with its underlying content resolved."""

    raw: RawBookmark
    resolved_content: str
    content_source: ContentSource
    resolved_url: str | None = None
    content_hash: str = ""


@dataclass
class ClassifiedBookmark:
    """A resolved bookmark with classification metadata."""

    resolved: ResolvedBookmark
    domains: list[str] = field(default_factory=list)
    intent: Intent = Intent.LEARN
    depth: Depth = Depth.SURFACE
    summary: str = ""
    framings: list[str] = field(default_factory=list)


@dataclass
class BookmarkCluster:
    """A group of thematically related bookmarks evaluated together."""

    members: list[ClassifiedBookmark]
    shared_domains: list[str] = field(default_factory=list)
    cluster_title: str = ""


@dataclass
class Brief:
    """Evaluation output for a single bookmark or cluster."""

    title: str
    source: str
    domains: list[str]
    intent: Intent
    what_this_is: str
    what_it_means: str
    suggested_action: SuggestedAction
    action_detail: str
    connections: list[str] = field(default_factory=list)
    is_cluster: bool = False
    member_count: int = 1


@dataclass
class RankedDigest:
    """The final ranked digest with grouped briefs."""

    date: str
    bookmarks_processed: int
    window_start: str
    window_end: str
    act: list[Brief] = field(default_factory=list)
    park: list[Brief] = field(default_factory=list)
    learn: list[Brief] = field(default_factory=list)
    discard: list[Brief] = field(default_factory=list)
