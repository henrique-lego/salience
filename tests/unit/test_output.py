# Tests for vault writing operations
from pathlib import Path

from salience.config.models import VaultConfig
from salience.output import append_ideas, write_digest, write_interest_profile


def _make_vault_config(tmp_path: Path) -> VaultConfig:
    vault = tmp_path / "vault"
    vault.mkdir()
    return VaultConfig(
        path=vault,
        salience_output_dir="salience/",
        ideas_file="ideas.md",
    )


class TestWriteDigest:
    def test_creates_file(self, tmp_path: Path) -> None:
        config = _make_vault_config(tmp_path)
        path = write_digest("# Test Digest", "2026-04-03", config)
        assert path.exists()
        assert path.name == "2026-04-03-digest.md"
        assert path.read_text() == "# Test Digest"

    def test_creates_output_dir(self, tmp_path: Path) -> None:
        config = _make_vault_config(tmp_path)
        path = write_digest("content", "2026-04-03", config)
        assert path.parent.exists()
        assert path.parent.name == "salience"


class TestWriteInterestProfile:
    def test_creates_profile(self, tmp_path: Path) -> None:
        config = _make_vault_config(tmp_path)
        path = write_interest_profile("# Interest Profile\n\nData here", config)
        assert path.exists()
        assert path.name == "interest-profile.md"

    def test_overwrites_existing(self, tmp_path: Path) -> None:
        config = _make_vault_config(tmp_path)
        write_interest_profile("version 1", config)
        path = write_interest_profile("version 2", config)
        assert path.read_text() == "version 2"


class TestAppendIdeas:
    def test_creates_new_file(self, tmp_path: Path) -> None:
        config = _make_vault_config(tmp_path)
        path = append_ideas(["Build a CLI tool #claude-code"], config)
        assert path is not None
        content = path.read_text()
        assert "## Salience-inspired" in content
        assert "Build a CLI tool #claude-code" in content

    def test_appends_to_existing_section(self, tmp_path: Path) -> None:
        config = _make_vault_config(tmp_path)
        ideas_file = Path(config.path) / config.ideas_file
        ideas_file.write_text("# Ideas\n\n## Salience-inspired\n\n- [ ] Old idea\n")

        append_ideas(["New idea #agents"], config)
        content = ideas_file.read_text()
        assert "Old idea" in content
        assert "New idea #agents" in content

    def test_returns_none_for_empty(self, tmp_path: Path) -> None:
        config = _make_vault_config(tmp_path)
        assert append_ideas([], config) is None
