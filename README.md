# An opinionated Kubernetes-based homelab

All the configuration and manifests for running my homelab on Kubernetes.

## Architecture Overview

```
Internet → Scaleway Proxy (Pangolin + Gerbil + Traefik + CrowdSec) → Homelab K8s Cluster (Traefik Ingress)
```

Selected services are exposed to the Internet through a reverse proxy hosted on a Scaleway instance. Traffic is tunneled from the proxy to the cluster using [Pangolin](https://pangolin.net/) with WireGuard (Gerbil). Everything else stays on the local network, secured with mkcert-issued TLS certificates.

## Key Technologies

| Component | Technology |
|-----------|------------|
| Container Orchestration | Kubernetes |
| Package Management | Helmfile + Helm |
| Storage | Rancher Local Path, OpenEBS ZFS-LocalPV (configs), NFS CSI (shared media) |
| Database | CloudNativePG (PostgreSQL) + Barman Cloud Plugin (backups to MinIO) |
| Ingress | Traefik |
| TLS | cert-manager (mkcert CA for local, Let's Encrypt for public) |
| GPU | Intel Device Plugins (iGPU/QSV) |
| Monitoring | kube-prometheus-stack |
| Auth | TinyAuth |
| External Proxy | Pangolin + Gerbil + Traefik (Scaleway) |
| Security | CrowdSec (WAF + AppSec + host firewall bouncer) |
| IaC | Terraform |

## Project Structure

```
homelab/
├── kubernetes/
│   ├── apps/         # User-facing application workloads
│   ├── infra/        # Cluster-wide infrastructure services
│   └── cluster/      # Shared resources (namespaces, storage classes, certificates, CNPG definitions)
│
└── infra/
    └── modules/
        └── scaleway-proxy/   # Terraform for the external reverse proxy
```

- **`kubernetes/apps/`** — Each subdirectory is a user-facing application deployed via Helmfile (e.g. Jellyfin, Sonarr, n8n).
- **`kubernetes/infra/`** — Cluster infrastructure services: storage backends, database operator, cert-manager, monitoring, GPU plugins. Also deployed via Helmfile (or kustomize for nfs-server).
- **`kubernetes/cluster/`** — Cluster-level definitions that don't belong to a single app: namespaces, storage classes, certificate issuers, CloudNativePG cluster and database CRs, persistent volumes.
- **`infra/`** — Terraform modules for resources outside the cluster (currently the Scaleway reverse proxy).

## Getting Started

### Prerequisites

- A Kubernetes cluster
- [Helm](https://helm.sh/) + [Helmfile](https://github.com/helmfile/helmfile)
- [kubectl](https://kubernetes.io/docs/tasks/tools/)
- [direnv](https://direnv.net/)
- [vals](https://github.com/helmfile/vals)
- [Terraform](https://www.terraform.io/) (only needed for the external reverse proxy)

### Environment Configuration

This project uses [direnv](https://direnv.net/) to manage environment variables. Helmfile relies on [vals](https://github.com/helmfile/vals) to inject these variables into Helm values at deploy time.

1. Install direnv following the [official installation guide](https://direnv.net/docs/installation.html)

2. Copy the example environment file:

```shell
cp .envrc.example .envrc
```

3. Edit `.envrc` and fill in the required values:

```shell
vim .envrc
```

4. Allow direnv to load the environment:

```shell
direnv allow
```

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `HOME_DIR` | Home directory of the user on the host machine | `/home/user` |
| `EMAIL_ADDRESS` | Your email address used for various services | `user@example.com` |
| `PUBLIC_DOMAIN_NAME` | Your homelab public domain name | `example.com` |
| `LOCAL_DOMAIN_NAME` | Your homelab internal domain name | `home.arpa` |
| `SINGLE_NODE_NAME` | Name of the single Kubernetes node | `k8s-node` |
| `PASSBOLT_BASE_URL` | Base URL for Passbolt password manager | `http://passbolt.ref+envsubst://$LOCAL_DOMAIN_NAME` |
| `PASSBOLT_GPG_KEY_FILE` | Path to your Passbolt GPG private key file | `/home/user/.gnupg/passbolt-key.asc` |
| `PASSBOLT_GPG_PASSPHRASE` | Passphrase for your Passbolt GPG key | (keep secure) |
| `PANGOLIN_PROXY_IP` | Public IP of the Scaleway proxy instance (for CoreDNS split-horizon) | `163.172.x.x` |
| `TRAEFIK_CLUSTER_IP` | ClusterIP of the Traefik service (for CoreDNS split-horizon) | `10.43.x.x` |

Once configured, these variables will be automatically loaded whenever you enter the project directory.

## Kubernetes — Applications

### Available Apps

<details>
<summary>Apps</summary>

| | App | Description | Deployed via |
|:--:|-----|-------------|:------------:|
| <img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/bazarr.png" width="32"> | bazarr | Subtitle management for media | Helmfile |
| <img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/dozzle.png" width="32"> | dozzle | Real-time log viewer for containers | Helmfile |
| <img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/glance.png" width="32"> | glance | Personal dashboard | Helmfile |
| <img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/headlamp.png" width="32"> | headlamp | Kubernetes web UI | Helmfile |
| <img src="https://raw.githubusercontent.com/komodorio/helm-dashboard/refs/heads/main/images/logo.png" width="32"> | helm-dashboard | Helm charts management UI | Helmfile |
| <img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/immich.png" width="32"> | immich | Self-hosted photo and video management | Helmfile |
| <img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/jellyfin.png" width="32"> | jellyfin | Media server with live TV | Helmfile |
| <img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/jellyseerr.png" width="32"> | jellyseerr | Media request management | Helmfile |
| <img src="https://raw.githubusercontent.com/kanbn/kan/refs/heads/main/apps/web/public/favicon.ico" width="32"> | kan | Kanban board | Helmfile |
| <img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/lidarr.png" width="32"> | lidarr | Music collection manager | Helmfile |
| <img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/linkding.png" width="32"> | linkding | Minimal bookmark manager | Helmfile |
| <img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/linkwarden.png" width="32"> | linkwarden | Collaborative bookmark manager | Helmfile |
| <img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/memos.png" width="32"> | memos | Lightweight self-hosted memo hub | Helmfile |
| <img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/n8n.png" width="32"> | n8n | Workflow automation platform | Helmfile |
| <img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/opencode.png" width="32"> | opencode | AI-powered coding assistant with built-in web UI | Helmfile |
| <img src="https://raw.githubusercontent.com/btriapitsyn/openchamber/20f158f2b71b66aef0235531b5092ba82cda720f/packages/vscode/assets/app-icon.png" width="32"> | openchamber | [OpenChamber](https://github.com/btriapitsyn/openchamber) web UI for OpenCode | Helmfile |
| <img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/pgadmin.png" width="32"> | pgadmin | PostgreSQL management UI | Helmfile |
| <img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/privatebin.png" width="32"> | privatebin | Encrypted pastebin for sharing secrets | Helmfile |
| <img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/prowlarr.png" width="32"> | prowlarr | Indexer manager for arr suite | Helmfile |
| <img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/qbittorrent.png" width="32"> | qbittorrent-vpn | BitTorrent client with VPN | Helmfile |
| <img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/radarr.png" width="32"> | radarr | Movie collection manager | Helmfile |
| <img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/sonarr.png" width="32"> | sonarr | TV show collection manager | Helmfile |
| <img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/scrutiny.png" width="32"> | scrutiny | Hard drive S.M.A.R.T health monitoring | Helmfile |
| <img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/stirling-pdf.png" width="32"> | stirling-pdf | PDF manipulation toolkit | Helmfile |
| <img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/tdarr.png" width="32"> | tdarr | Media transcoding optimizer | Helmfile |
| <img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/uptime-kuma.png" width="32"> | uptime-kuma | Uptime monitoring dashboard | Helmfile |
| <img src="https://raw.githubusercontent.com/projecthelena/warden/702a44724394d9841d86992b800d8df763023b9b/assets/favicon.svg" width="32"> | warden | Service health monitoring and alerting | Helmfile |
| <img src="https://raw.githubusercontent.com/ad4mts/zfdash/refs/heads/main/src/data/icons/zfs-gui.png" width="32"> | zfdash | ZFS monitoring dashboard | Helmfile |
| <img src="./kubernetes/apps/glance/assets/favicons/vibe-kanban.png" width="32"> | vibe-kanban | Kanban project management for vibe coding | Helmfile |

</details>

### App-Specific Notes

#### Headlamp

Generate an admin token to log in:

```shell
kubectl create token headlamp-admin -n kube-system
```

#### OpenCode & OpenChamber

Both apps share the same host directories for projects and worktrees. PVs will look at these locations:

- `$HOME_DIR/projects` — project working directory
- `$HOME_DIR/worktrees` — git worktrees

Each app has its own config PVC (ZFS-backed) but shares the workdir and worktree PVs.

You will need to add your SSH keys for GitHub and your git config.

#### Passbolt

Once the chart is applied, run the following command to set up an admin user:

```shell
kubectl exec -it -n passbolt <passbolt-pod-name> -- su -c "bin/cake passbolt register_user -u <email> -f <firstname> -l <lastname> -r admin" -s /bin/bash www-data
```

## Kubernetes — Infrastructure

### Available Infrastructure tools

<details>
<summary>Infrastructure Tools</summary>

| | Tool | Description | Deployed via |
|:--:|------|-------------|:------------:|
| <img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/cert-manager.png" width="32"> | cert-manager | TLS certificate automation | Helmfile |
| <img src="https://raw.githubusercontent.com/cloudnative-pg/cloudnative-pg.github.io/refs/heads/main/assets/images/hero_image.png" width="32"> | cloudnative-pg | PostgreSQL operator for K8s | Helmfile |
| <img src="https://upload.wikimedia.org/wikipedia/commons/thumb/8/85/Intel_logo_2023.svg/1280px-Intel_logo_2023.svg.png" width="32"> | intel-device-plugins | GPU and device plugin for Intel hardware | Helmfile |
| <img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/prometheus.png" width="32"> | kube-prometheus-stack | Monitoring and alerting stack | Helmfile |
| <img src="https://raw.githubusercontent.com/minio/minio/master/.github/logo.svg?sanitize=true" width="32"> | minio | High-performance blob storage | Helmfile |
| <img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/kubernetes.png" width="32"> | nfs-csi-driver | NFS CSI driver for RWX volumes | Helmfile |
| <img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/kubernetes.png" width="32"> | nfs-server | In-cluster NFS server for shared media | Kustomize |
| <img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/kubernetes.png" width="32"> | node-feature-discovery | Hardware feature discovery | Helmfile |
| <img src="https://raw.githubusercontent.com/cncf/artwork/master/projects/openebs/stacked/color/openebs-stacked-color.png" width="32"> | openebs | Container-native storage solution | Helmfile |
| <img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/pangolin.png" width="32"> | pangolin-newt | Newt tunnel client for external access via Pangolin | Helmfile |
| <img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/passbolt.png" width="32"> | passbolt | Team password manager | Helmfile |
| <img src="https://raw.githubusercontent.com/cloudnative-pg/cloudnative-pg.github.io/refs/heads/main/assets/images/hero_image.png" width="32"> | plugin-barman-cloud | Backup plugin for CloudNativePG (WAL archiving + base backups to MinIO) | Helmfile |

</details>

### Storage

The cluster uses three storage backends optimized for different use cases:

| StorageClass | Backend | Access Mode | Use Case |
|--------------|---------|-------------|----------|
| `local-path` | Rancher Local Path | RWO | App data |
| `zfs-vm-pool-dynamic` | OpenEBS ZFS-LocalPV | RWO | App configs, databases |
| `nfs-tank-media` | NFS CSI | RWX | Shared media (arr suite, Jellyfin) |

All storage uses **Retain** reclaim policy to prevent accidental data loss. You can use the [kubectl plugin for openebs](https://openebs.io/docs/user-guides/kubectl-openebs#install-kubectl-plugin) to help manage the storage volumes.

#### Local Path

Rancher Local Path utilizes the local storage in each node. Installation instructions can be found [here](https://github.com/rancher/local-path-provisioner).

#### ZFS-LocalPV (App Configs)

OpenEBS ZFS-LocalPV provides high-performance local storage backed by ZFS on the `vm-pool` dataset.

- **StorageClass**: `zfs-vm-pool-dynamic`
- **Features**: Compression (lz4), snapshots, dynamic provisioning
- **Location**: `/vm-pool/<pvc-uuid>` on single node

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: app-config
spec:
  accessModes: [ReadWriteOnce]
  storageClassName: zfs-vm-pool-dynamic
  resources:
    requests:
      storage: 1Gi
```

#### NFS Storage (Shared Media)

ReadWriteMany (RWX) volumes via an in-cluster NFS server, following the OpenEBS NFS provisioning pattern.

```
Pod → NFS CSI Driver → NFS Server Pod → hostPath (/mnt/tank/media)
```

- **StorageClass**: `nfs-tank-media` (dynamic), `nfs-media-library` (static)
- **NFS Server**: `nfs-server.nfs-server.svc.cluster.local`
- **Backend**: hostPath to `/mnt/tank/media` on single node

Static PVs for shared media are defined in `kubernetes/cluster/persistent-volumes/media.yaml`.

### Database (PostgreSQL)

All postgres databases run in a [CloudNativePG cluster](https://cloudnative-pg.io/). The cluster uses dynamically provisioned ZFS-backed PVCs (`zfs-vm-pool-dynamic`).

Backups are handled by the [Barman Cloud Plugin](https://cloudnative-pg.io/plugin-barman-cloud/) with WAL archiving and daily base backups to MinIO (`cnpg-backups` bucket). Configuration is in `kubernetes/cluster/cloudnative-pg/backup.yaml`.

You can use the [kubectl plugin for cnpg](https://cloudnative-pg.io/documentation/1.20/kubectl-plugin/) to manage the cluster:

```shell
# Cluster status (includes backup info)
kubectl cnpg status cnpg-cluster0 -n cnpg-clusters

# List databases
kubectl get database -n cnpg-clusters

# Check backups
kubectl get backup -n cnpg-clusters
kubectl get scheduledbackup -n cnpg-clusters
```

### TLS Certificates

Local network services use TLS certificates issued by a mkcert CA through cert-manager. The CA secret and ClusterIssuer are defined in `kubernetes/cluster/certificates/`.

To recreate the CA secret (e.g. after a fresh cluster install):

```shell
CERT_DIR=$(mkcert -CAROOT)
kubectl create secret tls mkcert-ca-key-pair -n cert-manager --cert=$CERT_DIR/rootCA.pem --key=$CERT_DIR/rootCA-key.pem
kubectl apply -f kubernetes/cluster/certificates/mkcert-ca-issuer.yaml
```

Adding the following annotation to an ingress will make cert-manager automatically:

- Create a Certificate resource
- Issue a leaf cert signed by your mkcert CA
- Manage renewals automatically
- Maintain the TLS Secret

```yaml
ingress:
  enabled: true
  className: traefik
  annotations:
    kubernetes.io/ingress.class: traefik
    cert-manager.io/cluster-issuer: mkcert-ca
```

Public-facing services get their TLS from Traefik (Let's Encrypt) on the Scaleway proxy via Pangolin — see [External Access](#external-access).

### GPU

Intel iGPU is available for hardware transcoding (Jellyfin, Tdarr) via the Intel Device Plugins operator.

```shell
kubectl get gpudeviceplugins
```

Host-level diagnostics:

- `intel_gpu_top` (from `intel-gpu-tools`) — live GPU usage
- `vainfo` (from `libva-utils`) — supported VAAPI profiles
- `clinfo` (from `clinfo`) — OpenCL availability

More info [here](https://intel.github.io/intel-device-plugins-for-kubernetes/cmd/gpu_plugin/README.html).

### Monitoring

The cluster runs [kube-prometheus-stack](https://github.com/prometheus-community/helm-charts/tree/main/charts/kube-prometheus-stack) for monitoring and alerting. Configuration is in `kubernetes/infra/kube-prometheus-stack/`.

## External Access

The homelab is exposed to the Internet through [Pangolin](https://pangolin.net/) hosted on a Scaleway instance. The infrastructure is provisioned with Terraform (`infra/modules/scaleway-proxy/`) and the services run in Docker on the instance. Exposed resources are managed declaratively via a [Pangolin blueprint](https://docs.pangolin.net/manage/blueprints).

### Architecture

```
Internet → Traefik (80/443) → Pangolin → Gerbil (WireGuard) → Newt (in-cluster) → K8s services
```

### Components

- **Pangolin** — Tunnel management platform with a web dashboard for configuring exposed services.
- **Gerbil** — WireGuard-based tunnel controller. Manages encrypted tunnels between the proxy and homelab.
- **Traefik** — Reverse proxy with automatic HTTPS via Let's Encrypt. Handles TLS termination and routing.
- **CrowdSec** — Collaborative behavior detection engine with WAF (AppSec), Traefik bouncer plugin, and host firewall bouncer for SSH protection.
- **Newt** — Tunnel client running in-cluster (`kubernetes/infra/pangolin-newt/`). Connects to Gerbil and routes traffic to K8s services.

### Blueprint (Declarative Resource Config)

All externally-accessible services are defined in a blueprint file (`kubernetes/infra/pangolin-newt/manifests/blueprint.yaml`). The blueprint is a ConfigMap that Newt reads on startup, declaratively configuring domains, auth settings, and healthchecks.

- **Public (no auth)**: jellyfin, jellyseerr, immich
- **Admin-only (SSO whitelist)**: all other apps and infra tools

To add a new externally-accessible service, add a resource block to the blueprint and redeploy:

```shell
# Deploy blueprint + Newt together
cd kubernetes/infra/pangolin-newt
helmfile apply

# Or update the blueprint only
vals eval -f manifests/blueprint.yaml | kubectl apply -f -
kubectl rollout restart deployment/fossorial-newt-main-tunnel -n fossorial
```

> **Note:** `sso-roles` cannot include "Admin" (reserved by Pangolin). Use `whitelist-users` with email addresses instead. The blueprint YAML lives inside a ConfigMap literal block — indentation errors are silently ignored, so always validate rendered output with `vals eval`.

### CoreDNS (Split-Horizon DNS)

Custom CoreDNS configuration (`kubernetes/cluster/coredns/coredns-custom.yaml`) implements split-horizon DNS so that in-cluster traffic to `*.<public-domain>` resolves to the internal Traefik ClusterIP instead of hairpinning through the Internet.

**Exception:** `pangolin.<public-domain>` resolves to the Scaleway proxy IP so the Newt tunnel client can reach Pangolin directly (otherwise it would get Traefik's IP via the wildcard rule and fail TLS handshake).

```shell
vals eval -f kubernetes/cluster/coredns/coredns-custom.yaml | kubectl apply -f -
kubectl rollout restart deployment coredns -n kube-system
```

Requires environment variables: `PANGOLIN_PROXY_IP` and `TRAEFIK_CLUSTER_IP` (see [Environment Variables](#environment-variables)).

### Scaleway Proxy (Terraform)

You'll need a [Scaleway config file](https://cli.scaleway.com/config/).

```shell
cd ./infra/modules/scaleway-proxy

cp ./terraform.tfvars.example ./terraform.tfvars
# edit the file with the relevant values
# generate pangolin_secret with: openssl rand -base64 48

terraform init
terraform plan
terraform apply
```

Once the instance is ready, run:

```shell
cd "$HOME_DIR/pangolin"
docker compose up -d
```

Then navigate to `https://pangolin.<domain>/auth/initial-setup` to complete the initial setup. The setup token is printed in the Pangolin container logs (`docker compose logs pangolin`).

After Terraform apply, also deploy the CoreDNS config (see above) and the Newt blueprint to complete the external access setup.

### CrowdSec (WAF + Host Protection)

The Scaleway proxy runs [CrowdSec](https://www.crowdsec.net/) for multi-layer security, deployed automatically via Terraform/cloud-init:

- **Traefik bouncer plugin** — Inspects all incoming HTTP/HTTPS requests via the `crowdsec-bouncer-traefik-plugin`. Banned IPs get a ban page. AppSec (virtual patching) is enabled for WAF-level protection.
- **Syslog monitoring** — CrowdSec reads `/var/log/auth.log` and `/var/log/syslog` to detect SSH brute-force and other host-level attacks.
- **Host firewall bouncer** — `crowdsec-firewall-bouncer-iptables` runs on the host and adds iptables rules to DROP banned IPs at the network level (covers SSH and any non-HTTP traffic).

Bouncer API keys are pre-registered via `BOUNCER_KEY_*` environment variables in the CrowdSec container, so no manual key generation is needed after deploy.

Useful commands (SSH into the proxy):

```shell
docker exec crowdsec cscli metrics                              # View bouncer stats
docker exec crowdsec cscli decisions list                       # List active bans
docker exec crowdsec cscli decisions add --ip <IP> -d 1m --type ban  # Manually ban an IP (1 min)
systemctl status crowdsec-firewall-bouncer                      # Host bouncer status
```

### Destroy

```shell
cd ./infra/modules/scaleway-proxy
terraform destroy
```

> **Note:** Scaleway allows duplicate DNS records. After `terraform destroy` and a fresh `terraform apply`, check for stale A records (apex `@` and wildcard `*`) pointing to the old instance IP. Duplicates will cause ACME certificate issuance to fail intermittently. Remove them manually from the Scaleway console.

## Utility Scripts

The `scripts/` directory contains utility scripts for managing the homelab cluster.

### Warden Monitoring Tools

The `warden/` package provides Kubernetes-to-Warden monitoring integration with automatic discovery, deployment verification, and cleanup capabilities.

**Quick Start:**

```shell
make warden-seed          # Seed app monitors
make warden-seed-cleanup  # Seed with cleanup
make warden-delete        # Delete all monitors
make warden-compare       # Compare K8s vs Warden
```

See [`scripts/warden/README.md`](scripts/warden/README.md) for detailed documentation.

### Passbolt Custom Field Tool

The `passbolt/` package adds custom key-value fields to new or existing Passbolt secrets via the GPG-authenticated API. Requires `PASSBOLT_BASE_URL`, `PASSBOLT_GPG_KEY_FILE`, `PASSBOLT_GPG_PASSPHRASE`.

```shell
cd scripts
uv run passbolt-add-field --name "MyApp" --password "s3cret" --field-name "api_key" --field-value "tok-123"
uv run passbolt-add-field --resource-name "MyApp" --field-name "env" --field-value "production"
```

## Useful Commands

Generate a strong password:

```shell
pwgen -scyn 32 1
or
openssl rand -base64 32
```

## Acknowledgments

- Some charts are inspired by [rtomik's helm-charts repository](https://github.com/rtomik/helm-charts)
