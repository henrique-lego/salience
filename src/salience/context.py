# Dynamic context assembly – scan vault and projects, select relevant files per bookmark
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from salience.config.models import VaultConfig
from salience.models import BookmarkCluster, ClassifiedBookmark

logger = logging.getLogger(__name__)

# Max total characters of context per evaluation (~15K tokens ≈ 60K chars)
MAX_CONTEXT_CHARS = 60_000

# Max characters to read from a single file
MAX_FILE_CHARS = 10_000


@dataclass
class FileEntry:
    """A file in the context map with its metadata."""

    path: Path
    title: str
    first_lines: str
    relative_path: str


@dataclass
class ContextMap:
    """Index of vault files available for context assembly."""

    entries: list[FileEntry] = field(default_factory=list)
    entities: dict[str, str] = field(default_factory=dict)  # slug -> display name


def build_context_map(config: VaultConfig) -> ContextMap:
    """Scan the vault once per run, building an index of available files.

    Also builds the entity lookup map for wikilink resolution.
    """
    vault_path = Path(config.path)
    entries: list[FileEntry] = []

    # Scan each configured path pattern
    for pattern in config.scan_paths:
        for file_path in sorted(vault_path.glob(pattern)):
            if not file_path.is_file():
                continue
            entry = _index_file(file_path, vault_path)
            if entry:
                entries.append(entry)

    # Build entity lookup
    entities = _build_entity_lookup(vault_path, config.entity_directories)

    logger.info("Context map built: %d files indexed, %d entities", len(entries), len(entities))
    return ContextMap(entries=entries, entities=entities)


def assemble_context(
    item: ClassifiedBookmark | BookmarkCluster,
    context_map: ContextMap,
) -> str:
    """Select and read relevant files for evaluating a bookmark or cluster.

    Selection is keyword-based: match bookmark domains against file titles and content.
    """
    domains = _get_domains(item)
    if not domains:
        return ""

    # Score each file by domain relevance
    scored: list[tuple[float, FileEntry]] = []
    for entry in context_map.entries:
        score = _relevance_score(domains, entry)
        if score > 0:
            scored.append((score, entry))

    # Sort by score descending, take top files within token budget
    scored.sort(key=lambda x: x[0], reverse=True)

    context_parts: list[str] = []
    total_chars = 0

    for score, entry in scored:
        if total_chars >= MAX_CONTEXT_CHARS:
            break

        content = _read_file(entry.path)
        if not content:
            continue

        # Truncate individual files
        if len(content) > MAX_FILE_CHARS:
            content = content[:MAX_FILE_CHARS] + "\n[...truncated]"

        context_parts.append(f"--- {entry.relative_path} ---\n{content}")
        total_chars += len(content)

    if context_parts:
        logger.debug(
            "Assembled context: %d files, %d chars for domains %s",
            len(context_parts),
            total_chars,
            domains,
        )

    return "\n\n".join(context_parts)


def _get_domains(item: ClassifiedBookmark | BookmarkCluster) -> list[str]:
    """Extract domains from a bookmark or cluster."""
    if isinstance(item, BookmarkCluster):
        return item.shared_domains
    return item.domains


def _index_file(file_path: Path, vault_path: Path) -> FileEntry | None:
    """Read the first few lines of a file to build its index entry."""
    try:
        with open(file_path, encoding="utf-8", errors="ignore") as f:
            lines = []
            for i, line in enumerate(f):
                if i >= 5:
                    break
                lines.append(line.rstrip())

        if not lines:
            return None

        title = lines[0].lstrip("#").strip() if lines else ""
        first_lines = " ".join(lines).lower()
        relative_path = str(file_path.relative_to(vault_path))

        return FileEntry(
            path=file_path,
            title=title,
            first_lines=first_lines,
            relative_path=relative_path,
        )
    except OSError:
        return None


def _build_entity_lookup(vault_path: Path, entity_dirs: list[str]) -> dict[str, str]:
    """Glob entity directories, read first line of each file for display name.

    Returns: {slug: display_name} where slug is the filename without .md extension.
    """
    entities: dict[str, str] = {}

    for dir_name in entity_dirs:
        entity_dir = vault_path / dir_name
        if not entity_dir.exists():
            continue

        for md_file in sorted(entity_dir.glob("*.md")):
            slug = md_file.stem
            try:
                with open(md_file, encoding="utf-8") as f:
                    first_line = f.readline().strip()
                display_name = first_line.lstrip("#").strip()
                if display_name:
                    entities[slug] = display_name
            except OSError:
                continue

    return entities


def _relevance_score(domains: list[str], entry: FileEntry) -> float:
    """Score a file's relevance to the given domains.

    Simple keyword matching against title and first lines.
    """
    score = 0.0
    searchable = f"{entry.title} {entry.first_lines} {entry.relative_path}".lower()

    for domain in domains:
        # Split compound domains (e.g. "agent-architecture" -> ["agent", "architecture"])
        keywords = domain.lower().replace("-", " ").split()
        for keyword in keywords:
            if keyword in searchable:
                score += 1.0

        # Bonus for exact domain match
        if domain.lower() in searchable:
            score += 2.0

    return score


def _read_file(path: Path) -> str:
    """Read file content, returning empty string on failure."""
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""
