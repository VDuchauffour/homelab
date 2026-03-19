#!/usr/bin/env python3
"""
Remove missing (ghost) items from the Jellyfin library by triggering a library
scan. Jellyfin's internal scan uses DeleteFileLocation=false, which safely
removes only the database entries without touching files on disk.

WARNING: Do NOT use the DELETE /Items/{id} API — it deletes actual media files.
"""

import os

import typer

from jellyfin.helper import (
    JellyfinClient,
    configure_log_level,
    get_logger,
)

log = get_logger(__name__)
app = typer.Typer(
    help="Remove missing (ghost) items from Jellyfin library via library scan"
)


@app.command()
def main(
    host: str = typer.Option("http://jellyfin.home.arpa", help="Jellyfin base URL"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="List missing items without triggering cleanup"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging"),
):
    configure_log_level(verbose)

    api_key = os.environ.get("JELLYFIN_API_KEY")
    if not api_key:
        log.error(
            "missing_api_key",
            message="JELLYFIN_API_KEY environment variable is required",
        )
        raise typer.Exit(code=1)

    client = JellyfinClient(host.rstrip("/"), api_key)

    try:
        items = client.get_missing_items()
    except Exception as e:
        log.error("failed_to_fetch_missing_items", error=str(e))
        raise typer.Exit(code=1)

    if not items:
        log.info("no_missing_items")
        raise typer.Exit(code=0)

    summary = client.summarize_by_folder(items)
    log.info("missing_items_found", total=len(items))
    for entry in summary:
        log.info("folder_summary", folder=entry.folder, count=entry.count)

    if dry_run:
        log.info("dry_run_mode", total=len(items))
        for item in items:
            log.info(
                "missing_item",
                name=item.name,
                type=item.type,
                path=item.path or "(none)",
                item_id=item.id,
            )
        raise typer.Exit(code=0)

    client.refresh_library()
    log.info(
        "cleanup_triggered",
        total=len(items),
        message="Library scan started. Jellyfin will remove missing entries "
        "from the database without deleting files on disk.",
    )

    client.close()


if __name__ == "__main__":
    app()
