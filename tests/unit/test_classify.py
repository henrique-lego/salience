# Tests for classification parsing logic
import json
from datetime import datetime

from salience.classify import _parse_classification
from salience.models import (
    ContentSource,
    Depth,
    Intent,
    RawBookmark,
    ResolvedBookmark,
)


def _classify_entry(
    bid: str, summary: str, domains: list[str] | None = None
) -> dict[str, object]:
    return {
        "id": bid,
        "domains": domains or ["ai"],
        "intent": "learn",
        "depth": "surface",
        "summary": summary,
    }


def _make_resolved(bookmark_id: str, text: str = "test") -> ResolvedBookmark:
    return ResolvedBookmark(
        raw=RawBookmark(
            id=bookmark_id,
            text=text,
            author_username="user",
            author_name="User",
            created_at=datetime(2026, 4, 1),
        ),
        resolved_content="Resolved content here",
        content_source=ContentSource.TWEET,
        content_hash="abc123",
    )


class TestParseClassification:
    def test_parses_valid_json(self) -> None:
        bookmarks = [_make_resolved("100"), _make_resolved("200")]
        raw = json.dumps([
            {
                "id": "100",
                "domains": ["agent-architecture", "memory-systems"],
                "intent": "challenge",
                "depth": "substantial",
                "summary": "A memory consolidation approach",
            },
            {
                "id": "200",
                "domains": ["workflow-automation"],
                "intent": "adopt",
                "depth": "surface",
                "summary": "Quick automation tip",
            },
        ])

        results = _parse_classification(raw, bookmarks)
        assert len(results) == 2

        first = results[0]
        assert first.domains == ["agent-architecture", "memory-systems"]
        assert first.intent == Intent.CHALLENGE
        assert first.depth == Depth.SUBSTANTIAL
        assert first.summary == "A memory consolidation approach"

        second = results[1]
        assert second.intent == Intent.ADOPT
        assert second.depth == Depth.SURFACE

    def test_parses_json_in_code_block(self) -> None:
        bookmarks = [_make_resolved("100")]
        item = _classify_entry("100", "test")
        raw = f"```json\n{json.dumps([item])}\n```"

        results = _parse_classification(raw, bookmarks)
        assert len(results) == 1
        assert results[0].domains == ["ai"]

    def test_handles_missing_bookmarks(self) -> None:
        bookmarks = [_make_resolved("100")]
        raw = json.dumps([
            _classify_entry("100", "ok"),
            _classify_entry("999", "not found", domains=["unknown"]),
        ])

        results = _parse_classification(raw, bookmarks)
        # Should return the valid one, skip the unknown
        assert len(results) == 1
        assert results[0].resolved.raw.id == "100"

    def test_fills_defaults_for_unclassified(self) -> None:
        bookmarks = [_make_resolved("100"), _make_resolved("200")]
        # Only classify one of the two
        raw = json.dumps([_classify_entry("100", "classified")])

        results = _parse_classification(raw, bookmarks)
        assert len(results) == 2

        unclassified = [r for r in results if r.resolved.raw.id == "200"][0]
        assert unclassified.intent == Intent.LEARN
        assert unclassified.depth == Depth.SURFACE
        assert unclassified.domains == []
