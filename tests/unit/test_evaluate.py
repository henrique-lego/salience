# Tests for evaluation brief parsing and model routing
import json

from salience.evaluate import _parse_brief
from salience.models import SuggestedAction


class TestParseBrief:
    def test_parses_valid_json(self) -> None:
        raw = json.dumps({
            "title": "Memory Consolidation Alternative",
            "what_this_is": "Proposes weekly consolidation over monthly.",
            "what_it_means": "Challenges your hippocampal-replay cycle.",
            "suggested_action": "evaluate",
            "action_detail": "Test with 2-week cycle on personal vault.",
            "connections": ["synapse-os", "hippocampal-replay"],
        })
        brief = _parse_brief(raw)
        assert brief.title == "Memory Consolidation Alternative"
        assert brief.suggested_action == SuggestedAction.EVALUATE
        assert "synapse-os" in brief.connections
        assert not brief.is_cluster

    def test_parses_cluster_brief(self) -> None:
        raw = json.dumps({
            "title": "Agent Evaluation Approaches",
            "what_this_is": "Three takes on agent evaluation.",
            "what_it_means": "Converge on structured benchmarks.",
            "suggested_action": "adopt",
            "action_detail": "Adopt the benchmark framework.",
            "connections": ["mc-ai-claude-foundation"],
            "member_count": 3,
        })
        brief = _parse_brief(raw, is_cluster=True)
        assert brief.is_cluster
        assert brief.member_count == 3

    def test_parses_json_in_code_block(self) -> None:
        data = {
            "title": "Test",
            "what_this_is": "t",
            "what_it_means": "t",
            "suggested_action": "park",
            "action_detail": "t",
            "connections": [],
        }
        raw = f"```json\n{json.dumps(data)}\n```"
        brief = _parse_brief(raw)
        assert brief.title == "Test"
        assert brief.suggested_action == SuggestedAction.PARK

    def test_defaults_for_missing_fields(self) -> None:
        raw = json.dumps({"title": "Minimal"})
        brief = _parse_brief(raw)
        assert brief.title == "Minimal"
        assert brief.suggested_action == SuggestedAction.PARK
        assert brief.what_this_is == ""
