# Homelab Documentation

A Kubernetes-based homelab with cloud infrastructure for secure external access.

## Architecture Overview

```
Internet → Scaleway Proxy (Pangolin + Gerbil + Traefik + CrowdSec) → Homelab K8s Cluster
```

- **External Access**: Scaleway-hosted reverse proxy with Pangolin (WireGuard tunneling via Gerbil)
- **Internal**: Kubernetes cluster with Traefik ingress and cert-manager

## Project Structure

```
homelab/
├── kubernetes/
│   ├── apps/                    # User applications
│   ├── infra/                   # Infrastructure services
│   │   └── pangolin-newt/       # Newt tunnel client + blueprint for external access
│   └── cluster/                 # Cluster-wide definitions
│       ├── coredns/             # CoreDNS custom config (split-horizon DNS)
│       └── cloudnative-pg/      # CNPG cluster, databases, backups
│
├── infra/
│   └── modules/
│       └── scaleway-proxy/      # Terraform for reverse proxy (Pangolin, Gerbil, Traefik)
│
├── scripts/                     # Python utility scripts (uv, Python 3.12+)
│   ├── pyproject.toml           # Shared project config, dependencies, CLI entry points
│   ├── warden/                  # Kubernetes-to-Warden monitoring integration
│   └── passbolt/                # Passbolt secret management (custom fields)
│
└── README.md                    # Main documentation
```

## App Structure Convention

Each app follows this pattern:

```
app-name/
├── helmfile.yaml       # Helmfile release definition
├── values.yaml         # Helm values override
├── manifests/          # Raw K8s manifests (PVs, secrets, etc.)
│   ├── pv.yaml
│   └── secret.yaml
└── charts/             # Custom Helm chart (if not using external)
    └── app-name/
        ├── Chart.yaml
        ├── values.yaml
        └── templates/
```

## Key Technologies

| Component | Technology |
|-----------|------------|
| Container Orchestration | Kubernetes |
| Package Management | Helmfile + Helm |
| Storage | Rancher Local Path, OpenEBS ZFS-LocalPV (configs), NFS CSI (shared media) |
| Database | CloudNativePG (PostgreSQL) + Barman Cloud Plugin (backups to RustFS) |
| Ingress | Traefik |
| TLS | cert-manager (mkcert CA for local, Let's Encrypt for public) |
| GPU | Intel Device Plugins (iGPU/QSV) |
| Monitoring | kube-prometheus-stack |
| Auth | TinyAuth |
| External Proxy | Pangolin + Gerbil + Traefik (Scaleway) |
| Security | CrowdSec (WAF + AppSec + host firewall bouncer) |
| IaC | Terraform |

## Deployment Patterns

### Internal Apps (via Helmfile)

```shell
cd kubernetes/apps/<app-name>
helmfile apply
```

### External Proxy (via Terraform)

```shell
cd infra/modules/scaleway-proxy
terraform apply -var-file=terraform.tfvars
```

## TLS Configuration

- **Local network**: mkcert CA via cert-manager ClusterIssuer
- **Public access**: Let's Encrypt via Traefik (on Scaleway proxy, managed by Pangolin)

Add to ingress for local TLS:

```yaml
annotations:
  cert-manager.io/cluster-issuer: mkcert-ca
```

## GPU Support

Intel iGPU is available for hardware transcoding (Jellyfin, Tdarr).

Check status:

```shell
kubectl get gpudeviceplugins
intel_gpu_top  # On host
```

## Storage

The cluster uses three storage backends optimized for different use cases:

| StorageClass | Backend | Access Mode | Use Case |
|--------------|---------|-------------|----------|
| `local-path` | Rancher Local Path | RWO | App data |
| `zfs-vm-pool-dynamic` | OpenEBS ZFS-LocalPV | RWO | App configs, databases |
| `nfs-tank-media` | NFS CSI | RWX | Shared media (arr suite, Jellyfin) |

All storage uses **Retain** reclaim policy to prevent accidental data loss.

### ZFS-LocalPV (App Configs)

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

### NFS Storage (Shared Media)

ReadWriteMany (RWX) volumes via an in-cluster NFS server, following the OpenEBS NFS provisioning pattern.

#### Architecture

```
Pod → NFS CSI Driver → NFS Server Pod → hostPath (/mnt/tank/media)
```

- **StorageClass**: `nfs-tank-media` (dynamic), `nfs-media-library` (static)
- **NFS Server**: `nfs-server.nfs-server.svc.cluster.local`
- **Backend**: hostPath to `/mnt/tank/media` on single node

#### Components

1. **NFS Server** (`kubernetes/infra/nfs-server/`)

   - Deployment + Service exposing `/mnt/tank/media` via NFS
   - Pinned to single node via nodeSelector

2. **NFS CSI Driver** (`kubernetes/infra/nfs-csi-driver/`)

   - kubernetes-csi/csi-driver-nfs for dynamic PVC provisioning

#### Deployment

```shell
kubectl apply -k kubernetes/infra/nfs-server/manifests/
cd kubernetes/infra/nfs-csi-driver && helmfile apply
```

#### Static vs Dynamic NFS PVCs

- **Static PVs** (`kubernetes/cluster/persistent-volumes/media.yaml`): Used by arr suite, Jellyfin, qBittorrent to share the same `/mnt/tank/media` root
- **Dynamic PVCs** (`nfs-tank-media` StorageClass): Creates subdirectories per PVC, useful for isolated app data

## Database (CloudNativePG)

The cluster runs a single CloudNativePG instance (`cnpg-cluster0`) in namespace `cnpg-clusters` with dynamically provisioned ZFS storage (`zfs-vm-pool-dynamic`, 10Gi).

- **Operator**: `kubernetes/infra/cloudnative-pg/` (Helmfile, chart v0.26.1)
- **Cluster + Secrets**: `kubernetes/cluster/cloudnative-pg/cluster0.yaml`
- **Database CRs**: `kubernetes/cluster/cloudnative-pg/{kan,n8n,linkwarden,linkding}.yaml`
- **Backup config**: `kubernetes/cluster/cloudnative-pg/backup.yaml` (ObjectStore + ScheduledBackup + RustFS credentials)

### Backups

Backups use the [Barman Cloud Plugin](https://cloudnative-pg.io/plugin-barman-cloud/) (`kubernetes/infra/plugin-barman-cloud/`):

- **WAL archiving**: Continuous to RustFS with gzip compression
- **Base backups**: Daily at 2:00 AM UTC via `ScheduledBackup` CR
- **Destination**: RustFS bucket `cnpg-backups` at `http://rustfs-svc.rustfs.svc.cluster.local:9000`
- **Retention**: 30 days
- **Credentials**: Secret `rustfs-cnpg-credentials` in `cnpg-clusters` namespace (keys: `ACCESS_KEY_ID`, `ACCESS_SECRET_KEY`)

Check backup status:

```shell
kubectl cnpg status cnpg-cluster0 -n cnpg-clusters
kubectl get backup -n cnpg-clusters
kubectl get scheduledbackup -n cnpg-clusters
kubectl get objectstore -n cnpg-clusters
```

### Adding a New Database

1. Create a credentials secret + `Database` CR in `kubernetes/cluster/cloudnative-pg/<app>.yaml`
2. Add a managed role in `cluster0.yaml` under `spec.managed.roles`
3. Apply with `vals eval -f <file> | kubectl apply -f -`

### Reclaim Policy

All PVs use `Retain` policy. If a PVC is deleted:

- PV moves to `Released` state
- Data is preserved on disk
- Manual cleanup required: `kubectl delete pv <pv-name>`

To check/fix reclaim policy:

```shell
kubectl get pv -o custom-columns='NAME:.metadata.name,RECLAIM:.spec.persistentVolumeReclaimPolicy'
kubectl patch pv <pv-name> -p '{"spec":{"persistentVolumeReclaimPolicy":"Retain"}}'
```

## Dashboard (Glance)

The homelab uses [Glance](https://github.com/glanceapp/glance) as a personal dashboard. It runs as **two instances** (public + local) from a single helmfile in `kubernetes/apps/glance/`.

### Architecture

- **glance-public**: Exposed via Pangolin (public domain), no local ingress
- **glance-local**: Local network only, ingress with mkcert TLS on `dashboard.<local-domain>`
- Both share `values-common.yaml` for bookmark groups, widgets, and API integrations

### Configuration Files

| File | Purpose |
|------|---------|
| `helmfile.yaml` | Two releases (glance-public, glance-local) with vals secrets |
| `values-common.yaml` | Shared bookmarks, widgets (weather, calendar, qBittorrent, Warden) |
| `values-local.yaml` | Local ingress config (mkcert TLS) |
| `values-public.yaml` | Public instance config (ingress disabled — exposed via Pangolin) |
| `charts/glance/` | Custom Helm chart (configmap template generates `glance.yml`) |

### Bookmark Structure

Bookmarks in `values-common.yaml` are organized into groups:

- **`instanceBookmarkGroups`**: Instance-specific links (Proxy, Cluster, Monitoring) — shown in the left sidebar
- **`commonBookmarkGroups`**: Shared app links (Productivity, Tools, Sharing, Media, Arr, AI) — shown in the main area

Each link uses either `url` (full URL) or `subdomain` (auto-expanded to `https://<subdomain>.<domainName>`).

### Adding a New App to the Dashboard

1. Add a bookmark entry to the appropriate group in `kubernetes/apps/glance/values-common.yaml`:

   ```yaml
   - title: MyApp
     subdomain: myapp
     icon: di:myapp  # or sh:myapp, or a raw URL
   ```

2. Redeploy: `cd kubernetes/apps/glance && helmfile apply`

### Icon Conventions

- `di:<name>` — [Dashboard Icons](https://github.com/walkxcode/dashboard-icons) (preferred)
- `sh:<name>` — [Selfh.st Icons](https://selfh.st/icons/)
- Raw URL — GitHub raw links for icons not in the above sets

## External Access (Pangolin Blueprints)

Services are exposed to the Internet through Pangolin on a Scaleway instance. The Newt tunnel client runs in-cluster and uses a **blueprint** to declaratively configure all exposed resources (domains, auth, healthchecks).

### Architecture

```
Internet → Traefik (80/443) → Pangolin → Gerbil (WireGuard) → Newt (in-cluster) → K8s services
```

### Blueprint System

The blueprint (`kubernetes/infra/pangolin-newt/manifests/blueprint.yaml`) is a ConfigMap containing a `blueprint.yaml` key that Newt reads on startup. It declaratively defines:

- **Public resources** (no auth): jellyfin, jellyseerr, immich
- **Admin-only resources** (SSO whitelist): all other apps and infra tools

Each resource specifies: domain, target hostname/port, auth settings, and healthcheck configuration.

**Key constraints:**

- `sso-roles` cannot include "Admin" (reserved by Pangolin) — use `whitelist-users` with email addresses instead
- The blueprint YAML lives inside a ConfigMap literal block (`|`) — indentation errors are silently ignored by Pangolin, always validate with `vals eval`
- Healthcheck blocks must be nested under each target, not at the resource level

### Deployment

```shell
cd kubernetes/infra/pangolin-newt
helmfile apply
```

The helmfile presync hook applies the blueprint ConfigMap before the Newt deployment. To update the blueprint only:

```shell
vals eval -f manifests/blueprint.yaml | kubectl apply -f -
kubectl rollout restart deployment/fossorial-newt-main-tunnel -n fossorial
```

### Adding a New Externally-Accessible Service

1. Add a new resource block to `kubernetes/infra/pangolin-newt/manifests/blueprint.yaml`
2. Set `full-domain`, target `hostname`/`port`, auth settings, and healthcheck
3. Apply with `vals eval -f manifests/blueprint.yaml | kubectl apply -f -`
4. Restart Newt: `kubectl rollout restart deployment/fossorial-newt-main-tunnel -n fossorial`
5. Add a bookmark to the Glance dashboard (see [Adding a New App to the Dashboard](#adding-a-new-app-to-the-dashboard))

## Post-Deployment Checklist (New App or Infra Tool)

After deploying a new app or infra tool, complete these additional steps:

1. **Glance dashboard**: Add a bookmark entry to `kubernetes/apps/glance/values-common.yaml` in the appropriate group, then redeploy Glance (`cd kubernetes/apps/glance && helmfile apply`)
2. **Pangolin blueprint** (if externally accessible): Add a resource block to `kubernetes/infra/pangolin-newt/manifests/blueprint.yaml`, then apply and restart Newt
3. **Warden monitoring**: Run `make warden-seed-cleanup` to discover the new app and sync monitors (adds new, removes stale)
4. **README.md**: Add the app/tool to the appropriate table (Apps or Infrastructure Tools) in `README.md` — run `make check-readme` to verify

## CoreDNS (Split-Horizon DNS)

Custom CoreDNS configuration (`kubernetes/cluster/coredns/coredns-custom.yaml`) implements split-horizon DNS so that in-cluster traffic to `*.<public-domain>` resolves to the internal Traefik ClusterIP instead of going out to the Internet and back.

**Exception:** `pangolin.<public-domain>` resolves to the Scaleway proxy IP so the Newt tunnel client can reach it directly.

### Environment Variables

- `PANGOLIN_PROXY_IP` — Scaleway instance public IP (for CoreDNS pangolin override)
- `TRAEFIK_CLUSTER_IP` — Traefik service ClusterIP (for CoreDNS wildcard override)

### Deployment

```shell
vals eval -f kubernetes/cluster/coredns/coredns-custom.yaml | kubectl apply -f -
kubectl rollout restart deployment coredns -n kube-system
```

### Why This Exists

Without the CoreDNS override, the Newt client resolves `pangolin.<domain>` to the internal Traefik IP (due to the wildcard override), causing TLS handshake failures because Traefik doesn't serve Pangolin's certificate. The separate server block for `pangolin.<domain>` ensures Newt connects to the actual Scaleway proxy.

## Security (CrowdSec)

The Scaleway proxy runs [CrowdSec](https://www.crowdsec.net/) for multi-layer security. Configuration is managed via Terraform (`infra/modules/scaleway-proxy/`).

### Layers

- **Traefik bouncer plugin** (`crowdsec-bouncer-traefik-plugin v1.4.4`) — WAF + AppSec on all HTTPS traffic
- **Syslog monitoring** — Detects SSH brute-force via `/var/log/auth.log` and `/var/log/syslog`
- **Host firewall bouncer** (`crowdsec-firewall-bouncer-iptables`) — Drops banned IPs at the iptables level

### Key Details

- Bouncer API keys are pre-registered via `BOUNCER_KEY_*` env vars in the CrowdSec container (Terraform variables: `crowdsec_bouncer_key`, `crowdsec_firewall_bouncer_key`)
- CrowdSec port 8080 is exposed only on localhost (`127.0.0.1:8080`) for the host firewall bouncer
- Collections: `crowdsecurity/traefik`, `crowdsecurity/appsec-virtual-patching`, `crowdsecurity/appsec-generic-rules`, `crowdsecurity/linux`
- Acquis configs: `config/crowdsec/acquis.d/{traefik,syslog,appsec}.yaml`
- Ban page: `config/traefik/ban.html` (default from crowdsec-bouncer-traefik-plugin)

## Utility Scripts (`scripts/`)

Python utility scripts managed with **uv** (Python 3.12+). All packages live under `scripts/` with a shared `pyproject.toml`.

### Packages

- `warden/` — Kubernetes-to-Warden monitoring integration (discover, seed, compare, delete monitors)
- `passbolt/` — Passbolt secret management (add custom fields to new or existing secrets via GPG-authenticated API)

### Script Conventions

New scripts **must** follow the established patterns:

| Concern | Convention |
|---------|-----------|
| CLI | Typer (`typer.Typer()` + `@app.command()`) |
| Models | Pydantic v2 (`BaseModel`, `Field`, frozen config) |
| HTTP | httpx (sync `Client` or async `AsyncClient`) |
| Logging | structlog (same `configure()` block as `warden/helper.py`) |
| Testing | pytest + `unittest.mock` (MagicMock, patch) |
| Config | Environment variables via `os.environ`, loaded in a `load_config_from_env()` function |

### Package Structure

```
scripts/<package-name>/
├── __init__.py          # Package metadata (__version__)
├── helper.py            # Shared models, API clients, logging setup
├── <command>.py          # CLI entry point (Typer app)
└── tests/
    ├── __init__.py
    └── test_<module>.py
```

### Adding a New Script Package

1. Create the package directory under `scripts/`
2. Add CLI entry point to `pyproject.toml` under `[project.scripts]`
3. Add the package to `[tool.hatch.build.targets.wheel].packages`
4. Add test path to `[tool.pytest.ini_options].testpaths`
5. Add to `[tool.coverage.run]` source and omit lists
6. Add any new dependencies to `[project].dependencies`
7. Run `uv sync` to install
