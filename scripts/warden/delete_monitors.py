#!/usr/bin/env python3
"""
Delete all monitors and groups from Warden.
"""

import os

import httpx
import typer

from warden.helper import UptimeResponse, configure_log_level, get_logger

log = get_logger(__name__)
app = typer.Typer()


@app.command()
def main(
    host: str = typer.Option("http://localhost:9090", help="Warden base URL"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be deleted without actually deleting"
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompts"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging"),
):
    """Delete all monitors and groups from Warden."""
    configure_log_level(verbose)

    api_key = os.environ.get("WARDEN_API_KEY")
    if not api_key:
        log.error("missing_api_key", message="WARDEN_API_KEY environment variable is required")
        raise typer.Exit(code=1)

    client = httpx.Client(
        base_url=host.rstrip("/"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        timeout=30,
    )

    # Fetch all monitors and groups
    log.info("fetching_monitors_from_warden")
    resp = client.get("/api/uptime")
    resp.raise_for_status()

    uptime_data = UptimeResponse.model_validate(resp.json())

    if not uptime_data.groups:
        log.info("no_data_to_delete")
        raise typer.Exit(code=0)

    monitors_to_delete = []
    groups_to_delete = []

    for group in uptime_data.groups:
        groups_to_delete.append({"id": group.id, "name": group.name})

        for monitor in group.monitors:
            monitors_to_delete.append(
                {"id": monitor.id, "name": monitor.name, "group": group.name}
            )

    log.info(
        "found_items",
        monitors=len(monitors_to_delete),
        groups=len(groups_to_delete),
    )

    if dry_run:
        log.info("dry_run_would_delete", monitors=len(monitors_to_delete), groups=len(groups_to_delete))
        for m in monitors_to_delete:
            log.info("would_delete_monitor", group=m["group"], name=m["name"], id=m["id"])
        for g in groups_to_delete:
            log.info("would_delete_group", name=g["name"], id=g["id"])
        raise typer.Exit(code=0)

    # Confirm deletion
    if not force:
        typer.echo("\n⚠️  This will DELETE:")
        for m in monitors_to_delete[:5]:
            typer.echo(f"   • {m['group']}/{m['name']}")
        if len(monitors_to_delete) > 5:
            typer.echo(f"   ... and {len(monitors_to_delete) - 5} more monitors")
        typer.echo()

        if not typer.confirm(
            f"Are you sure you want to delete {len(monitors_to_delete)} monitors?",
            default=False,
        ):
            log.info("aborted_by_user")
            raise typer.Exit(code=1)

    # Delete monitors
    deleted_monitors = 0
    failed_monitors = 0

    for monitor in monitors_to_delete:
        try:
            resp = client.delete(f"/api/monitors/{monitor['id']}")
            resp.raise_for_status()
            deleted_monitors += 1
            log.info("deleted_monitor", group=monitor["group"], name=monitor["name"])
        except httpx.HTTPStatusError as e:
            failed_monitors += 1
            log.error(
                "failed_to_delete_monitor",
                name=monitor["name"],
                status_code=e.response.status_code,
            )

    # Delete groups
    if not force and groups_to_delete:
        if not typer.confirm(
            f"\nDelete {len(groups_to_delete)} groups?", default=False
        ):
            log.info("skipping_group_deletion")
            raise typer.Exit(code=0)

    deleted_groups = 0
    failed_groups = 0

    for group in groups_to_delete:
        try:
            resp = client.delete(f"/api/groups/{group['id']}")
            resp.raise_for_status()
            deleted_groups += 1
            log.info("deleted_group", name=group["name"])
        except httpx.HTTPStatusError as e:
            failed_groups += 1
            log.error(
                "failed_to_delete_group",
                name=group["name"],
                status_code=e.response.status_code,
            )

    # Summary
    log.info(
        "deletion_complete",
        monitors_deleted=deleted_monitors,
        monitors_total=len(monitors_to_delete),
        monitors_failed=failed_monitors,
        groups_deleted=deleted_groups,
        groups_total=len(groups_to_delete),
        groups_failed=failed_groups,
    )

    client.close()


if __name__ == "__main__":
    app()
