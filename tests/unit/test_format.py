# Tests for digest formatting and entity linking
from salience.format import (
    _apply_entity_links,
    _format_brief_short,
    _map_domains_to_tags,
    format_digest,
)
from salience.models import Brief, Intent, RankedDigest, SuggestedAction


def _make_brief(title: str = "Test Brief", action: str = "park") -> Brief:
    return Brief(
        title=title,
        source="@author · 2026-04-01",
        domains=["agent-architecture", "memory-systems"],
        intent=Intent.CHALLENGE,
        what_this_is="A new approach to memory consolidation.",
        what_it_means="Challenges the monthly cycle in synapse-os.",
        suggested_action=SuggestedAction(action),
        action_detail="Evaluate against current setup.",
        connections=["synapse-os", "hippocampal-replay"],
    )


class TestEntityLinking:
    def test_links_first_occurrence(self) -> None:
        entities = {"alice": "Alice Smith"}
        content = "Alice Smith did this. Alice Smith did that."
        result = _apply_entity_links(content, entities)
        assert "[[alice|Alice Smith]]" in result
        # Should only link first occurrence
        assert result.count("[[alice|Alice Smith]]") == 1

    def test_no_dead_links(self) -> None:
        entities = {"alice": "Alice Smith"}
        content = "Bob Jones was here."
        result = _apply_entity_links(content, entities)
        assert "[[" not in result

    def test_empty_entities(self) -> None:
        content = "Some content"
        result = _apply_entity_links(content, {})
        assert result == content

    def test_links_per_section(self) -> None:
        entities = {"alice": "Alice Smith"}
        content = "## Section 1\nAlice Smith here.\n## Section 2\nAlice Smith again."
        result = _apply_entity_links(content, entities)
        # Should link once per section
        assert result.count("[[alice|Alice Smith]]") == 2


class TestTagMapping:
    def test_maps_domains_to_tags(self) -> None:
        vocab = {"work": ["automation", "agents"], "personal": ["finance"]}
        tags = _map_domains_to_tags(["agent-architecture"], vocab)
        assert "agents" in tags

    def test_no_match_returns_empty(self) -> None:
        vocab = {"work": ["automation"]}
        tags = _map_domains_to_tags(["cooking"], vocab)
        assert tags == []


class TestFormatDigest:
    def test_produces_valid_markdown(self) -> None:
        ranked = RankedDigest(
            date="2026-04-03",
            bookmarks_processed=3,
            window_start="2026-03-27",
            window_end="2026-04-03",
            act=[_make_brief("Top Brief", "adopt")],
            park=[_make_brief("Parked Brief", "park")],
            learn=[],
            discard=[],
        )
        result = format_digest(ranked, "Some signals", {}, {})
        assert "# Salience Digest" in result
        assert "## Act on these" in result
        assert "## Park" in result
        assert "## Interest signals" in result
        assert "type: salience-digest" in result

    def test_skips_empty_sections(self) -> None:
        ranked = RankedDigest(
            date="2026-04-03",
            bookmarks_processed=1,
            window_start="2026-04-03",
            window_end="2026-04-03",
            act=[_make_brief("Only Brief", "adopt")],
        )
        result = format_digest(ranked, "", {}, {})
        assert "## Act on these" in result
        assert "## Park" not in result
        assert "## Learning backlog" not in result
        assert "## Discarded" not in result
        assert "## Interest signals" not in result


class TestFormatBriefShort:
    def test_one_liner(self) -> None:
        brief = _make_brief("Quick Take", "park")
        result = _format_brief_short(brief)
        assert "Quick Take" in result
        assert "park" in result
