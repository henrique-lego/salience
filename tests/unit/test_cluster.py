# Tests for deduplication and thematic clustering
from datetime import datetime

from salience.cluster import (
    _content_dedup,
    _normalize_url,
    _thematic_cluster,
    cluster_bookmarks,
)
from salience.models import (
    BookmarkCluster,
    ClassifiedBookmark,
    ContentSource,
    Depth,
    Intent,
    RawBookmark,
    ResolvedBookmark,
)


def _make_classified(
    bookmark_id: str,
    url: str | None = None,
    content_hash: str = "",
    domains: list[str] | None = None,
    text: str = "test",
) -> ClassifiedBookmark:
    raw = RawBookmark(
        id=bookmark_id,
        text=text,
        author_username="user",
        author_name="User",
        created_at=datetime(2026, 4, 1),
    )
    resolved = ResolvedBookmark(
        raw=raw,
        resolved_content="content",
        content_source=ContentSource.URL if url else ContentSource.TWEET,
        resolved_url=url,
        content_hash=content_hash or f"hash_{bookmark_id}",
    )
    return ClassifiedBookmark(
        resolved=resolved,
        domains=domains or [],
        intent=Intent.LEARN,
        depth=Depth.SUBSTANTIAL,
        summary="test summary",
    )


class TestNormalizeUrl:
    def test_strips_query_params(self) -> None:
        assert _normalize_url("https://example.com/article?utm_source=twitter") == (
            "https://example.com/article"
        )

    def test_strips_www(self) -> None:
        assert _normalize_url("https://www.example.com/page") == (
            "https://example.com/page"
        )

    def test_strips_trailing_slash(self) -> None:
        assert _normalize_url("https://example.com/page/") == (
            "https://example.com/page"
        )

    def test_strips_fragment(self) -> None:
        assert _normalize_url("https://example.com/page#section") == (
            "https://example.com/page"
        )

    def test_different_tracking_same_article(self) -> None:
        url_a = "https://blog.anthropic.com/post?ref=twitter&utm=abc"
        url_b = "https://blog.anthropic.com/post?source=newsletter"
        assert _normalize_url(url_a) == _normalize_url(url_b)

    def test_merges_with_tracking_params(self) -> None:
        bookmarks = [
            _make_classified("1", url="https://example.com/article?utm_source=tw1", text="Take A"),
            _make_classified("2", url="https://example.com/article?ref=tw2", text="Take B"),
        ]
        result = _content_dedup(bookmarks)
        assert len(result) == 1
        assert len(result[0].framings) == 2


class TestContentDedup:
    def test_no_duplicates(self) -> None:
        bookmarks = [
            _make_classified("1", url="https://a.com"),
            _make_classified("2", url="https://b.com"),
        ]
        result = _content_dedup(bookmarks)
        assert len(result) == 2

    def test_same_url_merges(self) -> None:
        bookmarks = [
            _make_classified("1", url="https://same.com", text="First take"),
            _make_classified("2", url="https://same.com", text="Second take"),
        ]
        result = _content_dedup(bookmarks)
        assert len(result) == 1
        assert len(result[0].framings) == 2
        assert "First take" in result[0].framings
        assert "Second take" in result[0].framings

    def test_same_hash_merges(self) -> None:
        bookmarks = [
            _make_classified("1", content_hash="same_hash", text="View A"),
            _make_classified("2", content_hash="same_hash", text="View B"),
        ]
        result = _content_dedup(bookmarks)
        assert len(result) == 1
        assert len(result[0].framings) == 2

    def test_merges_domains(self) -> None:
        bookmarks = [
            _make_classified("1", url="https://same.com", domains=["ai", "agents"]),
            _make_classified("2", url="https://same.com", domains=["agents", "memory"]),
        ]
        result = _content_dedup(bookmarks)
        assert len(result) == 1
        # Should have all unique domains
        assert set(result[0].domains) == {"ai", "agents", "memory"}


class TestThematicCluster:
    def test_no_clustering_when_different_domains(self) -> None:
        bookmarks = [
            _make_classified("1", domains=["ai"]),
            _make_classified("2", domains=["cooking"]),
        ]
        clusters, remaining = _thematic_cluster(bookmarks)
        assert len(clusters) == 0
        assert len(remaining) == 2

    def test_clusters_on_shared_domains(self) -> None:
        bookmarks = [
            _make_classified("1", domains=["ai", "agents", "memory"]),
            _make_classified("2", domains=["ai", "agents", "evaluation"]),
        ]
        clusters, remaining = _thematic_cluster(bookmarks)
        assert len(clusters) == 1
        assert len(remaining) == 0
        assert set(clusters[0].shared_domains) == {"ai", "agents"}
        assert len(clusters[0].members) == 2

    def test_single_shared_domain_not_enough(self) -> None:
        bookmarks = [
            _make_classified("1", domains=["ai", "memory"]),
            _make_classified("2", domains=["ai", "cooking"]),
        ]
        clusters, remaining = _thematic_cluster(bookmarks)
        assert len(clusters) == 0
        assert len(remaining) == 2


class TestClusterBookmarks:
    def test_empty_input(self) -> None:
        assert cluster_bookmarks([]) == []

    def test_mixed_dedup_and_cluster(self) -> None:
        bookmarks = [
            # These two share a URL – should merge
            _make_classified("1", url="https://same.com", domains=["ai", "agents"]),
            _make_classified("2", url="https://same.com", domains=["ai"]),
            # This one is independent
            _make_classified("3", url="https://other.com", domains=["cooking"]),
        ]
        result = cluster_bookmarks(bookmarks)
        # After dedup: 2 items (merged + independent)
        # No thematic clustering (different domains)
        assert len(result) == 2

    def test_returns_clusters_and_individuals(self) -> None:
        bookmarks = [
            _make_classified("1", domains=["ai", "agents", "memory"]),
            _make_classified("2", domains=["ai", "agents", "evaluation"]),
            _make_classified("3", domains=["cooking", "recipes"]),
        ]
        result = cluster_bookmarks(bookmarks)
        clusters = [r for r in result if isinstance(r, BookmarkCluster)]
        individuals = [r for r in result if isinstance(r, ClassifiedBookmark)]
        assert len(clusters) == 1
        assert len(individuals) == 1
