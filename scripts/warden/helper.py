from typing import Optional

import httpx
import structlog
from kubernetes import client, config
from pydantic import BaseModel, Field, HttpUrl

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(20),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=False,
)


def get_logger(name: str = __name__) -> structlog.BoundLogger:
    return structlog.get_logger(name)


def configure_log_level(verbose: bool = False):
    level = 10 if verbose else 20
    structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(level))


class Monitor(BaseModel):
    model_config = {"frozen": True}

    deployment: str = Field(..., description="Deployment name")
    namespace: str = Field(..., description="Kubernetes namespace")
    url: HttpUrl = Field(..., description="Health check URL")
    interval: int = Field(..., ge=1, description="Check interval in seconds")


class ExistingMonitor(BaseModel):
    id: str
    name: str
    url: HttpUrl
    group_id: str = Field(..., alias="groupId")
    group_name: str = Field(..., alias="groupName")
    interval: int


class GroupResponse(BaseModel):
    id: str
    name: str


class MonitorResponse(BaseModel):
    id: str
    name: str
    url: HttpUrl
    interval: int
    status: str
    active: bool


class GroupWithMonitors(BaseModel):
    id: str
    name: str
    monitors: list[MonitorResponse]


class UptimeResponse(BaseModel):
    groups: Optional[list[GroupWithMonitors]] = None


class KubernetesConfig:
    @staticmethod
    def load():
        log = get_logger()
        try:
            config.load_incluster_config()
            log.debug("loaded_in_cluster_config")
        except config.ConfigException:
            config.load_kube_config()
            log.debug("loaded_local_kubeconfig")


class KubernetesDiscovery:
    def __init__(self):
        self.apps_v1 = client.AppsV1Api()
        self.core_v1 = client.CoreV1Api()
        self._services_cache: dict[str, client.V1ServiceList] = {}
        self.log = get_logger()

    def discover_monitors(
        self,
        namespace_filter: Optional[str] = None,
        namespace_list: Optional[list[str]] = None,
    ) -> list[Monitor]:
        deployments = self.apps_v1.list_deployment_for_all_namespaces()
        monitors = []

        for deploy in deployments.items:
            ns = deploy.metadata.namespace
            name = deploy.metadata.name

            if namespace_filter and ns != namespace_filter:
                continue
            if namespace_list and ns not in namespace_list:
                continue

            deployment_monitors = self._process_deployment(deploy, ns, name)
            monitors.extend(deployment_monitors)

        filter_desc = namespace_filter or (
            f"{len(namespace_list)} namespaces" if namespace_list else "all"
        )
        self.log.info(
            "discovered_monitors",
            count=len(monitors),
            namespace=filter_desc,
        )
        return monitors

    def _process_deployment(self, deploy, ns: str, name: str) -> list[Monitor]:
        monitors = []
        containers_with_probes = []

        for container in deploy.spec.template.spec.containers:
            probe = container.liveness_probe
            if not probe:
                continue

            if probe.http_get or probe.tcp_socket:
                containers_with_probes.append(container)

        include_container_name = len(containers_with_probes) > 1

        for container in containers_with_probes:
            probe = container.liveness_probe

            if probe.http_get:
                path = probe.http_get.path or "/"
                port = probe.http_get.port
            elif probe.tcp_socket:
                path = "/"
                port = probe.tcp_socket.port
            else:
                continue

            if isinstance(port, str):
                container_port = self._resolve_port(container, port)
                if not container_port:
                    self.log.debug(
                        "skipping_named_port",
                        namespace=ns,
                        deployment=name,
                        container=container.name,
                        port_name=port,
                    )
                    continue
            else:
                container_port = port

            svc_name, service_port = self._get_service_info(deploy, ns, container_port)
            svc_name = svc_name or name
            final_port = service_port if service_port else container_port

            url = HttpUrl(
                f"http://{svc_name}.{ns}.svc.cluster.local:{final_port}{path}"
            )

            monitor_name = (
                f"{name}-{container.name}" if include_container_name else name
            )

            monitors.append(
                Monitor(
                    deployment=monitor_name,
                    namespace=ns,
                    url=url,
                    interval=probe.period_seconds or 30,
                )
            )

        return monitors

    def _resolve_port(self, container, named_port: str) -> Optional[int]:
        for p in container.ports or []:
            if p.name == named_port:
                return p.container_port
        return None

    def _get_service_info(
        self, deploy, namespace: str, container_port: int
    ) -> tuple[Optional[str], Optional[int]]:
        if namespace not in self._services_cache:
            self._services_cache[namespace] = self.core_v1.list_namespaced_service(
                namespace
            )

        labels = deploy.spec.template.metadata.labels or {}
        services = self._services_cache[namespace]

        matching_services = []

        for svc in services.items:
            selector = svc.spec.selector or {}
            if selector and all(labels.get(k) == v for k, v in selector.items()):
                for port_spec in svc.spec.ports or []:
                    target_port = port_spec.target_port

                    if isinstance(target_port, int) and target_port == container_port:
                        return svc.metadata.name, port_spec.port
                    elif isinstance(target_port, str):
                        if self._port_name_matches(deploy, target_port, container_port):
                            return svc.metadata.name, port_spec.port

                matching_services.append(svc.metadata.name)

        if matching_services:
            return matching_services[0], None

        return None, None

    def _port_name_matches(self, deploy, port_name: str, container_port: int) -> bool:
        for container in deploy.spec.template.spec.containers:
            for p in container.ports or []:
                if p.name == port_name and p.container_port == container_port:
                    return True
        return False


class WardenClient:
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
        resp = self.http.get("/api/uptime")
        resp.raise_for_status()

        uptime_data = UptimeResponse.model_validate(resp.json())
        monitors_by_name: dict[str, ExistingMonitor] = {}

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
        resp = self.http.post("/api/groups", json={"name": name})
        resp.raise_for_status()
        group_data = GroupResponse.model_validate(resp.json())
        self.log.info("created_group", group_name=name, group_id=group_data.id)
        return group_data.id

    def create_monitor(self, name: str, url: str, group_id: str, interval: int) -> None:
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
        resp = self.http.delete(f"/api/monitors/{monitor_id}")
        resp.raise_for_status()

    def delete_group(self, group_id: str) -> None:
        resp = self.http.delete(f"/api/groups/{group_id}")
        resp.raise_for_status()

    def close(self):
        self.http.close()


class WardenAsyncClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.api_key = api_key
        self.log = get_logger().bind(component="warden_async_client")
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
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
        if self._client:
            await self._client.aclose()

    @property
    def http(self) -> httpx.AsyncClient:
        if not self._client:
            raise RuntimeError(
                "WardenAsyncClient must be used as async context manager"
            )
        return self._client

    async def get_existing_monitors(self) -> dict[str, ExistingMonitor]:
        resp = await self.http.get("/api/uptime")
        resp.raise_for_status()

        uptime_data = UptimeResponse.model_validate(resp.json())
        monitors_by_name: dict[str, ExistingMonitor] = {}

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
        resp = await self.http.post("/api/groups", json={"name": name})
        resp.raise_for_status()
        group_data = GroupResponse.model_validate(resp.json())
        self.log.info("created_group", group_name=name, group_id=group_data.id)
        return group_data.id

    async def create_monitor(
        self, name: str, url: str, group_id: str, interval: int
    ) -> None:
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
        resp = await self.http.delete(f"/api/monitors/{monitor_id}")
        resp.raise_for_status()

    async def delete_group(self, group_id: str) -> None:
        resp = await self.http.delete(f"/api/groups/{group_id}")
        resp.raise_for_status()
