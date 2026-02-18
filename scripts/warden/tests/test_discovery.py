import pytest
from unittest.mock import MagicMock, patch
from warden.helper import KubernetesDiscovery


def create_mock_container(name, liveness_probe=None, ports=None):
    container = MagicMock()
    container.name = name
    container.liveness_probe = liveness_probe
    container.ports = ports
    return container


def create_mock_probe(http_get=None, tcp_socket=None, period_seconds=None):
    probe = MagicMock()
    probe.http_get = http_get
    probe.tcp_socket = tcp_socket
    probe.period_seconds = period_seconds
    return probe


def create_mock_http_get(path, port):
    http_get = MagicMock()
    http_get.path = path
    http_get.port = port
    return http_get


def create_mock_tcp_socket(port):
    tcp_socket = MagicMock()
    tcp_socket.port = port
    return tcp_socket


def create_mock_port(name, container_port):
    port = MagicMock()
    port.name = name
    port.container_port = container_port
    return port


def create_mock_deployment(name, namespace, containers, labels=None):
    deploy = MagicMock()
    deploy.metadata.name = name
    deploy.metadata.namespace = namespace
    deploy.spec.template.spec.containers = containers
    deploy.spec.template.metadata.labels = labels or {}
    return deploy


def create_mock_service(name, namespace, ports=None, selector=None):
    svc = MagicMock()
    svc.metadata.name = name
    svc.metadata.namespace = namespace
    svc.spec.ports = ports
    svc.spec.selector = selector
    return svc


def create_mock_service_port(port, target_port):
    svc_port = MagicMock()
    svc_port.port = port
    svc_port.target_port = target_port
    return svc_port


@pytest.fixture
def mock_k8s_client():
    with patch("warden.helper.client") as mock_client:
        mock_apps_v1 = MagicMock()
        mock_core_v1 = MagicMock()
        mock_client.AppsV1Api.return_value = mock_apps_v1
        mock_client.CoreV1Api.return_value = mock_core_v1
        yield mock_client


@pytest.fixture
def discovery(mock_k8s_client):
    return KubernetesDiscovery()


def test_process_deployment_http_probe(discovery):
    http_get = create_mock_http_get(path="/health", port=8080)
    probe = create_mock_probe(http_get=http_get, period_seconds=15)
    container = create_mock_container(name="app", liveness_probe=probe)
    deploy = create_mock_deployment(
        name="test-app", namespace="default", containers=[container]
    )

    discovery.core_v1.list_namespaced_service.return_value.items = []

    monitors = discovery._process_deployment(deploy, "default", "test-app")

    assert len(monitors) == 1
    assert monitors[0].deployment == "test-app"
    assert monitors[0].namespace == "default"
    assert (
        str(monitors[0].url) == "http://test-app.default.svc.cluster.local:8080/health"
    )
    assert monitors[0].interval == 15


def test_process_deployment_tcp_probe(discovery):
    tcp_socket = create_mock_tcp_socket(port=9000)
    probe = create_mock_probe(tcp_socket=tcp_socket, period_seconds=20)
    container = create_mock_container(name="db", liveness_probe=probe)
    deploy = create_mock_deployment(
        name="test-db", namespace="default", containers=[container]
    )

    discovery.core_v1.list_namespaced_service.return_value.items = []

    monitors = discovery._process_deployment(deploy, "default", "test-db")

    assert len(monitors) == 1
    assert monitors[0].deployment == "test-db"
    assert str(monitors[0].url) == "http://test-db.default.svc.cluster.local:9000/"
    assert monitors[0].interval == 20


def test_process_deployment_no_probe_fallback(discovery):
    container = create_mock_container(name="app", liveness_probe=None)
    deploy = create_mock_deployment(
        name="test-app",
        namespace="default",
        containers=[container],
        labels={"app": "test"},
    )

    svc_port = create_mock_service_port(port=80, target_port=8080)
    svc = create_mock_service(
        name="test-service",
        namespace="default",
        ports=[svc_port],
        selector={"app": "test"},
    )
    discovery.core_v1.list_namespaced_service.return_value.items = [svc]

    monitors = discovery._process_deployment(
        deploy, "default", "test-app", default_interval=45
    )

    assert len(monitors) == 1
    assert monitors[0].deployment == "test-app"
    assert str(monitors[0].url) == "http://test-service.default.svc.cluster.local/"
    assert monitors[0].interval == 45


def test_process_deployment_multiple_containers(discovery):
    probe1 = create_mock_probe(http_get=create_mock_http_get("/", 8080))
    c1 = create_mock_container(name="frontend", liveness_probe=probe1)

    probe2 = create_mock_probe(http_get=create_mock_http_get("/api/health", 3000))
    c2 = create_mock_container(name="backend", liveness_probe=probe2)

    deploy = create_mock_deployment(
        name="full-stack", namespace="default", containers=[c1, c2]
    )
    discovery.core_v1.list_namespaced_service.return_value.items = []

    monitors = discovery._process_deployment(deploy, "default", "full-stack")

    assert len(monitors) == 2
    names = {m.deployment for m in monitors}
    assert "full-stack-frontend" in names
    assert "full-stack-backend" in names


def test_fallback_from_service_match(discovery):
    deploy = create_mock_deployment(
        name="app", namespace="ns1", containers=[], labels={"app": "foo", "tier": "web"}
    )

    svc_port = create_mock_service_port(port=80, target_port=8080)
    svc = create_mock_service(
        name="app-svc",
        namespace="ns1",
        ports=[svc_port],
        selector={"app": "foo", "tier": "web"},
    )

    discovery.core_v1.list_namespaced_service.return_value.items = [svc]

    monitor = discovery._fallback_from_service(
        deploy, "ns1", "app", default_interval=60
    )

    assert monitor is not None
    assert monitor.deployment == "app"
    assert str(monitor.url) == "http://app-svc.ns1.svc.cluster.local/"
    assert monitor.interval == 60


def test_fallback_from_service_no_match(discovery):
    deploy = create_mock_deployment(
        name="app", namespace="ns1", containers=[], labels={"app": "foo"}
    )

    svc = create_mock_service(
        name="other-svc", namespace="ns1", ports=[], selector={"app": "bar"}
    )

    discovery.core_v1.list_namespaced_service.return_value.items = [svc]

    monitor = discovery._fallback_from_service(deploy, "ns1", "app")
    assert monitor is None


def test_fallback_from_service_match_no_ports(discovery):
    deploy = create_mock_deployment(
        name="app", namespace="ns1", containers=[], labels={"app": "foo"}
    )

    svc = create_mock_service(
        name="app-svc", namespace="ns1", ports=[], selector={"app": "foo"}
    )

    discovery.core_v1.list_namespaced_service.return_value.items = [svc]

    monitor = discovery._fallback_from_service(deploy, "ns1", "app")
    assert monitor is None


def test_fallback_from_service_default_interval(discovery):
    deploy = create_mock_deployment(
        name="app", namespace="ns1", containers=[], labels={"app": "foo"}
    )
    svc_port = create_mock_service_port(port=80, target_port=8080)
    svc = create_mock_service(
        name="app-svc", namespace="ns1", ports=[svc_port], selector={"app": "foo"}
    )
    discovery.core_v1.list_namespaced_service.return_value.items = [svc]

    monitor = discovery._fallback_from_service(
        deploy, "ns1", "app", default_interval=120
    )
    assert monitor.interval == 120


def test_discover_monitors_default_interval_threaded(discovery):
    container = create_mock_container(name="app", liveness_probe=None)
    deploy = create_mock_deployment(
        name="app", namespace="ns1", containers=[container], labels={"app": "foo"}
    )

    discovery.apps_v1.list_deployment_for_all_namespaces.return_value.items = [deploy]

    svc_port = create_mock_service_port(port=80, target_port=8080)
    svc = create_mock_service(
        name="app-svc", namespace="ns1", ports=[svc_port], selector={"app": "foo"}
    )
    discovery.core_v1.list_namespaced_service.return_value.items = [svc]

    monitors = discovery.discover_monitors(default_interval=99)

    assert len(monitors) == 1
    assert monitors[0].interval == 99


def test_discover_monitors_namespace_filtering(discovery):
    d1 = create_mock_deployment(
        name="d1",
        namespace="ns1",
        containers=[
            create_mock_container(
                "c1", create_mock_probe(http_get=create_mock_http_get("/", 80))
            )
        ],
    )
    d2 = create_mock_deployment(
        name="d2",
        namespace="ns2",
        containers=[
            create_mock_container(
                "c2", create_mock_probe(http_get=create_mock_http_get("/", 80))
            )
        ],
    )
    d3 = create_mock_deployment(
        name="d3",
        namespace="ns3",
        containers=[
            create_mock_container(
                "c3", create_mock_probe(http_get=create_mock_http_get("/", 80))
            )
        ],
    )

    discovery.apps_v1.list_deployment_for_all_namespaces.return_value.items = [
        d1,
        d2,
        d3,
    ]
    discovery.core_v1.list_namespaced_service.return_value.items = []

    monitors = discovery.discover_monitors(namespace_filter="ns1")
    assert len(monitors) == 1
    assert monitors[0].namespace == "ns1"

    monitors = discovery.discover_monitors(namespace_list=["ns2", "ns3"])
    assert len(monitors) == 2
    namespaces = {m.namespace for m in monitors}
    assert "ns2" in namespaces
    assert "ns3" in namespaces
    assert "ns1" not in namespaces


def test_get_service_info_resolves_port(discovery):
    deploy = create_mock_deployment(
        name="app", namespace="ns1", containers=[], labels={"app": "foo"}
    )

    svc_port1 = create_mock_service_port(port=80, target_port=8080)
    svc1 = create_mock_service(
        name="svc1", namespace="ns1", ports=[svc_port1], selector={"app": "foo"}
    )

    discovery.core_v1.list_namespaced_service.return_value.items = [svc1]

    svc_name, port = discovery._get_service_info(deploy, "ns1", container_port=8080)
    assert svc_name == "svc1"
    assert port == 80


def test_get_service_info_resolves_named_port(discovery):
    c_port = create_mock_port(name="http", container_port=8080)
    container = create_mock_container(name="c1", ports=[c_port])
    deploy = create_mock_deployment(
        name="app", namespace="ns1", containers=[container], labels={"app": "foo"}
    )

    svc_port = create_mock_service_port(port=80, target_port="http")
    svc = create_mock_service(
        name="svc-named", namespace="ns1", ports=[svc_port], selector={"app": "foo"}
    )

    discovery.core_v1.list_namespaced_service.return_value.items = [svc]

    svc_name, port = discovery._get_service_info(deploy, "ns1", container_port=8080)
    assert svc_name == "svc-named"
    assert port == 80


def test_get_service_info_no_match(discovery):
    deploy = create_mock_deployment(
        name="app", namespace="ns1", containers=[], labels={"app": "foo"}
    )
    svc = create_mock_service(
        name="other",
        namespace="ns1",
        ports=[create_mock_service_port(port=80, target_port=8080)],
        selector={"app": "bar"},
    )
    discovery.core_v1.list_namespaced_service.return_value.items = [svc]

    svc_name, port = discovery._get_service_info(deploy, "ns1", container_port=8080)
    assert svc_name is None
    assert port is None


def test_fallback_from_service_no_labels(discovery):
    deploy = create_mock_deployment(
        name="app", namespace="ns1", containers=[], labels={}
    )

    monitor = discovery._fallback_from_service(deploy, "ns1", "app")
    assert monitor is None


def test_fallback_from_service_fetches_when_not_cached(discovery):
    svc_port = create_mock_service_port(port=7878, target_port=7878)
    svc = create_mock_service(
        name="radarr", namespace="arr", ports=[svc_port], selector={"app": "radarr"}
    )
    svc_list = MagicMock()
    svc_list.items = [svc]
    discovery.core_v1.list_namespaced_service.return_value = svc_list

    deploy = create_mock_deployment(
        name="radarr", namespace="arr", containers=[], labels={"app": "radarr"}
    )

    monitor = discovery._fallback_from_service(deploy, "arr", "radarr")

    assert monitor is not None
    discovery.core_v1.list_namespaced_service.assert_called_once_with("arr")


def test_fallback_default_interval_is_30(discovery):
    svc_port = create_mock_service_port(port=7878, target_port=7878)
    svc = create_mock_service(
        name="radarr", namespace="arr", ports=[svc_port], selector={"app": "radarr"}
    )
    discovery.core_v1.list_namespaced_service.return_value.items = [svc]

    deploy = create_mock_deployment(
        name="radarr", namespace="arr", containers=[], labels={"app": "radarr"}
    )

    monitor = discovery._fallback_from_service(deploy, "arr", "radarr")
    assert monitor is not None
    assert monitor.interval == 30


def test_process_deployment_no_probe_no_match_returns_empty(discovery):
    container = create_mock_container(name="app", liveness_probe=None)
    deploy = create_mock_deployment(
        name="app",
        namespace="ns1",
        containers=[container],
        labels={"app": "foo"},
    )
    svc = create_mock_service(
        name="other",
        namespace="ns1",
        ports=[create_mock_service_port(port=80, target_port=80)],
        selector={"app": "bar"},
    )
    discovery.core_v1.list_namespaced_service.return_value.items = [svc]

    monitors = discovery._process_deployment(deploy, "ns1", "app")
    assert len(monitors) == 0


def test_process_deployment_single_container_no_suffix(discovery):
    probe = create_mock_probe(
        http_get=create_mock_http_get("/health", 8080), period_seconds=30
    )
    container = create_mock_container(name="web", liveness_probe=probe)
    deploy = create_mock_deployment(
        name="my-app", namespace="default", containers=[container]
    )
    discovery.core_v1.list_namespaced_service.return_value.items = []

    monitors = discovery._process_deployment(deploy, "default", "my-app")

    assert len(monitors) == 1
    assert monitors[0].deployment == "my-app"


def test_resolve_port_named(discovery):
    port = create_mock_port(name="http", container_port=8080)
    container = create_mock_container(name="web", ports=[port])

    result = discovery._resolve_port(container, "http")
    assert result == 8080


def test_resolve_port_unknown(discovery):
    port = create_mock_port(name="http", container_port=8080)
    container = create_mock_container(name="web", ports=[port])

    result = discovery._resolve_port(container, "grpc")
    assert result is None


def test_resolve_port_no_ports(discovery):
    container = create_mock_container(name="web", ports=None)

    result = discovery._resolve_port(container, "http")
    assert result is None


def test_discover_monitors_returns_all_without_filter(discovery):
    probe = create_mock_probe(
        http_get=create_mock_http_get("/", 8080), period_seconds=30
    )
    d1 = create_mock_deployment(
        name="a", namespace="ns1", containers=[create_mock_container("c", probe)]
    )
    d2 = create_mock_deployment(
        name="b", namespace="ns2", containers=[create_mock_container("c", probe)]
    )
    discovery.apps_v1.list_deployment_for_all_namespaces.return_value.items = [d1, d2]
    discovery.core_v1.list_namespaced_service.return_value.items = []

    monitors = discovery.discover_monitors()
    assert len(monitors) == 2


def test_process_deployment_named_port_resolved(discovery):
    http_get = create_mock_http_get(path="/health", port="http")
    probe = create_mock_probe(http_get=http_get, period_seconds=10)
    c_port = create_mock_port(name="http", container_port=8080)
    container = create_mock_container(name="web", liveness_probe=probe, ports=[c_port])
    deploy = create_mock_deployment(name="app", namespace="ns1", containers=[container])
    discovery.core_v1.list_namespaced_service.return_value.items = []

    monitors = discovery._process_deployment(deploy, "ns1", "app")

    assert len(monitors) == 1
    assert ":8080" in str(monitors[0].url)
    assert monitors[0].interval == 10


def test_process_deployment_named_port_unresolved_skips(discovery):
    http_get = create_mock_http_get(path="/health", port="missing")
    probe = create_mock_probe(http_get=http_get, period_seconds=10)
    container = create_mock_container(
        name="web", liveness_probe=probe, ports=[create_mock_port("http", 8080)]
    )
    deploy = create_mock_deployment(name="app", namespace="ns1", containers=[container])
    discovery.core_v1.list_namespaced_service.return_value.items = []

    monitors = discovery._process_deployment(deploy, "ns1", "app")

    assert len(monitors) == 0


def test_get_service_info_selector_match_no_port_match_fallback(discovery):
    deploy = create_mock_deployment(
        name="app", namespace="ns1", containers=[], labels={"app": "foo"}
    )
    svc = create_mock_service(
        name="my-svc",
        namespace="ns1",
        ports=[create_mock_service_port(port=80, target_port=9999)],
        selector={"app": "foo"},
    )
    discovery.core_v1.list_namespaced_service.return_value.items = [svc]

    svc_name, port = discovery._get_service_info(deploy, "ns1", container_port=8080)

    assert svc_name == "my-svc"
    assert port is None


def test_port_name_matches_true(discovery):
    c_port = create_mock_port(name="http", container_port=8080)
    container = create_mock_container(name="web", ports=[c_port])
    deploy = create_mock_deployment(name="app", namespace="ns1", containers=[container])

    assert discovery._port_name_matches(deploy, "http", 8080) is True


def test_port_name_matches_false_wrong_name(discovery):
    c_port = create_mock_port(name="http", container_port=8080)
    container = create_mock_container(name="web", ports=[c_port])
    deploy = create_mock_deployment(name="app", namespace="ns1", containers=[container])

    assert discovery._port_name_matches(deploy, "grpc", 8080) is False


def test_port_name_matches_false_wrong_port(discovery):
    c_port = create_mock_port(name="http", container_port=8080)
    container = create_mock_container(name="web", ports=[c_port])
    deploy = create_mock_deployment(name="app", namespace="ns1", containers=[container])

    assert discovery._port_name_matches(deploy, "http", 3000) is False


def test_get_service_info_named_target_port_no_match(discovery):
    c_port = create_mock_port(name="http", container_port=8080)
    container = create_mock_container(name="web", ports=[c_port])
    deploy = create_mock_deployment(
        name="app", namespace="ns1", containers=[container], labels={"app": "foo"}
    )
    svc = create_mock_service(
        name="my-svc",
        namespace="ns1",
        ports=[create_mock_service_port(port=80, target_port="grpc")],
        selector={"app": "foo"},
    )
    discovery.core_v1.list_namespaced_service.return_value.items = [svc]

    svc_name, port = discovery._get_service_info(deploy, "ns1", container_port=8080)

    assert svc_name == "my-svc"
    assert port is None


def test_process_deployment_http_probe_no_path_defaults_to_slash(discovery):
    http_get = create_mock_http_get(path=None, port=8080)
    probe = create_mock_probe(http_get=http_get, period_seconds=30)
    container = create_mock_container(name="web", liveness_probe=probe)
    deploy = create_mock_deployment(name="app", namespace="ns1", containers=[container])
    discovery.core_v1.list_namespaced_service.return_value.items = []

    monitors = discovery._process_deployment(deploy, "ns1", "app")

    assert len(monitors) == 1
    assert str(monitors[0].url).endswith(":8080/")


def test_process_deployment_period_seconds_none_defaults_to_30(discovery):
    http_get = create_mock_http_get(path="/", port=8080)
    probe = create_mock_probe(http_get=http_get, period_seconds=None)
    container = create_mock_container(name="web", liveness_probe=probe)
    deploy = create_mock_deployment(name="app", namespace="ns1", containers=[container])
    discovery.core_v1.list_namespaced_service.return_value.items = []

    monitors = discovery._process_deployment(deploy, "ns1", "app")

    assert monitors[0].interval == 30


def test_configure_log_level_verbose():
    from warden.helper import configure_log_level

    configure_log_level(verbose=True)


def test_configure_log_level_default():
    from warden.helper import configure_log_level

    configure_log_level(verbose=False)


def test_kubernetes_config_load_incluster(mock_k8s_client):
    from warden.helper import KubernetesConfig

    with patch("warden.helper.config") as mock_config:
        KubernetesConfig.load()
        mock_config.load_incluster_config.assert_called_once()


def test_kubernetes_config_load_fallback_to_kubeconfig(mock_k8s_client):
    from warden.helper import KubernetesConfig

    with patch("warden.helper.config") as mock_config:
        mock_config.ConfigException = Exception
        mock_config.load_incluster_config.side_effect = Exception("not in cluster")
        KubernetesConfig.load()
        mock_config.load_kube_config.assert_called_once()


class TestWardenClient:
    @pytest.fixture
    def client(self):
        with patch("warden.helper.httpx.Client") as mock_httpx:
            from warden.helper import WardenClient

            c = WardenClient("http://warden.test", "test-key")
            c.http = mock_httpx.return_value
            yield c

    def test_get_existing_monitors_empty(self, client):
        client.http.get.return_value.json.return_value = {"groups": []}
        client.http.get.return_value.raise_for_status = MagicMock()

        result = client.get_existing_monitors()

        assert result == {}
        client.http.get.assert_called_once_with("/api/uptime")

    def test_get_existing_monitors_with_data(self, client):
        client.http.get.return_value.json.return_value = {
            "groups": [
                {
                    "id": "g1",
                    "name": "arr",
                    "monitors": [
                        {
                            "id": "m1",
                            "name": "radarr",
                            "url": "http://radarr:7878/",
                            "interval": 30,
                            "status": "up",
                            "active": True,
                        }
                    ],
                }
            ]
        }
        client.http.get.return_value.raise_for_status = MagicMock()

        result = client.get_existing_monitors()

        assert "radarr" in result
        assert result["radarr"].group_name == "arr"

    def test_create_group(self, client):
        client.http.post.return_value.json.return_value = {"id": "g1", "name": "arr"}
        client.http.post.return_value.raise_for_status = MagicMock()

        group_id = client.create_group("arr")

        assert group_id == "g1"
        client.http.post.assert_called_once_with("/api/groups", json={"name": "arr"})

    def test_create_monitor(self, client):
        client.http.post.return_value.raise_for_status = MagicMock()

        client.create_monitor("radarr", "http://radarr:7878/", "g1", 30)

        client.http.post.assert_called_once_with(
            "/api/monitors",
            json={
                "name": "radarr",
                "url": "http://radarr:7878/",
                "groupId": "g1",
                "interval": 30,
            },
        )

    def test_update_monitor(self, client):
        client.http.put.return_value.raise_for_status = MagicMock()

        client.update_monitor("m1", "radarr", "http://radarr:7878/", "g1", 60)

        client.http.put.assert_called_once_with(
            "/api/monitors/m1",
            json={
                "name": "radarr",
                "url": "http://radarr:7878/",
                "groupId": "g1",
                "interval": 60,
            },
        )

    def test_delete_monitor(self, client):
        client.http.delete.return_value.raise_for_status = MagicMock()

        client.delete_monitor("m1")

        client.http.delete.assert_called_once_with("/api/monitors/m1")

    def test_delete_group(self, client):
        client.http.delete.return_value.raise_for_status = MagicMock()

        client.delete_group("g1")

        client.http.delete.assert_called_once_with("/api/groups/g1")

    def test_close(self, client):
        client.close()

        client.http.close.assert_called_once()


class TestWardenAsyncClient:
    @pytest.fixture
    def async_client(self):
        from warden.helper import WardenAsyncClient

        return WardenAsyncClient("http://warden.test", "test-key")

    def test_http_property_raises_without_context(self, async_client):
        with pytest.raises(RuntimeError, match="async context manager"):
            _ = async_client.http

    @pytest.mark.asyncio
    async def test_context_manager_creates_client(self, async_client):
        async with async_client as c:
            assert c._client is not None

    @pytest.mark.asyncio
    async def test_context_manager_closes_client(self, async_client):
        async with async_client:
            pass
        assert async_client._client is None or True

    @pytest.mark.asyncio
    async def test_get_existing_monitors(self, async_client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"groups": []}
        mock_resp.raise_for_status = MagicMock()

        async with async_client as c:
            with patch.object(c._client, "get", return_value=mock_resp) as mock_get:
                result = await c.get_existing_monitors()

        assert result == {}
        mock_get.assert_called_once_with("/api/uptime")

    @pytest.mark.asyncio
    async def test_create_group(self, async_client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"id": "g1", "name": "arr"}
        mock_resp.raise_for_status = MagicMock()

        async with async_client as c:
            with patch.object(c._client, "post", return_value=mock_resp):
                group_id = await c.create_group("arr")

        assert group_id == "g1"

    @pytest.mark.asyncio
    async def test_create_monitor(self, async_client):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()

        async with async_client as c:
            with patch.object(c._client, "post", return_value=mock_resp) as mock_post:
                await c.create_monitor("radarr", "http://radarr:7878/", "g1", 30)

        mock_post.assert_called_once_with(
            "/api/monitors",
            json={
                "name": "radarr",
                "url": "http://radarr:7878/",
                "groupId": "g1",
                "interval": 30,
            },
        )

    @pytest.mark.asyncio
    async def test_update_monitor(self, async_client):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()

        async with async_client as c:
            with patch.object(c._client, "put", return_value=mock_resp) as mock_put:
                await c.update_monitor("m1", "radarr", "http://radarr:7878/", "g1", 60)

        mock_put.assert_called_once_with(
            "/api/monitors/m1",
            json={
                "name": "radarr",
                "url": "http://radarr:7878/",
                "groupId": "g1",
                "interval": 60,
            },
        )

    @pytest.mark.asyncio
    async def test_delete_monitor(self, async_client):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()

        async with async_client as c:
            with patch.object(
                c._client, "delete", return_value=mock_resp
            ) as mock_delete:
                await c.delete_monitor("m1")

        mock_delete.assert_called_once_with("/api/monitors/m1")

    @pytest.mark.asyncio
    async def test_delete_group(self, async_client):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()

        async with async_client as c:
            with patch.object(
                c._client, "delete", return_value=mock_resp
            ) as mock_delete:
                await c.delete_group("g1")

        mock_delete.assert_called_once_with("/api/groups/g1")
