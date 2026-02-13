"""Shared helper functions and classes for Warden scripts."""

from typing import Optional

import httpx
import structlog
from kubernetes import client, config
from pydantic import BaseModel, Field, HttpUrl

# Configure structlog
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO level
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=False,
)


def get_logger(name: str = __name__) -> structlog.BoundLogger:
    """Get a configured structlog logger."""
    return structlog.get_logger(name)


def configure_log_level(verbose: bool = False):
    """Configure structlog log level."""
    level = 10 if verbose else 20  # DEBUG if verbose else INFO
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(level)
    )


# Pydantic Models
class Monitor(BaseModel):
    """Represents a discovered monitor from Kubernetes."""

    model_config = {"frozen": True}

    deployment: str = Field(..., description="Deployment name")
    namespace: str = Field(..., description="Kubernetes namespace")
    url: HttpUrl = Field(..., description="Health check URL")
    interval: int = Field(..., ge=1, description="Check interval in seconds")


class ExistingMonitor(BaseModel):
    """Represents an existing monitor from Warden API."""

    id: str
    name: str
    url: HttpUrl
    group_id: str = Field(..., alias="groupId")
    group_name: str = Field(..., alias="groupName")
    interval: int


class GroupResponse(BaseModel):
    """Response from /api/groups endpoint."""

    id: str
    name: str


class MonitorResponse(BaseModel):
    """Monitor data from /api/uptime endpoint."""

    id: str
    name: str
    url: HttpUrl
    interval: int
    status: str
    active: bool


class GroupWithMonitors(BaseModel):
    """Group with monitors from /api/uptime endpoint."""

    id: str
    name: str
    monitors: list[MonitorResponse]


class UptimeResponse(BaseModel):
    """Response from /api/uptime endpoint."""

    groups: Optional[list[GroupWithMonitors]] = None


# Kubernetes Utilities
class KubernetesConfig:
    """Handles Kubernetes configuration loading."""

    @staticmethod
    def load():
        """Load kubeconfig from in-cluster or local config."""
        log = get_logger()
        try:
            config.load_incluster_config()
            log.debug("loaded_in_cluster_config")
        except config.ConfigException:
            config.load_kube_config()
            log.debug("loaded_local_kubeconfig")


class KubernetesDiscovery:
    """Discovers Kubernetes deployments with HTTP liveness probes."""

    def __init__(self):
        self.apps_v1 = client.AppsV1Api()
        self.core_v1 = client.CoreV1Api()
        self._services_cache: dict[str, client.V1ServiceList] = {}
        self.log = get_logger()

    def discover_monitors(
        self, namespace_filter: Optional[str] = None
    ) -> list[Monitor]:
        """
        Discover all deployments with HTTP liveness probes.

        Args:
            namespace_filter: Optional namespace to filter by

        Returns:
            List of Monitor objects
        """
        deployments = self.apps_v1.list_deployment_for_all_namespaces()
        monitors = []

        for deploy in deployments.items:
            ns = deploy.metadata.namespace
            name = deploy.metadata.name

            if namespace_filter and ns != namespace_filter:
                continue

            monitor = self._process_deployment(deploy, ns, name)
            if monitor:
                monitors.append(monitor)

        self.log.info(
            "discovered_monitors",
            count=len(monitors),
            namespace=namespace_filter or "all",
        )
        return monitors

    def _process_deployment(self, deploy, ns: str, name: str) -> Optional[Monitor]:
        """Process a single deployment and extract monitor info."""
        for container in deploy.spec.template.spec.containers:
            probe = container.liveness_probe
            if not probe or not probe.http_get:
                continue

            path = probe.http_get.path or "/"
            port = probe.http_get.port

            if isinstance(port, str):
                port = self._resolve_port(container, port)
                if not port:
                    self.log.debug(
                        "skipping_named_port",
                        namespace=ns,
                        deployment=name,
                        port_name=port,
                    )
                    continue

            svc_name = self._get_service_name(deploy, ns) or name
            url = f"http://{svc_name}.{ns}.svc.cluster.local:{port}{path}"

            return Monitor(
                deployment=name,
                namespace=ns,
                url=url,
                interval=probe.period_seconds or 30,
            )

        return None

    def _resolve_port(self, container, named_port: str) -> Optional[int]:
        """Resolve a named port to its container port number."""
        for p in container.ports or []:
            if p.name == named_port:
                return p.container_port
        return None

    def _get_service_name(self, deploy, namespace: str) -> Optional[str]:
        """Find the service name that matches the deployment labels."""
        if namespace not in self._services_cache:
            self._services_cache[namespace] = self.core_v1.list_namespaced_service(
                namespace
            )

        labels = deploy.spec.template.metadata.labels or {}
        services = self._services_cache[namespace]

        for svc in services.items:
            selector = svc.spec.selector or {}
            if selector and all(labels.get(k) == v for k, v in selector.items()):
                return svc.metadata.name

        return None


# Warden API Client (Sync)
class WardenClient:
    """Synchronous client for interacting with the Warden API."""

    def __init__(self, base_url: str, api_key: str):
        self.http = httpx.Client(
            base_url=base_url,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            timeout=30,
        )
        self.log = get_logger().bind(component="warden_client")

    def get_existing_monitors(self) -> dict[str, ExistingMonitor]:
        """
        Fetch all existing monitors from Warden.

        Returns:
            Dictionary mapping monitor names to ExistingMonitor objects
        """
        resp = self.http.get("/api/uptime")
        resp.raise_for_status()

        # Parse and validate response
        uptime_data = UptimeResponse.model_validate(resp.json())

        # Build lookup dict by name for quick access
        monitors_by_name: dict[str, ExistingMonitor] = {}

        # Handle case where groups is None (empty Warden instance)
        if uptime_data.groups:
            for group in uptime_data.groups:
                for monitor in group.monitors:
                    existing = ExistingMonitor(
                        id=monitor.id,
                        name=monitor.name,
                        url=monitor.url,
                        groupId=group.id,
                        groupName=group.name,
                        interval=monitor.interval,
                    )
                    monitors_by_name[monitor.name] = existing

        self.log.debug("fetched_existing_monitors", count=len(monitors_by_name))
        return monitors_by_name

    def create_group(self, name: str) -> str:
        """
        Create a monitor group in Warden.

        Args:
            name: Group name

        Returns:
            Group ID
        """
        resp = self.http.post("/api/groups", json={"name": name})
        resp.raise_for_status()
        group_data = GroupResponse.model_validate(resp.json())
        self.log.info("created_group", group_name=name, group_id=group_data.id)
        return group_data.id

    def create_monitor(self, name: str, url: str, group_id: str, interval: int) -> None:
        """
        Create a monitor in Warden.

        Args:
            name: Monitor name
            url: URL to monitor
            group_id: Group ID to assign monitor to
            interval: Check interval in seconds
        """
        payload = {
            "name": name,
            "url": url,
            "groupId": group_id,
            "interval": interval,
        }
        resp = self.http.post("/api/monitors", json=payload)
        resp.raise_for_status()
        self.log.info(
            "created_monitor",
            monitor_name=name,
            url=url,
            interval=interval,
            action="created",
        )

    def update_monitor(
        self, monitor_id: str, name: str, url: str, group_id: str, interval: int
    ) -> None:
        """
        Update an existing monitor in Warden.

        Args:
            monitor_id: Monitor ID to update
            name: Monitor name
            url: URL to monitor
            group_id: Group ID to assign monitor to
            interval: Check interval in seconds
        """
        payload = {
            "name": name,
            "url": url,
            "groupId": group_id,
            "interval": interval,
        }
        resp = self.http.put(f"/api/monitors/{monitor_id}", json=payload)
        resp.raise_for_status()
        self.log.info(
            "updated_monitor",
            monitor_name=name,
            url=url,
            interval=interval,
            action="updated",
        )

    def delete_monitor(self, monitor_id: str) -> None:
        """Delete a monitor from Warden."""
        resp = self.http.delete(f"/api/monitors/{monitor_id}")
        resp.raise_for_status()

    def delete_group(self, group_id: str) -> None:
        """Delete a group from Warden."""
        resp = self.http.delete(f"/api/groups/{group_id}")
        resp.raise_for_status()

    def close(self):
        """Close the HTTP client."""
        self.http.close()


# Warden API Client (Async)
class WardenAsyncClient:
    """Async client for interacting with the Warden API."""

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.api_key = api_key
        self.log = get_logger().bind(component="warden_async_client")
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        """Async context manager entry."""
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            timeout=30,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()

    @property
    def http(self) -> httpx.AsyncClient:
        """Get the HTTP client."""
        if not self._client:
            raise RuntimeError("WardenAsyncClient must be used as async context manager")
        return self._client

    async def get_existing_monitors(self) -> dict[str, ExistingMonitor]:
        """
        Fetch all existing monitors from Warden.

        Returns:
            Dictionary mapping monitor names to ExistingMonitor objects
        """
        resp = await self.http.get("/api/uptime")
        resp.raise_for_status()

        # Parse and validate response
        uptime_data = UptimeResponse.model_validate(resp.json())

        # Build lookup dict by name for quick access
        monitors_by_name: dict[str, ExistingMonitor] = {}

        # Handle case where groups is None (empty Warden instance)
        if uptime_data.groups:
            for group in uptime_data.groups:
                for monitor in group.monitors:
                    existing = ExistingMonitor(
                        id=monitor.id,
                        name=monitor.name,
                        url=monitor.url,
                        groupId=group.id,
                        groupName=group.name,
                        interval=monitor.interval,
                    )
                    monitors_by_name[monitor.name] = existing

        self.log.debug("fetched_existing_monitors", count=len(monitors_by_name))
        return monitors_by_name

    async def create_group(self, name: str) -> str:
        """
        Create a monitor group in Warden.

        Args:
            name: Group name

        Returns:
            Group ID
        """
        resp = await self.http.post("/api/groups", json={"name": name})
        resp.raise_for_status()
        group_data = GroupResponse.model_validate(resp.json())
        self.log.info("created_group", group_name=name, group_id=group_data.id)
        return group_data.id

    async def create_monitor(self, name: str, url: str, group_id: str, interval: int) -> None:
        """
        Create a monitor in Warden.

        Args:
            name: Monitor name
            url: URL to monitor
            group_id: Group ID to assign monitor to
            interval: Check interval in seconds
        """
        payload = {
            "name": name,
            "url": url,
            "groupId": group_id,
            "interval": interval,
        }
        resp = await self.http.post("/api/monitors", json=payload)
        resp.raise_for_status()
        self.log.info(
            "created_monitor",
            monitor_name=name,
            url=url,
            interval=interval,
            action="created",
        )

    async def update_monitor(
        self, monitor_id: str, name: str, url: str, group_id: str, interval: int
    ) -> None:
        """
        Update an existing monitor in Warden.

        Args:
            monitor_id: Monitor ID to update
            name: Monitor name
            url: URL to monitor
            group_id: Group ID to assign monitor to
            interval: Check interval in seconds
        """
        payload = {
            "name": name,
            "url": url,
            "groupId": group_id,
            "interval": interval,
        }
        resp = await self.http.put(f"/api/monitors/{monitor_id}", json=payload)
        resp.raise_for_status()
        self.log.info(
            "updated_monitor",
            monitor_name=name,
            url=url,
            interval=interval,
            action="updated",
        )

    async def delete_monitor(self, monitor_id: str) -> None:
        """Delete a monitor from Warden."""
        resp = await self.http.delete(f"/api/monitors/{monitor_id}")
        resp.raise_for_status()

    async def delete_group(self, group_id: str) -> None:
        """Delete a group from Warden."""
        resp = await self.http.delete(f"/api/groups/{group_id}")
        resp.raise_for_status()
