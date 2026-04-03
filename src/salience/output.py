# Vault writing – digest, interest profile, ideas backlog
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from salience.config.models import VaultConfig

logger = logging.getLogger(__name__)


def write_digest(content: str, date: str, config: VaultConfig) -> Path:
    """Write the digest markdown to the vault."""
    output_dir = Path(config.path) / config.salience_output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / f"{date}-digest.md"
    output_path.write_text(content, encoding="utf-8")

    logger.info("Digest written to %s", output_path)
    return output_path


def write_interest_profile(content: str, config: VaultConfig) -> Path:
    """Write the updated interest profile to the vault."""
    output_dir = Path(config.path) / config.salience_output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    profile_path = output_dir / "interest-profile.md"
    profile_path.write_text(content, encoding="utf-8")

    logger.info("Interest profile updated at %s", profile_path)
    return profile_path


def append_ideas(ideas: list[str], config: VaultConfig) -> Path | None:
    """Append ideas to the ideas backlog under a Salience-inspired section."""
    if not ideas:
        return None

    ideas_path = Path(config.path) / config.ideas_file

    # Read existing content or create new
    if ideas_path.exists():
        existing = ideas_path.read_text(encoding="utf-8")
    else:
        ideas_path.parent.mkdir(parents=True, exist_ok=True)
        existing = ""

    # Find or create the Salience-inspired section
    section_header = "## Salience-inspired"
    today = datetime.now().strftime("%Y-%m-%d")

    new_entries = "\n".join(
        f"- [ ] `{today}` — {idea}" for idea in ideas
    )

    if section_header in existing:
        # Append after the section header
        idx = existing.index(section_header) + len(section_header)
        updated = existing[:idx] + f"\n\n{new_entries}" + existing[idx:]
    else:
        # Add the section at the end
        updated = existing.rstrip() + f"\n\n{section_header}\n\n{new_entries}\n"

    ideas_path.write_text(updated, encoding="utf-8")
    logger.info("Appended %d ideas to %s", len(ideas), ideas_path)
    return ideas_path
