# Configuration loader – merges config.yaml (structure) with env vars (secrets)
import logging
from pathlib import Path

import yaml

from salience.config.models import (
    AnthropicConfig,
    ModelsConfig,
    SalienceConfig,
    VaultConfig,
    XApiConfig,
)

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = Path("config.yaml")


def load_config(config_path: Path = DEFAULT_CONFIG_PATH) -> SalienceConfig:
    """Load and validate the full Salience configuration.

    Secrets come from environment variables (via pydantic-settings).
    Structure comes from config.yaml.
    """
    if not config_path.exists():
        raise FileNotFoundError(
            f"Config file not found: {config_path}. "
            "Copy config.yaml.example to config.yaml and fill in your values."
        )

    with open(config_path) as f:
        raw = yaml.safe_load(f)

    vault = VaultConfig(**raw.get("vault", {}))
    models = ModelsConfig(**raw.get("models", {}))
    processed_ledger_path = Path(raw.get("processed_ledger_path", "processed.json"))

    # Secrets auto-loaded from env vars
    x_api = XApiConfig()  # type: ignore[call-arg]
    anthropic = AnthropicConfig()  # type: ignore[call-arg]

    config = SalienceConfig(
        x_api=x_api,
        anthropic=anthropic,
        vault=vault,
        models=models,
        processed_ledger_path=processed_ledger_path,
    )

    logger.info("Configuration loaded: vault=%s, models=%s", vault.path, models.classify)
    return config
