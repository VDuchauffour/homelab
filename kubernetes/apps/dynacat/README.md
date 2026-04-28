# Glance

Note for qBittorrent: You need to whitelist Glance's IP in qBittorrent Web UI settings:

- Tools → Options → Web UI → Authentication
- Check "Bypass authentication for clients in whitelisted IP subnets"
- Add your cluster pod CIDR, you find it with `kubectl get nodes -o jsonpath='{.items[*].spec.podCIDR}'`

Note for Uptime Kuma: Make sure you have a status page with slug homelab configured. Adjust the slug in helmfile if different.
