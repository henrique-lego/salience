# Tests for content resolution and text extraction
import pytest

from salience.models import ContentSource, RawBookmark
from salience.resolve import _extract_text, _hash_content, _resolve_tweet


class TestExtractText:
    def test_strips_html_tags(self) -> None:
        html = "<p>Hello <strong>world</strong></p>"
        text = _extract_text(html)
        assert "Hello" in text
        assert "world" in text
        assert "<" not in text

    def test_removes_scripts_and_styles(self) -> None:
        html = """
        <html>
        <head><style>body { color: red; }</style></head>
        <body>
        <script>alert('hi')</script>
        <p>Visible content</p>
        </body>
        </html>
        """
        text = _extract_text(html)
        assert "Visible content" in text
        assert "alert" not in text
        assert "color: red" not in text

    def test_decodes_html_entities(self) -> None:
        html = "<p>A &amp; B &lt; C &gt; D &quot;E&quot; F&#39;s</p>"
        text = _extract_text(html)
        assert "A & B" in text
        assert "< C >" in text
        assert '"E"' in text
        assert "F's" in text

    def test_collapses_whitespace(self) -> None:
        html = "<p>Line one</p>   \n\n\n   <p>Line two</p>"
        text = _extract_text(html)
        assert "Line one" in text
        assert "Line two" in text
        # Should not have excessive blank lines
        assert "\n\n\n" not in text

    def test_empty_html(self) -> None:
        assert _extract_text("") == ""
        assert _extract_text("<div></div>") == ""


class TestHashContent:
    def test_consistent_hash(self) -> None:
        h1 = _hash_content("Hello world")
        h2 = _hash_content("Hello world")
        assert h1 == h2

    def test_case_insensitive(self) -> None:
        h1 = _hash_content("Hello World")
        h2 = _hash_content("hello world")
        assert h1 == h2

    def test_truncates_to_1000_chars(self) -> None:
        long_text = "a" * 2000
        short_text = "a" * 1000
        assert _hash_content(long_text) == _hash_content(short_text)

    def test_different_content_different_hash(self) -> None:
        h1 = _hash_content("Content about AI agents")
        h2 = _hash_content("Content about home automation")
        assert h1 != h2


class TestResolveTweet:
    def test_uses_tweet_text(self) -> None:
        bookmark = RawBookmark(
            id="1",
            text="This is a great insight about agents",
            author_username="author",
            author_name="Author",
            created_at=pytest.importorskip("datetime").datetime(2026, 4, 1),
        )
        resolved = _resolve_tweet(bookmark)
        assert resolved.resolved_content == bookmark.text
        assert resolved.content_source == ContentSource.TWEET
        assert resolved.resolved_url is None
        assert resolved.content_hash != ""

    def test_preserves_url_on_fallback(self) -> None:
        from datetime import datetime

        bookmark = RawBookmark(
            id="2",
            text="Check this out",
            author_username="author",
            author_name="Author",
            created_at=datetime(2026, 4, 1),
        )
        resolved = _resolve_tweet(bookmark, resolved_url="https://failed.example.com")
        assert resolved.resolved_url == "https://failed.example.com"
        assert resolved.content_source == ContentSource.TWEET
