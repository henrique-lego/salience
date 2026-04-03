# Tests for configuration loading and validation
from pathlib import Path

import pytest
import yaml

from salience.config.models import AnthropicConfig, ModelsConfig, VaultConfig, XApiConfig


class TestXApiConfig:
    def test_loads_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("X_API_BEARER_TOKEN", "test-bearer")
        monkeypatch.setenv("X_API_CLIENT_ID", "test-client-id")
        monkeypatch.setenv("X_API_CLIENT_SECRET", "test-secret")
        monkeypatch.setenv("X_API_USER_ID", "12345")

        config = XApiConfig()  # type: ignore[call-arg]
        assert config.bearer_token == "test-bearer"
        assert config.client_id == "test-client-id"
        assert config.client_secret == "test-secret"
        assert config.user_id == "12345"

    def test_missing_env_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("X_API_BEARER_TOKEN", raising=False)
        monkeypatch.delenv("X_API_CLIENT_ID", raising=False)
        monkeypatch.delenv("X_API_CLIENT_SECRET", raising=False)
        monkeypatch.delenv("X_API_USER_ID", raising=False)

        with pytest.raises(Exception):
            XApiConfig()  # type: ignore[call-arg]


class TestAnthropicConfig:
    def test_loads_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "sk-test")
        monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)

        config = AnthropicConfig()  # type: ignore[call-arg]
        assert config.auth_token == "sk-test"
        assert config.base_url is None

    def test_with_base_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "sk-test")
        monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://gateway.example.com/claude")

        config = AnthropicConfig()  # type: ignore[call-arg]
        assert config.base_url == "https://gateway.example.com/claude"


class TestVaultConfig:
    def test_defaults(self) -> None:
        config = VaultConfig(path=Path("/tmp/vault"))
        assert config.entity_directories == ["people/", "concepts/"]
        assert config.salience_output_dir == "salience/"
        assert config.ideas_file == "claude-code/ideas.md"

    def test_custom_values(self) -> None:
        config = VaultConfig(
            path=Path("/my/vault"),
            entity_directories=["people/", "concepts/", "companies/"],
            tag_vocabulary={"work": ["ai", "data"]},
            scan_paths=["notes/**/*.md"],
        )
        assert len(config.entity_directories) == 3
        assert config.tag_vocabulary["work"] == ["ai", "data"]


class TestModelsConfig:
    def test_defaults(self) -> None:
        config = ModelsConfig()
        assert "haiku" in config.classify
        assert "sonnet" in config.evaluate_single
        assert "opus" in config.evaluate_cluster
        assert "opus" in config.rank
        assert "opus" in config.interest

    def test_override(self) -> None:
        config = ModelsConfig(
            classify="anthropic.claude-haiku-4-5-20251001-v1:0",
            evaluate_single="anthropic.claude-sonnet-4-5-20250929-v1:0",
        )
        assert "anthropic." in config.classify
        assert "anthropic." in config.evaluate_single


class TestConfigLoader:
    def test_load_from_yaml(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("X_API_BEARER_TOKEN", "bearer")
        monkeypatch.setenv("X_API_CLIENT_ID", "client-id")
        monkeypatch.setenv("X_API_CLIENT_SECRET", "secret")
        monkeypatch.setenv("X_API_USER_ID", "123")
        monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "sk-test")

        config_data = {
            "vault": {
                "path": str(tmp_path / "vault"),
                "entity_directories": ["people/"],
                "scan_paths": ["**/*.md"],
            },
            "models": {"classify": "custom-haiku"},
            "processed_ledger_path": str(tmp_path / "processed.json"),
        }
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(config_data))

        from salience.config.loader import load_config

        config = load_config(config_file)
        assert config.vault.path == tmp_path / "vault"
        assert config.models.classify == "custom-haiku"
        assert config.x_api.bearer_token == "bearer"
        assert config.anthropic.auth_token == "sk-test"

    def test_missing_config_file_raises(self) -> None:
        from salience.config.loader import load_config

        with pytest.raises(FileNotFoundError, match="Config file not found"):
            load_config(Path("/nonexistent/config.yaml"))
