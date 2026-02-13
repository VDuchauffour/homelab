#!/usr/bin/env python3
"""
Discover Kubernetes deployments with HTTP liveness probes and seed them to Warden.
"""

import asyncio
import os
from typing import Optional

import httpx
import typer

from warden.helper import (
    ExistingMonitor,
    KubernetesConfig,
    KubernetesDiscovery,
    Monitor,
    WardenAsyncClient,
    configure_log_level,
    get_logger,
)

log = get_logger(__name__)
app = typer.Typer(
    help="Discover Kubernetes deployments with HTTP liveness probes and register them as Warden monitors"
)


class MonitorSeeder:
    """Orchestrates the seeding of monitors to Warden."""

    def __init__(self, warden_client: WardenAsyncClient):
        self.client = warden_client
        self._group_ids: dict[str, str] = {}
        self.log = get_logger(__name__).bind(component="seeder")

    async def seed(
        self,
        monitors: list[Monitor],
        group_override: Optional[str] = None,
        interval_override: Optional[int] = None,
    ) -> None:
        """
        Seed monitors to Warden using upsert logic (create or update).

        Args:
            monitors: List of monitors to seed
            group_override: Optional group name to use for all monitors
            interval_override: Optional interval to override monitor intervals
        """
        # Fetch existing monitors once at the start
        self.log.info("fetching_existing_monitors")
        try:
            existing_monitors = await self.client.get_existing_monitors()
            self.log.info("found_existing_monitors", count=len(existing_monitors))
        except httpx.HTTPStatusError as e:
            self.log.warning(
                "failed_to_fetch_existing_monitors", status_code=e.response.status_code
            )
            existing_monitors = {}

        by_namespace = self._group_by_namespace(monitors)

        for ns, ns_monitors in by_namespace.items():
            group_name = group_override or ns
            group_id = await self._ensure_group(group_name, existing_monitors)

            if not group_id:
                continue

            await self._upsert_monitors(ns_monitors, group_id, interval_override, existing_monitors)

    def _group_by_namespace(self, monitors: list[Monitor]) -> dict[str, list[Monitor]]:
        """Group monitors by namespace."""
        by_namespace: dict[str, list[Monitor]] = {}
        for monitor in monitors:
            by_namespace.setdefault(monitor.namespace, []).append(monitor)
        return by_namespace

    async def _ensure_group(
        self, group_name: str, existing_monitors: dict[str, ExistingMonitor]
    ) -> Optional[str]:
        """Ensure a group exists, creating it if necessary."""
        if group_name in self._group_ids:
            return self._group_ids[group_name]

        try:
            group_id = await self.client.create_group(group_name)
            self._group_ids[group_name] = group_id
            return group_id
        except httpx.HTTPStatusError as e:
            # Group might already exist (409 Conflict)
            if e.response.status_code == 409:
                self.log.warning(
                    "group_already_exists", group_name=group_name, status_code=409
                )
                # Try to find existing group ID from existing monitors
                for existing in existing_monitors.values():
                    if existing.group_name == group_name:
                        group_id = existing.group_id
                        self._group_ids[group_name] = group_id
                        self.log.info(
                            "using_existing_group",
                            group_name=group_name,
                            group_id=group_id,
                        )
                        return group_id

            self.log.error(
                "failed_to_create_group",
                group_name=group_name,
                status_code=e.response.status_code,
            )
            return None

    async def _upsert_monitors(
        self,
        monitors: list[Monitor],
        group_id: str,
        interval_override: Optional[int],
        existing_monitors: dict[str, ExistingMonitor],
    ) -> None:
        """Create or update monitors in Warden concurrently."""
        tasks = []

        for monitor in monitors:
            interval = interval_override or monitor.interval
            existing = existing_monitors.get(monitor.deployment)

            tasks.append(
                self._upsert_single_monitor(monitor, group_id, interval, existing)
            )

        # Run all upsert operations concurrently
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _upsert_single_monitor(
        self,
        monitor: Monitor,
        group_id: str,
        interval: int,
        existing: Optional[ExistingMonitor],
    ) -> None:
        """Upsert a single monitor."""
        try:
            if existing:
                # Check if anything changed
                if (
                    str(existing.url) == str(monitor.url)
                    and existing.group_id == group_id
                    and existing.interval == interval
                ):
                    self.log.info(
                        "monitor_unchanged",
                        monitor_name=monitor.deployment,
                        action="unchanged",
                    )
                    return

                # Monitor exists but has changes → PUT to update
                await self.client.update_monitor(
                    monitor_id=existing.id,
                    name=monitor.deployment,
                    url=str(monitor.url),
                    group_id=group_id,
                    interval=interval,
                )
            else:
                # Monitor doesn't exist → POST to create
                await self.client.create_monitor(
                    name=monitor.deployment,
                    url=str(monitor.url),
                    group_id=group_id,
                    interval=interval,
                )
        except httpx.HTTPStatusError as e:
            self.log.error(
                "failed_to_upsert_monitor",
                monitor_name=monitor.deployment,
                status_code=e.response.status_code,
                error=str(e),
            )
        except Exception as e:
            self.log.error(
                "unexpected_error",
                monitor_name=monitor.deployment,
                error=str(e),
            )


async def async_main(
    host: str,
    interval: Optional[int],
    group: Optional[str],
    namespace: Optional[str],
    api_key: str,
):
    """Async main logic."""
    # Load Kubernetes configuration
    KubernetesConfig.load()

    # Discover monitors (synchronous K8s API calls)
    discovery = KubernetesDiscovery()
    monitors = discovery.discover_monitors(namespace)

    if not monitors:
        log.warning("no_monitors_found", namespace=namespace or "all")
        return

    # Seed monitors to Warden (async HTTP calls)
    async with WardenAsyncClient(host.rstrip("/"), api_key) as warden_client:
        seeder = MonitorSeeder(warden_client)
        await seeder.seed(monitors, group, interval)
        log.info("seeding_complete")


@app.command()
def main(
    host: str = typer.Option("http://localhost:9090", help="Warden base URL"),
    interval: Optional[int] = typer.Option(
        None, help="Override check interval (seconds)"
    ),
    group: Optional[str] = typer.Option(
        None, help="Group name (default: one group per namespace)"
    ),
    namespace: Optional[str] = typer.Option(None, help="Only scan this namespace"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Print discovered monitors without posting"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable debug logging"
    ),
):
    """Discover Kubernetes deployments with HTTP liveness probes and register them as Warden monitors."""
    configure_log_level(verbose)

    api_key = os.environ.get("WARDEN_API_KEY")
    if not api_key and not dry_run:
        log.error(
            "missing_api_key",
            message="WARDEN_API_KEY environment variable is required",
        )
        raise typer.Exit(code=1)

    # Load Kubernetes configuration
    KubernetesConfig.load()

    # Discover monitors
    discovery = KubernetesDiscovery()
    monitors = discovery.discover_monitors(namespace)

    if not monitors:
        log.warning("no_monitors_found", namespace=namespace or "all")
        raise typer.Exit(code=0)

    # Dry-run: just print discovered monitors
    if dry_run:
        log.info("dry_run_mode", count=len(monitors))
        for m in monitors:
            log.info(
                "discovered_monitor",
                namespace=m.namespace,
                deployment=m.deployment,
                url=str(m.url),
                interval=m.interval,
            )
        raise typer.Exit(code=0)

    # Seed monitors to Warden (async)
    assert api_key is not None  # Guaranteed by check above
    asyncio.run(async_main(host, interval, group, namespace, api_key))


if __name__ == "__main__":
    app()
