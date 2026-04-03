# Tests for context assembly and entity lookup
from pathlib import Path

from salience.config.models import VaultConfig
from salience.context import (
    FileEntry,
    _build_entity_lookup,
    _index_file,
    _relevance_score,
    build_context_map,
)


def _create_vault(tmp_path: Path) -> Path:
    """Create a minimal vault structure for testing."""
    vault = tmp_path / "vault"
    vault.mkdir()

    # Entity dirs
    (vault / "people").mkdir()
    (vault / "people" / "alice.md").write_text("# Alice Smith\n\nSenior engineer\n")
    (vault / "people" / "bob.md").write_text("# Bob Jones\n\nProduct manager\n")

    (vault / "concepts").mkdir()
    (vault / "concepts" / "agent-governance.md").write_text("# Agent Governance\n\nDefinition\n")

    # Content files
    (vault / "notes").mkdir()
    (vault / "notes" / "agents-article.md").write_text(
        "# AI Agent Architecture\n\nArticle about agent patterns and memory systems\n"
    )
    (vault / "notes" / "cooking-recipe.md").write_text(
        "# Pasta Recipe\n\nHow to make carbonara\n"
    )
    (vault / "notes" / "claude-code-setup.md").write_text(
        "# Claude Code Configuration\n\nSetup guide for claude code and plugins\n"
    )

    return vault


class TestIndexFile:
    def test_indexes_markdown_file(self, tmp_path: Path) -> None:
        f = tmp_path / "test.md"
        f.write_text("# My Title\n\nSome content about agents\n")

        entry = _index_file(f, tmp_path)
        assert entry is not None
        assert entry.title == "My Title"
        assert "agents" in entry.first_lines
        assert entry.relative_path == "test.md"

    def test_skips_empty_file(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.md"
        f.write_text("")

        entry = _index_file(f, tmp_path)
        assert entry is None


class TestEntityLookup:
    def test_builds_entity_map(self, tmp_path: Path) -> None:
        vault = _create_vault(tmp_path)
        entities = _build_entity_lookup(vault, ["people/", "concepts/"])

        assert "alice" in entities
        assert entities["alice"] == "Alice Smith"
        assert "bob" in entities
        assert entities["bob"] == "Bob Jones"
        assert "agent-governance" in entities
        assert entities["agent-governance"] == "Agent Governance"

    def test_handles_missing_directory(self, tmp_path: Path) -> None:
        vault = tmp_path / "vault"
        vault.mkdir()
        entities = _build_entity_lookup(vault, ["nonexistent/"])
        assert entities == {}


class TestRelevanceScore:
    def test_scores_domain_match(self) -> None:
        entry = FileEntry(
            path=Path("/vault/test.md"),
            title="AI Agent Architecture",
            first_lines="article about agent patterns and memory systems",
            relative_path="notes/agents-article.md",
        )
        score = _relevance_score(["agent-architecture"], entry)
        assert score > 0

    def test_zero_for_unrelated(self) -> None:
        entry = FileEntry(
            path=Path("/vault/cooking.md"),
            title="Pasta Recipe",
            first_lines="how to make carbonara",
            relative_path="notes/cooking.md",
        )
        score = _relevance_score(["agent-architecture"], entry)
        assert score == 0

    def test_higher_for_exact_domain(self) -> None:
        entry = FileEntry(
            path=Path("/vault/test.md"),
            title="Agent Architecture Deep Dive",
            first_lines="agent-architecture patterns for production",
            relative_path="notes/agent-architecture.md",
        )
        score_exact = _relevance_score(["agent-architecture"], entry)
        score_partial = _relevance_score(["agent"], entry)
        assert score_exact > score_partial


class TestBuildContextMap:
    def test_builds_map_from_vault(self, tmp_path: Path) -> None:
        vault = _create_vault(tmp_path)
        config = VaultConfig(
            path=vault,
            entity_directories=["people/", "concepts/"],
            scan_paths=["notes/*.md"],
        )

        context_map = build_context_map(config)
        assert len(context_map.entries) == 3  # 3 notes files
        assert "alice" in context_map.entities
        assert "agent-governance" in context_map.entities
