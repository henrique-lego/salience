# Tests for bookmark fetching and deduplication logic
import json
from datetime import datetime
from pathlib import Path

from salience.harvest import _is_twitter_url, _load_ledger, mark_processed, save_ledger
from salience.models import RawBookmark


class TestLedger:
    def test_load_empty_ledger(self, tmp_path: Path) -> None:
        ledger = _load_ledger(tmp_path / "nonexistent.json")
        assert ledger == {}

    def test_load_existing_ledger(self, tmp_path: Path) -> None:
        path = tmp_path / "processed.json"
        data = {"123": {"processed_at": "2026-04-01T00:00:00", "digest_date": "2026-04-01"}}
        path.write_text(json.dumps(data))

        ledger = _load_ledger(path)
        assert "123" in ledger
        assert ledger["123"]["digest_date"] == "2026-04-01"

    def test_save_and_reload(self, tmp_path: Path) -> None:
        path = tmp_path / "processed.json"
        ledger = {"456": {"processed_at": "2026-04-02T12:00:00", "digest_date": "2026-04-02"}}

        save_ledger(ledger, path)
        reloaded = _load_ledger(path)
        assert reloaded == ledger


class TestTwitterUrlDetection:
    def test_twitter_urls(self) -> None:
        assert _is_twitter_url("https://twitter.com/user/status/123")
        assert _is_twitter_url("https://x.com/user/status/123")
        assert _is_twitter_url("https://t.co/abc123")

    def test_non_twitter_urls(self) -> None:
        assert not _is_twitter_url("https://example.com/article")
        assert not _is_twitter_url("https://blog.anthropic.com/post")
        assert not _is_twitter_url("https://github.com/repo")


class TestMarkProcessed:
    def test_marks_bookmarks(self, tmp_path: Path) -> None:
        from unittest.mock import MagicMock

        config = MagicMock()
        config.processed_ledger_path = tmp_path / "processed.json"

        bookmarks = [
            RawBookmark(
                id="100",
                text="test",
                author_username="user",
                author_name="User",
                created_at=datetime(2026, 4, 1),
            ),
            RawBookmark(
                id="200",
                text="test2",
                author_username="user2",
                author_name="User 2",
                created_at=datetime(2026, 4, 1),
            ),
        ]

        mark_processed(bookmarks, "2026-04-03", config)

        ledger = _load_ledger(config.processed_ledger_path)
        assert "100" in ledger
        assert "200" in ledger
        assert ledger["100"]["digest_date"] == "2026-04-03"

    def test_appends_to_existing_ledger(self, tmp_path: Path) -> None:
        from unittest.mock import MagicMock

        path = tmp_path / "processed.json"
        path.write_text(json.dumps({"50": {"processed_at": "old", "digest_date": "old"}}))

        config = MagicMock()
        config.processed_ledger_path = path

        bookmarks = [
            RawBookmark(
                id="60",
                text="new",
                author_username="u",
                author_name="U",
                created_at=datetime(2026, 4, 2),
            ),
        ]

        mark_processed(bookmarks, "2026-04-03", config)

        ledger = _load_ledger(path)
        assert "50" in ledger
        assert "60" in ledger
