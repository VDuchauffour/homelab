______________________________________________________________________

## name: ssh-reverse-proxy description: Connect to and manage the Scaleway reverse proxy instance via SSH. Use when managing Pangolin, Traefik, CrowdSec, or Docker services on the proxy, or troubleshooting external access. compatibility: Requires SSH access configured in ~/.ssh/config metadata: author: homelab version: "1.0"

# SSH into Reverse Proxy

## Getting the SSH Command

The SSH hostname matches the `instance_name` value in `infra/modules/scaleway-proxy/terraform.tfvars`. This works because the instance name is configured as an SSH host alias (via `.ssh/config`).

```shell
# Read the instance name from tfvars
grep instance_name infra/modules/scaleway-proxy/terraform.tfvars
```

Then SSH with:

```shell
ssh <instance_name>
```

## Working Directory

The Pangolin stack (Docker Compose) lives in `~/pangolin` on the instance:

```shell
ssh <instance_name>
cd pangolin
```

All `docker` and `docker compose` commands should be run from this directory.

## Common Operations

### Docker Compose

```shell
# Stack status
docker compose ps

# Restart a service
docker compose restart <service>

# View logs
docker compose logs <service> --tail 50
docker logs <container_name>
```

### CrowdSec

```shell
# List active bans
docker exec crowdsec cscli decisions list

# Remove ban for specific IP
docker exec crowdsec cscli decisions delete --ip <IP>

# Check metrics (bouncer stats, scenarios, parsers)
docker exec crowdsec cscli metrics

# Manage allowlists
docker exec crowdsec cscli allowlists list
docker exec crowdsec cscli allowlists create <name> --description "<desc>"
docker exec crowdsec cscli allowlists add <name> <IP_OR_CIDR> -d "<comment>"

# Check bouncer connectivity
docker exec crowdsec cscli bouncers list
```

### Traefik

```shell
# Live config is at: config/traefik/dynamic_config.yml
# Traefik auto-reloads when this file changes (file provider)

# Check Traefik logs
docker logs traefik --tail 50
```

### Certificates

```shell
# Check Let's Encrypt cert status
cat config/letsencrypt/acme.json | python3 -m json.tool | grep -A2 '"main"'
```

## Host Firewall Bouncer

The CrowdSec firewall bouncer runs directly on the host (not in Docker):

```shell
systemctl status crowdsec-firewall-bouncer
journalctl -u crowdsec-firewall-bouncer --no-pager -n 50
```

## SSH Host Key Changes

If Terraform rebuilds the instance, the SSH host key will change. Fix with:

```shell
ssh-keygen -R <instance_ip>
ssh -o StrictHostKeyChecking=accept-new <instance_name>
```

Get the instance IP from:

```shell
cd infra/modules/scaleway-proxy
terraform output
```

## Config Files on Instance

| Path (relative to `~/pangolin`) | Description |
|---|---|
| `compose.yaml` | Docker Compose stack |
| `config/config.yml` | Pangolin configuration |
| `config/traefik/traefik_config.yml` | Traefik static config |
| `config/traefik/dynamic_config.yml` | Traefik dynamic config (middlewares, routers) |
| `config/traefik/ban.html` | CrowdSec ban page |
| `config/traefik/logs/` | Traefik access logs |
| `config/crowdsec/` | CrowdSec config and DB |
| `config/crowdsec/acquis.d/` | CrowdSec acquisition configs (traefik, syslog, appsec) |
| `config/letsencrypt/acme.json` | Let's Encrypt certificates |
| `config/postgres/` | PostgreSQL data |

## Important Notes

- **Do NOT use `ss` inside the CrowdSec container** — it's not installed. Use `docker logs` to check if services (like AppSec on port 7422) are running.
- Changes to `dynamic_config.yml` are auto-reloaded by Traefik. Changes to `traefik_config.yml` require a Traefik restart.
- Config files on the instance are **not managed by Terraform after initial provisioning**. To persist changes across rebuilds, update the `.tftpl` templates in `infra/modules/scaleway-proxy/`.
