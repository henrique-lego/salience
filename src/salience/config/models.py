# Pydantic configuration models – secrets from env vars, structure from config.yaml
from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class XApiConfig(BaseSettings):
    """X API credentials – loaded from environment variables."""

    bearer_token: str = Field(..., description="X API bearer token")
    client_id: str = Field(..., description="X API client ID")
    client_secret: str = Field(..., description="X API client secret")
    user_id: str = Field(..., description="X API user ID for bookmark owner")

    model_config = {"env_prefix": "X_API_"}


class AnthropicConfig(BaseSettings):
    """Anthropic API credentials – loaded from environment variables."""

    auth_token: str = Field(..., description="Anthropic API key or auth token")
    base_url: str | None = Field(
        default=None, description="Custom base URL for corporate gateways"
    )

    model_config = {"env_prefix": "ANTHROPIC_"}


class VaultConfig(BaseModel):
    """Obsidian vault configuration – loaded from config.yaml."""

    path: Path = Field(..., description="Absolute path to Obsidian vault")
    entity_directories: list[str] = Field(
        default=["people/", "concepts/"],
        description="Directories containing entity notes for wikilink resolution",
    )
    tag_vocabulary: dict[str, list[str]] = Field(
        default_factory=dict, description="Tag vocabulary grouped by category"
    )
    scan_paths: list[str] = Field(
        default_factory=list, description="Glob patterns for context assembly"
    )
    salience_output_dir: str = Field(
        default="salience/", description="Output directory relative to vault"
    )
    ideas_file: str = Field(
        default="claude-code/ideas.md", description="Ideas backlog file relative to vault"
    )


class ModelsConfig(BaseModel):
    """Claude model IDs for each pipeline step – loaded from config.yaml."""

    classify: str = Field(default="claude-haiku-4-5-20251001")
    evaluate_single: str = Field(default="claude-sonnet-4-5-20250929")
    evaluate_cluster: str = Field(default="claude-opus-4-6")
    rank: str = Field(default="claude-opus-4-6")
    interest: str = Field(default="claude-opus-4-6")


class SalienceConfig(BaseModel):
    """Top-level configuration combining env-based secrets and yaml-based structure."""

    x_api: XApiConfig
    anthropic: AnthropicConfig
    vault: VaultConfig
    models: ModelsConfig = Field(default_factory=ModelsConfig)
    processed_ledger_path: Path = Field(default=Path("processed.json"))
