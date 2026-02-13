#!/usr/bin/env python3

import os

import httpx

from warden.helper import (
    KubernetesConfig,
    UptimeResponse,
    configure_log_level,
    get_logger,
)
from kubernetes import client

log = get_logger(__name__)


def main():
    configure_log_level(False)

    KubernetesConfig.load()

    apps_v1 = client.AppsV1Api()
    deployments = apps_v1.list_deployment_for_all_namespaces()

    k8s_with_http_probes = set()
    k8s_without_http_probes = {}

    for deploy in deployments.items:
        ns = deploy.metadata.namespace
        name = deploy.metadata.name

        has_http_probe = False
        probe_info = None

        for container in deploy.spec.template.spec.containers:
            probe = container.liveness_probe
            if probe and probe.http_get:
                has_http_probe = True
                probe_info = f"{probe.http_get.path or '/'} port={probe.http_get.port}"
                break

        if has_http_probe:
            k8s_with_http_probes.add((ns, name))
        else:
            probe_type = "none"
            for container in deploy.spec.template.spec.containers:
                probe = container.liveness_probe
                if probe:
                    if probe.tcp_socket:
                        probe_type = "tcp"
                        probe_info = f"port={probe.tcp_socket.port}"
                    elif probe._exec:
                        probe_type = "exec"
                        probe_info = "command"
                    break
            k8s_without_http_probes[(ns, name)] = (probe_type, probe_info)

    # Fetch from Warden
    api_key = os.environ.get("WARDEN_API_KEY")
    if not api_key:
        log.error("missing_api_key")
        return

    client_http = httpx.Client(
        base_url="http://warden.home.arpa",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    resp = client_http.get("/api/uptime")
    resp.raise_for_status()

    uptime_data = UptimeResponse.model_validate(resp.json())

    warden_monitors = set()
    warden_details = {}

    if uptime_data.groups:
        for group in uptime_data.groups:
            for monitor in group.monitors:
                key = (group.name, monitor.name)
                warden_monitors.add(key)
                warden_details[key] = {
                    "url": str(monitor.url),
                    "status": monitor.status,
                    "active": monitor.active,
                }

    # Print comparison
    print("\n" + "=" * 80)
    print("📊 KUBERNETES vs WARDEN COMPARISON")
    print("=" * 80 + "\n")

    print(f"✅ Deployments WITH HTTP probes: {len(k8s_with_http_probes)}\n")
    for ns, name in sorted(k8s_with_http_probes):
        in_warden = (ns, name) in warden_monitors
        emoji = "✓" if in_warden else "✗"
        print(f"   {emoji} {ns}/{name}")

    print(f"\n❌ Deployments WITHOUT HTTP probes: {len(k8s_without_http_probes)}\n")
    for (ns, name), (probe_type, probe_info) in sorted(k8s_without_http_probes.items()):
        in_warden = (ns, name) in warden_monitors
        status = ""
        if in_warden:
            details = warden_details[(ns, name)]
            status_emoji = {
                "up": "🟢",
                "down": "🔴",
                "degraded": "🟡",
                "paused": "⏸️",
            }.get(details["status"], "❓")
            status = f" [{status_emoji} {details['status']}] {details['url']}"

        print(
            f"   {ns}/{name} (probe: {probe_type}{f' {probe_info}' if probe_info else ''}){status}"
        )

    print("\n🔍 Monitors in Warden NOT matching any deployment:")
    for group_name, monitor_name in sorted(warden_monitors):
        if (group_name, monitor_name) not in k8s_with_http_probes and (
            group_name,
            monitor_name,
        ) not in k8s_without_http_probes:
            details = warden_details[(group_name, monitor_name)]
            status_emoji = {
                "up": "🟢",
                "down": "🔴",
                "degraded": "🟡",
                "paused": "⏸️",
            }.get(details["status"], "❓")
            print(
                f"   {group_name}/{monitor_name} [{status_emoji} {details['status']}]"
            )
            print(f"      URL: {details['url']}")

    print("\n" + "=" * 80)
    print("💡 SUMMARY")
    print("=" * 80)
    print(f"  K8s with HTTP probes:    {len(k8s_with_http_probes)}")
    print(f"  K8s without HTTP probes:  {len(k8s_without_http_probes)}")
    print(f"  Total in Warden:          {len(warden_monitors)}")
    print()

    client_http.close()


if __name__ == "__main__":
    main()
