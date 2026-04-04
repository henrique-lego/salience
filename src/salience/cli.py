# CLI entry point – three commands: run, digest, reprocess
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console

from salience.config import load_config
from salience.config.models import SalienceConfig

app = typer.Typer(
    name="salience",
    help="Personal intelligence tool – evaluate X bookmarks against your context.",
    no_args_is_help=True,
)
console = Console()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)


async def _run_pipeline(
    config: SalienceConfig,
    since: datetime | None = None,
    dry_run: bool = False,
    interactive: bool = True,
    limit: int | None = None,
    skip_backlog: bool = False,
) -> None:
    """Execute the full Salience pipeline."""
    from salience.classify import classify_bookmarks
    from salience.cluster import cluster_bookmarks
    from salience.context import assemble_context, build_context_map
    from salience.evaluate import _get_item_id, evaluate_all
    from salience.format import format_digest
    from salience.harvest import fetch_bookmarks, mark_processed
    from salience.interest import update_interest_profile
    from salience.output import write_digest, write_interest_profile
    from salience.rank import rank_briefs
    from salience.resolve import resolve_bookmarks

    today = datetime.now().strftime("%Y-%m-%d")

    # 1. Harvest
    console.print("\n[bold]1/8[/bold] Harvesting bookmarks...")
    raw_bookmarks = fetch_bookmarks(config, since=since)
    if not raw_bookmarks:
        console.print("[yellow]No new bookmarks found. Nothing to process.[/yellow]")
        return
    if limit and len(raw_bookmarks) > limit:
        backlog = raw_bookmarks[limit:]
        raw_bookmarks = raw_bookmarks[:limit]
        console.print(
            f"  Found {len(raw_bookmarks) + len(backlog)} new bookmarks, "
            f"processing {len(raw_bookmarks)}"
        )
        if skip_backlog and backlog and not dry_run:
            mark_processed(backlog, today, config)
            console.print(
                f"  Skipped {len(backlog)} older bookmarks (marked as seen)"
            )
    else:
        console.print(f"  Found {len(raw_bookmarks)} new bookmarks")

    # 2. Resolve
    console.print("[bold]2/8[/bold] Resolving content...")
    resolved = await resolve_bookmarks(raw_bookmarks)
    console.print(f"  Resolved {len(resolved)} bookmarks")

    # 3. Classify
    console.print("[bold]3/8[/bold] Classifying bookmarks...")
    classified = await classify_bookmarks(resolved, config)
    console.print(f"  Classified {len(classified)} bookmarks")

    # 4. Cluster
    console.print("[bold]4/8[/bold] Clustering...")
    items = cluster_bookmarks(classified)
    cluster_count = sum(1 for i in items if hasattr(i, "members"))
    individual_count = len(items) - cluster_count
    console.print(f"  {cluster_count} clusters + {individual_count} individual")

    # 5. Assemble context
    console.print("[bold]5/8[/bold] Assembling context...")
    context_map = build_context_map(config.vault)
    contexts = {}
    for item in items:
        item_id = _get_item_id(item)
        contexts[item_id] = assemble_context(item, context_map)
    console.print(f"  Context assembled for {len(items)} items")

    # 6. Evaluate
    console.print("[bold]6/8[/bold] Evaluating...")
    briefs = await evaluate_all(items, contexts, config)
    console.print(f"  Generated {len(briefs)} briefs")

    # 7. Rank
    console.print("[bold]7/8[/bold] Ranking...")
    ranked = await rank_briefs(briefs, today, config)
    console.print(
        f"  Act: {len(ranked.act)} · Park: {len(ranked.park)} · "
        f"Learn: {len(ranked.learn)} · Discard: {len(ranked.discard)}"
    )

    # 8. Interest tracking
    console.print("[bold]8/8[/bold] Updating interest profile...")
    profile_md, signals_md = await update_interest_profile(briefs, today, config)

    # Format digest
    digest_content = format_digest(
        ranked, signals_md, context_map.entities, config.vault.tag_vocabulary
    )

    if dry_run:
        console.print("\n[bold]--- Digest Preview ---[/bold]\n")
        console.print(digest_content)
        console.print("\n[dim]Dry run – nothing written to vault.[/dim]")
        return

    if interactive:
        console.print("\n[bold]--- Digest Preview ---[/bold]\n")
        console.print(digest_content)
        confirm = typer.confirm("\nWrite digest to vault?", default=True)
        if not confirm:
            console.print("[dim]Aborted – nothing written.[/dim]")
            return

    # Write outputs
    digest_path = write_digest(digest_content, today, config.vault)
    console.print(f"  Digest: {digest_path}")

    if profile_md:
        profile_path = write_interest_profile(profile_md, config.vault)
        console.print(f"  Interest profile: {profile_path}")

    mark_processed(raw_bookmarks, today, config)
    console.print(f"  Ledger updated: {len(raw_bookmarks)} bookmarks marked")

    console.print("\n[bold green]Done.[/bold green]")


@app.command()
def auth(
    config_path: Annotated[
        Path,
        typer.Option("--config", help="Path to config.yaml"),
    ] = Path("config.yaml"),
) -> None:
    """Authorize Salience with your X account (one-time setup)."""
    from salience.auth import authorize

    config = load_config(config_path)
    console.print("[bold]Salience[/bold] – X authorization (OAuth 2.0 PKCE)")
    console.print("Opening browser for X authorization...")
    console.print("[dim]Authorize the app and you'll be redirected back.[/dim]\n")

    tokens = authorize(config.x_api.client_id)
    console.print("\n[bold green]Authorized.[/bold green] Tokens saved to tokens.json")
    console.print(f"Access token scope: {tokens.get('scope', 'unknown')}")


@app.command()
def run(
    since: Annotated[
        Optional[datetime],
        typer.Option(help="Process bookmarks since this date (ISO format)"),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview without writing to vault"),
    ] = False,
    limit: Annotated[
        Optional[int],
        typer.Option(help="Max bookmarks to process (useful for testing)"),
    ] = None,
    skip_backlog: Annotated[
        bool,
        typer.Option("--skip-backlog", help="Mark older bookmarks as seen without processing"),
    ] = False,
    config_path: Annotated[
        Path,
        typer.Option("--config", help="Path to config.yaml"),
    ] = Path("config.yaml"),
) -> None:
    """Interactive mode – evaluate bookmarks and confirm before writing."""
    config = load_config(config_path)
    console.print(f"[bold]Salience[/bold] – interactive mode (dry_run={dry_run})")
    console.print(f"Vault: {config.vault.path}")
    asyncio.run(
        _run_pipeline(
            config,
            since=since,
            dry_run=dry_run,
            interactive=True,
            limit=limit,
            skip_backlog=skip_backlog,
        )
    )


@app.command()
def digest(
    since: Annotated[
        Optional[datetime],
        typer.Option(help="Process bookmarks since this date (ISO format)"),
    ] = None,
    limit: Annotated[
        Optional[int],
        typer.Option(help="Max bookmarks to process"),
    ] = None,
    skip_backlog: Annotated[
        bool,
        typer.Option("--skip-backlog", help="Mark older bookmarks as seen without processing"),
    ] = False,
    config_path: Annotated[
        Path,
        typer.Option("--config", help="Path to config.yaml"),
    ] = Path("config.yaml"),
) -> None:
    """Scheduled mode – evaluate and write digest without confirmation."""
    config = load_config(config_path)
    console.print("[bold]Salience[/bold] – digest mode")
    asyncio.run(
        _run_pipeline(
            config,
            since=since,
            dry_run=False,
            interactive=False,
            limit=limit,
            skip_backlog=skip_backlog,
        )
    )


@app.command()
def reprocess(
    date: Annotated[
        str, typer.Argument(help="Date of the batch to reprocess (YYYY-MM-DD)")
    ],
    config_path: Annotated[
        Path,
        typer.Option("--config", help="Path to config.yaml"),
    ] = Path("config.yaml"),
) -> None:
    """Re-evaluate a previous batch with current context."""
    _config = load_config(config_path)  # validate config even though reprocess is not yet wired
    console.print(f"[bold]Salience[/bold] – reprocess mode for {date}")
    console.print("[dim]Reprocess not yet implemented.[/dim]")
