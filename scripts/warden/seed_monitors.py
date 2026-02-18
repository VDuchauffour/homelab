#!/usr/bin/env python3
"""
Discover Kubernetes deployments with HTTP liveness probes and seed them to Warden.
"""

import asyncio
import os
from pathlib import Path
from typing import Optional
from kubernetes import client

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
    def __init__(self, warden_client: WardenAsyncClient):
        self.client = warden_client
        self._group_ids: dict[str, str] = {}
        self.log = get_logger(__name__).bind(component="seeder")

    async def seed(
        self,
        monitors: list[Monitor],
        group_override: Optional[str] = None,
        interval_override: Optional[int] = None,
        cleanup: bool = False,
        allowed_namespaces: Optional[list[str]] = None,
    ) -> None:
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

            await self._upsert_monitors(
                ns_monitors, group_id, interval_override, existing_monitors
            )

        if cleanup and allowed_namespaces is not None:
            await self._cleanup_unmanaged_monitors(
                existing_monitors, monitors, allowed_namespaces
            )

    def _group_by_namespace(self, monitors: list[Monitor]) -> dict[str, list[Monitor]]:
        by_namespace: dict[str, list[Monitor]] = {}
        for monitor in monitors:
            by_namespace.setdefault(monitor.namespace, []).append(monitor)
        return by_namespace

    async def _ensure_group(
        self, group_name: str, existing_monitors: dict[str, ExistingMonitor]
    ) -> Optional[str]:
        if group_name in self._group_ids:
            return self._group_ids[group_name]

        try:
            group_id = await self.client.create_group(group_name)
            self._group_ids[group_name] = group_id
            return group_id
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 409:
                self.log.warning(
                    "group_already_exists", group_name=group_name, status_code=409
                )
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
        tasks = []

        for monitor in monitors:
            interval = interval_override or monitor.interval
            existing = existing_monitors.get(monitor.deployment)

            tasks.append(
                self._upsert_single_monitor(monitor, group_id, interval, existing)
            )

        await asyncio.gather(*tasks, return_exceptions=True)

    async def _upsert_single_monitor(
        self,
        monitor: Monitor,
        group_id: str,
        interval: int,
        existing: Optional[ExistingMonitor],
    ) -> None:
        try:
            if existing:
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

                await self.client.update_monitor(
                    monitor_id=existing.id,
                    name=monitor.deployment,
                    url=str(monitor.url),
                    group_id=group_id,
                    interval=interval,
                )
            else:
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

    async def _cleanup_unmanaged_monitors(
        self,
        existing_monitors: dict[str, ExistingMonitor],
        target_monitors: list[Monitor],
        allowed_namespaces: list[str],
    ) -> None:
        target_names = {m.deployment for m in target_monitors}
        allowed_ns_set = set(allowed_namespaces)

        monitors_to_delete = []
        groups_to_delete = set()

        for name, monitor in existing_monitors.items():
            if monitor.group_name in allowed_ns_set:
                if name in target_names:
                    continue

            monitors_to_delete.append(
                (monitor.id, name, monitor.group_name, monitor.group_id)
            )
            self.log.info(
                "cleanup_will_delete_monitor",
                monitor=name,
                group=monitor.group_name,
                reason="not in target list"
                if monitor.group_name in allowed_ns_set
                else "group not in allowed namespaces",
            )

        if not monitors_to_delete:
            self.log.info("no_monitors_to_cleanup")
            return

        self.log.info("cleaning_up_monitors", count=len(monitors_to_delete))

        for monitor_id, monitor_name, group_name, group_id in monitors_to_delete:
            try:
                await self.client.delete_monitor(monitor_id)
                self.log.info("deleted_monitor", monitor=monitor_name, group=group_name)
                groups_to_delete.add((group_id, group_name))
            except httpx.HTTPStatusError as e:
                self.log.error(
                    "failed_to_delete_monitor",
                    monitor=monitor_name,
                    status_code=e.response.status_code,
                )

        for group_id, group_name in groups_to_delete:
            remaining_monitors = [
                m
                for m in existing_monitors.values()
                if m.group_id == group_id and m.name in target_names
            ]

            if not remaining_monitors:
                try:
                    await self.client.delete_group(group_id)
                    self.log.info("deleted_empty_group", group=group_name)
                except httpx.HTTPStatusError as e:
                    self.log.error(
                        "failed_to_delete_group",
                        group=group_name,
                        status_code=e.response.status_code,
                    )


async def async_main(
    host: str,
    interval: Optional[int],
    group: Optional[str],
    namespace: Optional[str],
    namespace_list: Optional[list[str]],
    api_key: str,
    cleanup: bool = False,
):
    KubernetesConfig.load()

    discovery = KubernetesDiscovery()
    monitors = discovery.discover_monitors(
        namespace, namespace_list, default_interval=interval or 30
    )

    if not monitors:
        filter_desc = namespace or (
            f"{len(namespace_list)} namespaces" if namespace_list else "all"
        )
        log.warning("no_monitors_found", namespace=filter_desc)
        return

    async with WardenAsyncClient(host.rstrip("/"), api_key) as warden_client:
        seeder = MonitorSeeder(warden_client)
        await seeder.seed(
            monitors,
            group,
            interval,
            cleanup=cleanup,
            allowed_namespaces=namespace_list,
        )
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
    namespaces: Optional[list[str]] = typer.Option(
        None, "--namespaces", help="List of namespaces to scan (comma-separated)"
    ),
    apps_only: bool = typer.Option(
        False,
        "--apps-only",
        help="Only monitor apps from kubernetes/apps/ (user-facing)",
    ),
    cleanup: bool = typer.Option(
        False,
        "--cleanup",
        help="Remove monitors/groups not in the discovered list (use with --apps-only)",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Print discovered monitors without posting"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging"),
):
    configure_log_level(verbose)

    api_key = os.environ.get("WARDEN_API_KEY")
    if not api_key and not dry_run:
        log.error(
            "missing_api_key",
            message="WARDEN_API_KEY environment variable is required",
        )
        raise typer.Exit(code=1)

    namespace_list = None
    if apps_only:
        apps_dir = Path(__file__).parent.parent.parent / "kubernetes" / "apps"
        exclude_namespaces = {
            "kube-system",
        }

        if apps_dir.exists():
            namespace_set = set()
            for item in apps_dir.iterdir():
                if item.is_dir() and not item.name.startswith("."):
                    helmfile = item / "helmfile.yaml"
                    if helmfile.exists():
                        try:
                            with open(helmfile, "r") as f:
                                for line in f:
                                    if "namespace:" in line:
                                        ns = (
                                            line.split("namespace:")[1]
                                            .strip()
                                            .strip("\"'")
                                        )
                                        if ns and ns not in exclude_namespaces:
                                            namespace_set.add(ns)
                                        break
                        except Exception as e:
                            log.warning(
                                "failed_to_read_helmfile",
                                path=str(helmfile),
                                error=str(e),
                            )

            KubernetesConfig.load()

            core_v1 = client.CoreV1Api()
            try:
                cluster_namespaces = core_v1.list_namespace()
                deployed_namespaces = {
                    ns.metadata.name for ns in cluster_namespaces.items
                }

                namespace_list = sorted(list(namespace_set & deployed_namespaces))
                skipped = namespace_set - deployed_namespaces

                log.info(
                    "apps_only_mode",
                    namespaces=namespace_list,
                    discovered_from=str(apps_dir),
                    deployed=len(namespace_list),
                    skipped=len(skipped),
                )
                if skipped:
                    log.info(
                        "skipped_undeployed_namespaces",
                        namespaces=sorted(list(skipped)),
                    )
            except Exception as e:
                log.warning("failed_to_check_deployed_namespaces", error=str(e))
                namespace_list = sorted(list(namespace_set))
        else:
            log.warning("apps_directory_not_found", path=str(apps_dir))
            namespace_list = []
    elif namespaces:
        namespace_list = namespaces

    KubernetesConfig.load()

    if namespace or namespace_list:
        core_v1 = client.CoreV1Api()
        try:
            cluster_namespaces = core_v1.list_namespace()
            deployed = {ns.metadata.name for ns in cluster_namespaces.items}

            if namespace and namespace not in deployed:
                log.error(
                    "namespace_not_found",
                    namespace=namespace,
                    available=sorted(deployed),
                )
                raise typer.Exit(code=1)

            if namespace_list and not apps_only:
                invalid = set(namespace_list) - deployed
                if invalid:
                    log.error(
                        "namespaces_not_found",
                        invalid=sorted(invalid),
                        available=sorted(deployed),
                    )
                    raise typer.Exit(code=1)
        except typer.Exit:
            raise
        except Exception as e:
            log.warning("failed_to_validate_namespaces", error=str(e))

    discovery = KubernetesDiscovery()
    monitors = discovery.discover_monitors(
        namespace, namespace_list, default_interval=interval or 30
    )

    if not monitors:
        filter_desc = namespace or (
            f"{len(namespace_list)} namespaces" if namespace_list else "all"
        )
        log.warning("no_monitors_found", namespace=filter_desc)
        raise typer.Exit(code=0)

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

    if cleanup and not apps_only and not namespace_list:
        log.error(
            "cleanup_requires_scope",
            message="--cleanup requires either --apps-only or --namespaces to define allowed scope",
        )
        raise typer.Exit(code=1)

    assert api_key is not None
    asyncio.run(
        async_main(host, interval, group, namespace, namespace_list, api_key, cleanup)
    )


if __name__ == "__main__":
    app()
