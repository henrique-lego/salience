# Interest pattern tracking using Claude Opus
from __future__ import annotations

import json
import logging
from pathlib import Path

import anthropic

from salience.config.models import SalienceConfig
from salience.models import Brief

logger = logging.getLogger(__name__)

INTEREST_PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "interest.md"


async def update_interest_profile(
    briefs: list[Brief],
    digest_date: str,
    config: SalienceConfig,
) -> tuple[str, str]:
    """Update the interest profile and generate signals for the digest.

    Returns: (updated_profile_markdown, signals_markdown)
    """
    system_prompt = INTEREST_PROMPT_PATH.read_text()
    current_profile = _load_current_profile(config)
    user_message = _build_interest_message(briefs, current_profile, digest_date)

    logger.info("Updating interest profile with %s", config.models.interest)

    client = anthropic.AsyncAnthropic(
        api_key=config.anthropic.auth_token,
        base_url=config.anthropic.base_url,
    )

    response = await client.messages.create(
        model=config.models.interest,
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )

    return _parse_interest_response(response.content[0].text)


def _load_current_profile(config: SalienceConfig) -> str:
    """Load the existing interest profile from the vault, if any."""
    vault_path = Path(config.vault.path)
    profile_path = vault_path / config.vault.salience_output_dir / "interest-profile.md"

    if profile_path.exists():
        return profile_path.read_text(encoding="utf-8")
    return "No existing interest profile. This is the first run."


def _build_interest_message(
    briefs: list[Brief], current_profile: str, digest_date: str
) -> str:
    """Build the user message for interest tracking."""
    parts = [f"## Current Interest Profile\n{current_profile}"]
    parts.append(f"\n## New Briefs (digest date: {digest_date})\n")

    for i, brief in enumerate(briefs):
        parts.append(
            f"### Brief {i}: {brief.title}\n"
            f"- Domains: {', '.join(brief.domains)}\n"
            f"- Intent: {brief.intent.value}\n"
            f"- Action: {brief.suggested_action.value}\n"
            f"- Detail: {brief.action_detail}"
        )

    return "\n\n".join(parts)


def _parse_interest_response(raw_text: str) -> tuple[str, str]:
    """Parse the interest tracking response.

    Returns: (profile_markdown, signals_markdown)
    """
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        if "```json" in raw_text:
            start = raw_text.index("```json") + 7
            end = raw_text.index("```", start)
            data = json.loads(raw_text[start:end])
        else:
            logger.error("Failed to parse interest response")
            return ("", "")

    profile = data.get("profile_markdown", "")
    signals = data.get("signals_markdown", "")
    return (profile, signals)
