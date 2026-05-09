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
│       ├── backups/             # Restic backup CronJobs (custom Helm chart)
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
│   └── jellyfin/                # Jellyfin media mover with metadata preservation
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
| Secret Management | Scaleway CLI (via vals `ref+scw://` provider) |
| Backup | Restic (app configs to RustFS) + Barman Cloud Plugin (PostgreSQL) + Pangolin DB (Scaleway S3) |
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
| `zfs-configs-clusters-k3s-dynamic` | OpenEBS ZFS-LocalPV | RWO | App configs, databases |
| `nfs-tank-media` | NFS CSI | RWX | Shared NFS storage (media, filebrowser) |

All storage uses **Retain** reclaim policy to prevent accidental data loss.

### ZFS-LocalPV (App Configs)

OpenEBS ZFS-LocalPV provides high-performance local storage backed by ZFS on the `configs-clusters-k3s` dataset.

- **StorageClass**: `zfs-configs-clusters-k3s-dynamic`
- **Features**: Compression (lz4), snapshots, dynamic provisioning
- **Location**: `/configs-clusters-k3s/<pvc-uuid>` on single node

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: app-config
spec:
  accessModes: [ReadWriteOnce]
  storageClassName: zfs-configs-clusters-k3s-dynamic
  resources:
    requests:
      storage: 1Gi
```

### NFS Storage (Shared Tank)

ReadWriteMany (RWX) volumes via an in-cluster NFS server, following the OpenEBS NFS provisioning pattern.

#### Architecture

```
Pod → NFS CSI Driver → NFS Server Pod → hostPath (/mnt/tank/media or /mnt/tank/share)
```

Two NFS server instances export different ZFS datasets:

- **Media NFS Server** (`nfs-server-media.nfs-server-media.svc.cluster.local`): Exports `/mnt/tank/media`

- **Share NFS Server** (`nfs-server-share.nfs-server-share.svc.cluster.local`): Exports `/mnt/tank/share`

- **StorageClass**: `nfs-tank-media` (dynamic), `nfs-media-library` (static media), `nfs-share-library` (static share)

Static PVs use `share` subpaths (e.g. `/`, `/photos/immich`) to scope access per app.

#### Components

1. **NFS Servers** (`kubernetes/infra/nfs-server/`)

   - Shared Helm chart with two Helmfile releases (nfs-server-media, nfs-server-share)
   - Each pinned to single node via nodeSelector

2. **NFS CSI Driver** (`kubernetes/infra/nfs-csi-driver/`)

   - kubernetes-csi/csi-driver-nfs for dynamic PVC provisioning

#### Deployment

```shell
cd kubernetes/infra/nfs-server && helmfile apply
cd kubernetes/infra/nfs-csi-driver && helmfile apply
```

#### Static vs Dynamic NFS PVCs

- **Static PVs** (`kubernetes/cluster/persistent-volumes/media.yaml`): Used by arr suite, Jellyfin, qBittorrent, filebrowser, slskd, nextcloud, immich. Each PV specifies a `share` subpath (e.g. `/`, `/photos/immich`) to scope access. Filebrowser's share PV uses the share NFS server.
- **Dynamic PVCs** (`nfs-tank-media` StorageClass): Creates subdirectories per PVC under `/mnt/tank/media`, useful for isolated app data

**Important**: Any pod mounting an NFS media volume with `fsGroup` **must** set `fsGroupChangePolicy: OnRootMismatch` in `podSecurityContext`. Without it, Kubernetes performs a recursive ownership walk of the entire NFS share on every pod start, which fails on large media libraries. For pods where `fsGroup` differs from the NFS root owner (1000), use `supplementalGroups` instead of `fsGroup` (e.g. nextcloud uses `fsGroup: 33` → replaced with `supplementalGroups: [33, 1000]`).

## Database (CloudNativePG)

The cluster runs a single CloudNativePG instance (`cnpg-cluster0`) in namespace `cnpg-clusters` with dynamically provisioned ZFS storage (`zfs-configs-clusters-k3s-dynamic`, 10Gi).

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

## Backups (Restic)

All app config PVCs are backed up to RustFS using [Restic](https://restic.net/). Backups are managed by a single custom Helm chart (`kubernetes/cluster/backups/charts/restic-backups/`) deployed via Helmfile.

### Architecture

```
CronJob (orchestrator) → scales down app → creates inner Job (restic container with PVC mounts) → restic backup to RustFS → scales app back up
```

Two backup modes:

- **Orchestrated** (default): Scales down the app, runs backup in an inner Job, scales back up via EXIT trap
- **Direct**: Simple CronJob with restic container directly mounting volumes (used for nfs-share)

### Configuration

- **Chart**: `kubernetes/cluster/backups/charts/restic-backups/`
- **Helmfile**: `kubernetes/cluster/backups/helmfile.yaml`
- **App values**: `kubernetes/cluster/backups/values.yaml` — all 21 apps defined here
- **Destination**: RustFS bucket `restic-backups` at `http://rustfs-svc.rustfs.svc.cluster.local:9000`
- **Schedule**: Weekly on Sundays, staggered 5-minute intervals starting at 3:00 AM
- **Retention**: 2 weekly snapshots

### Environment Variables

- `RUSTFS_ROOT_USER` — RustFS access key (from Scaleway CLI: `scw secret get name=rustfs --field user`)
- `RUSTFS_ROOT_PASSWORD` — RustFS secret key (from Scaleway CLI: `scw secret get name=rustfs --field password`)
- `RESTIC_PASSWORD` — Restic repository encryption password (from Scaleway CLI: `scw secret get name=restic --field password`)
- `SINGLE_NODE_NAME` — Node name for nodeSelector
- `SCW_ACCESS_KEY` — Scaleway API access key for vals `ref+scw://` provider
- `SCW_SECRET_KEY` — Scaleway API secret key for vals `ref+scw://` provider
- `SCW_PROJECT_ID` — Scaleway project ID for vals `ref+scw://` provider
- `SCW_REGION` — Scaleway region for vals `ref+scw://` provider

### Backed-Up Apps

| App | Namespace | Schedule | Mode | Notes |
|-----|-----------|----------|------|-------|
| arr (6 apps) | arr | Sun 3:00 | orchestrated | bazarr, lidarr, prowlarr, radarr, sonarr, tdarr |
| jellyfin | media-center | Sun 3:00 | orchestrated | excludes transcodes |
| nfs-share | nfs-server-share | Sun 4:00 | direct | hostPath /mnt/tank/share |
| filebrowser | filebrowser | Sun 3:05 | orchestrated | |
| linkding | linkding | Sun 3:10 | orchestrated | |
| linkwarden | linkwarden | Sun 3:15 | orchestrated | |
| memos | memos | Sun 3:20 | orchestrated | |
| n8n | n8n | Sun 3:25 | orchestrated | |
| pgadmin | pgadmin | Sun 3:30 | orchestrated | |
| pihole | pihole | Sun 3:35 | orchestrated | |
| protonmail-bridge | protonmail-bridge | Sun 3:40 | orchestrated | |
| slskd | slskd | Sun 3:45 | orchestrated | |
| wakapi | wakapi | Sun 3:50 | orchestrated | |
| helm-dashboard | kube-system | Sun 3:55 | orchestrated | shared ns, unique names |
| jellyseerr | media-center | Sun 4:00 | orchestrated | shared ns, unique names |
| nextcloud | nextcloud | Sun 4:10 | orchestrated | excludes updater- \*/ |
| privatebin | privatebin | Sun 4:20 | orchestrated | StatefulSet |
| qbittorrent-vpn | qbittorrent-vpn | Sun 4:25 | orchestrated | 2 PVCs |
| scrutiny | scrutiny | Sun 4:30 | orchestrated | 2 PVCs |
| seafile | seafile | Sun 4:35 | orchestrated | deploy + StatefulSet, 3 PVCs |
| zfdash | zfdash | Sun 4:45 | orchestrated | 2 PVCs |

### Deployment

```shell
cd kubernetes/cluster/backups
helmfile apply
```

### Adding a New App Backup

1. Add an entry to `kubernetes/cluster/backups/values.yaml` under `apps:`
2. Specify: `namespace`, `schedule`, `targets` (deployments/statefulsets to scale), `pvcs` (name + mountPath), and optional `excludes`
3. If the app shares a namespace with another backed-up app, set `uniqueNames: true`
4. Deploy: `cd kubernetes/cluster/backups && helmfile apply`

### Manual Trigger

```shell
kubectl create job --from=cronjob/restic-backup-<app> manual-backup-<app> -n <namespace>
```

### Check Backup Status

```shell
kubectl get cronjobs -A | grep restic
kubectl get jobs -A | grep restic
```

## Dashboard (Glance)

The homelab uses [Glance](https://github.com/dynacatapp/dynacat) as a personal dashboard. It runs as **two instances** (public + local) from a single helmfile in `kubernetes/apps/dynacat/`.

### Architecture

- **dynacat-public**: Exposed via Pangolin (public domain), no local ingress
- **dynacat-local**: Local network only, ingress with mkcert TLS on `dashboard.<local-domain>`
- Both share `values-common.yaml` for bookmark groups, widgets, and API integrations

### Configuration Files

| File | Purpose |
|------|---------|
| `helmfile.yaml` | Two releases (dynacat-public, dynacat-local) with vals secrets |
| `values-common.yaml` | Shared bookmarks, widgets (weather, calendar, qBittorrent, Warden) |
| `values-local.yaml` | Local ingress config (mkcert TLS) |
| `values-public.yaml` | Public instance config (ingress disabled — exposed via Pangolin) |
| `charts/dynacat/` | Custom Helm chart (configmap template generates `dynacat.yml`) |

### Bookmark Structure

Bookmarks in `values-common.yaml` are organized into groups:

- **`instanceBookmarkGroups`**: Instance-specific links (Proxy, Cluster, Monitoring) — shown in the left sidebar
- **`commonBookmarkGroups`**: Shared app links (Productivity, Tools, Sharing, Media, Arr, AI) — shown in the main area

Each link uses either `url` (full URL) or `subdomain` (auto-expanded to `https://<subdomain>.<domainName>`).

### Adding a New App to the Dashboard

1. Add a bookmark entry to the appropriate group in `kubernetes/apps/dynacat/values-common.yaml`:

   ```yaml
   - title: MyApp
     subdomain: myapp
     icon: di:myapp  # or sh:myapp, or a raw URL
   ```

2. Redeploy: `make dynacat-update`

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
- Resource blocks must be ordered **alphabetically** by key name
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

1. Add a new resource block to `kubernetes/infra/pangolin-newt/manifests/blueprint.yaml` (maintain alphabetical order by resource key)
2. Set `full-domain`, target `hostname`/`port`, auth settings, and healthcheck
3. Apply with `vals eval -f manifests/blueprint.yaml | kubectl apply -f -`
4. Restart Newt: `kubectl rollout restart deployment/fossorial-newt-main-tunnel -n fossorial`
5. Add a bookmark to the Glance dashboard (see [Adding a New App to the Dashboard](#adding-a-new-app-to-the-dashboard))

## Post-Deployment Checklist (New App or Infra Tool)

After deploying a new app or infra tool, complete these additional steps:

1. **Glance dashboard**: Add a bookmark entry to `kubernetes/apps/dynacat/values-common.yaml` in the appropriate group, then redeploy Glance (`make dynacat-update`)
2. **Pangolin blueprint** (if externally accessible): Add a resource block to `kubernetes/infra/pangolin-newt/manifests/blueprint.yaml`, then apply and restart Newt
3. **Warden monitoring**: Run `make warden-seed-cleanup` to discover the new app and sync monitors (adds new, removes stale)
4. **Restic backup** (if app has config PVCs): Add an entry to `kubernetes/cluster/backups/values.yaml`, then redeploy (`cd kubernetes/cluster/backups && helmfile apply`)
5. **README.md**: Add the app/tool to the appropriate table (Apps or Infrastructure Tools) in `README.md` — run `make check-readme` to verify

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

## Pangolin DB Backup

Pangolin's PostgreSQL database is backed up weekly to a Scaleway Object Storage bucket, managed via Terraform.

- **Bucket**: `<instance_name>-pangolin-backups` in `fr-par` (Terraform resource: `scaleway_object_bucket.pangolin_backups`)
- **Script**: `backup-db.sh.tftpl` → rendered to `/home/<username>/pangolin/backup-db.sh` on the instance
- **Schedule**: Weekly on Sunday at 3:00 AM via `/etc/cron.d/pangolin-db-backup`
- **Retention**: 30 days (S3 lifecycle rule, configurable via `pangolin_backup_retention_days`)
- **Logs**: `/var/log/pangolin-backup.log`

### How It Works

```
Cron (Sunday 3am) → backup-db.sh → docker exec postgres pg_dump → gzip → aws s3 cp → Scaleway Object Storage
```

The script uses the same Scaleway API credentials as Traefik's DNS challenge (`scaleway_access_key`, `scaleway_secret_key`). The `awscli` package is installed via cloud-init.

### Manual Backup

```shell
ssh <username>@<instance-ip>
/home/<username>/pangolin/backup-db.sh
```

### Restore on New Instance

After `terraform apply` creates a fresh instance and `docker compose up -d` starts the stack:

```shell
# List available backups
export AWS_ACCESS_KEY_ID="<scaleway_access_key>"
export AWS_SECRET_ACCESS_KEY="<scaleway_secret_key>"
aws s3 ls s3://<instance_name>-pangolin-backups/pangolin/ --endpoint-url https://s3.fr-par.scw.cloud

# Download the latest dump
aws s3 cp s3://<instance_name>-pangolin-backups/pangolin/pangolin-db-<timestamp>.sql.gz /tmp/ --endpoint-url https://s3.fr-par.scw.cloud

# Stop Pangolin (keep Postgres running)
docker stop pangolin gerbil traefik crowdsec

# Drop and recreate the database (required — restoring into an existing DB causes FK/PK conflicts)
docker exec postgres psql -U <pangolin_pg_user> -d postgres -c "DROP DATABASE pangolin;"
docker exec postgres psql -U <pangolin_pg_user> -d postgres -c "CREATE DATABASE pangolin OWNER <pangolin_pg_user>;"

# Restore
gunzip -c /tmp/pangolin-db-<timestamp>.sql.gz | docker exec -i postgres psql -U <pangolin_pg_user> -d pangolin

# Fix Gerbil public key — the new instance generates a fresh WireGuard keypair,
# but the restored DB still has the old exit node's public key.
# Derive the current public key from gerbil's private key and update the DB:
NEW_PUBKEY=$(cat ~/pangolin/config/key | wg pubkey)
docker exec postgres psql -U <pangolin_pg_user> -d pangolin \
  -c "UPDATE \"exitNodes\" SET \"publicKey\" = '$NEW_PUBKEY' WHERE \"exitNodeId\" = 1;"

# Restart all services
docker compose -f ~/pangolin/compose.yaml down && docker compose -f ~/pangolin/compose.yaml up -d
```

**Why the Gerbil key fix is needed:** Gerbil generates and saves its WireGuard private key at `~/pangolin/config/key` on first start (`--generateAndSaveKeyTo`). On a new instance, this key is different from the one stored in the backup. Gerbil sends its public key to Pangolin's config API, but Pangolin matches exit nodes by public key — if it doesn't match, Gerbil receives an empty config with no CIDR address, causing a crash loop. Traefik also fails because it shares Gerbil's network namespace (`network_mode: service:gerbil`).

### Configuration

- **Terraform files**: `infra/modules/scaleway-proxy/` — `main.tf` (bucket resource), `backup-db.sh.tftpl` (script template), `cloud-init.yaml.tftpl` (cron + script delivery)
- **Variable**: `pangolin_backup_retention_days` (default: 30) in `variables.tf`

## CrowdSec DB Backup

CrowdSec's SQLite database and Web UI data are backed up weekly to the same Scaleway Object Storage bucket as Pangolin, under a `crowdsec/` prefix.

- **Bucket**: `<instance_name>-pangolin-backups` (shared with Pangolin backups)
- **Script**: `backup-crowdsec.sh.tftpl` → rendered to `/home/<username>/pangolin/backup-crowdsec.sh` on the instance
- **Schedule**: Weekly on Sunday at 3:00 AM via `/etc/cron.d/crowdsec-backup`
- **Retention**: 30 days (same S3 lifecycle rule as Pangolin backups)
- **Logs**: `/var/log/crowdsec-backup.log`

### What Gets Backed Up

| Archive | Source Path | Contents |
|---------|-------------|----------|
| `crowdsec-db-<timestamp>.tar.gz` | `~/pangolin/config/crowdsec/db/` | SQLite DB (decisions, alerts, CAPI state, metrics, machine accounts) |
| `crowdsec-webui-<timestamp>.tar.gz` | `~/pangolin/config/crowdsec-web-ui/` | Web UI session data and state |

### How It Works

```
Cron (Sunday 3am) → backup-crowdsec.sh → docker stop → tar + gzip → aws s3 cp → docker start → Scaleway Object Storage
```

The script stops CrowdSec and Web UI containers briefly (a few seconds) for a consistent SQLite snapshot, creates compressed archives, uploads them to S3, then restarts the containers via an EXIT trap (ensuring restart even on failure). Existing iptables rules from the host firewall bouncer remain active during the brief downtime.

### Manual Backup

```shell
ssh <username>@<instance-ip>
/home/<username>/pangolin/backup-crowdsec.sh
```

### Restore on New Instance

After `terraform apply` creates a fresh instance and `docker compose up -d` starts the stack:

```shell
# List available CrowdSec backups
export AWS_ACCESS_KEY_ID="<scaleway_access_key>"
export AWS_SECRET_ACCESS_KEY="<scaleway_secret_key>"
aws s3 ls s3://<instance_name>-pangolin-backups/crowdsec/ --endpoint-url https://s3.fr-par.scw.cloud

# Download the latest archives
aws s3 cp s3://<instance_name>-pangolin-backups/crowdsec/crowdsec-db-<timestamp>.tar.gz /tmp/ --endpoint-url https://s3.fr-par.scw.cloud
aws s3 cp s3://<instance_name>-pangolin-backups/crowdsec/crowdsec-webui-<timestamp>.tar.gz /tmp/ --endpoint-url https://s3.fr-par.scw.cloud

# Stop CrowdSec containers
docker stop crowdsec_web_ui crowdsec

# Restore CrowdSec DB (overwrites the fresh empty DB)
tar -xzf /tmp/crowdsec-db-<timestamp>.tar.gz -C ~/pangolin/config/crowdsec/

# Restore Web UI data
tar -xzf /tmp/crowdsec-webui-<timestamp>.tar.gz -C ~/pangolin/config/

# Restart CrowdSec and wait for LAPI health
docker start crowdsec
for i in $(seq 1 30); do docker exec crowdsec cscli lapi status >/dev/null 2>&1 && break || sleep 5; done

# Re-register the web UI machine account (the restored DB may have a stale registration)
docker exec crowdsec cscli machines add crowdsec-web-ui --password "<crowdsec_webui_machine_password>" --force -f /dev/null

# Restart Web UI
docker start crowdsec_web_ui

# Cleanup
rm -f /tmp/crowdsec-db-<timestamp>.tar.gz /tmp/crowdsec-webui-<timestamp>.tar.gz
```

**Note:** Community blocklists sync automatically via CAPI on CrowdSec startup regardless of restore. The main value of restoring the DB is preserving **local decisions** (manual bans), alert history, and metrics. If you don't need those, CrowdSec will rebuild its state from scratch.

### Configuration

- **Terraform files**: `infra/modules/scaleway-proxy/` — `main.tf` (script template), `backup-crowdsec.sh.tftpl` (script template), `cloud-init.yaml.tftpl` (cron + script delivery)
- **Shared bucket**: Uses the same `scaleway_object_bucket.pangolin_backups` resource with `crowdsec/` key prefix

## Secret Management (Scaleway CLI + vals)

The homelab uses [Scaleway Secret Manager](https://www.scaleway.com/en/docs/identity-and-access-management/api-access-and-secret-manager/) via the `vals` tool's `ref+scw://` provider. This eliminates hardcoded secrets in Helm charts and provides a centralized, auditable secret store.

### Architecture

```
Helmfile with vals → ref+scw:// → Scaleway Secret Manager API → secret value
```

### Secret Reference Pattern

```yaml
# Simple field lookup
password: ref+scw:///homelab/rustfs#/password

# Multiple fields from same secret
username: ref+scw:///homelab/cnpg#/user
password: ref+scw:///homelab/cnpg#/password

# Nested path
apiKey: ref+scw:///homelab/wakatime#/api-key
```

### Environment Variables

Required in `.envrc` for vals to authenticate with Scaleway:

```bash
export SCW_ACCESS_KEY="<your-access-key>"
export SCW_SECRET_KEY="<your-secret-key>"
export SCW_PROJECT_ID="<project-id>"
export SCW_REGION="fr-par"
```

### Adding a New Secret

Use the Scaleway CLI to create a new secret:

```bash
# Install Scaleway CLI (if not already installed)
scw secret create name=homelab
# Add fields
scw secret add name=homelab --field name=rustfs --field value=admin
scw secret add name=homelab --field name=rustfs --field password=s3cret
```

### Managing Secrets

```bash
# List all secrets
scw secret list

# Get specific secret details
scw secret get name=homelab

# List secret versions/revisions
scw secret list name=homelab
```

### Using Secrets in Helm

After secrets are stored in Scaleway, reference them in Helm values using the `ref+scw://` provider. Vals automatically resolves these at deploy time:

```bash
# Vals resolves ref+scw:// at deploy time
cd kubernetes/apps/myapp
helmfile apply
```

**Key Benefits:**

- Secrets never committed to Git
- Single source of truth for all homelab secrets
- Auditable access logs in Scaleway console
- Track secret history and revisions
- Dynamic resolution at deploy time

For detailed usage, see the `scaleway-secrets` skill: `skill scaleway-secrets`

## Utility Scripts (`scripts/`)

Python utility scripts managed with **uv** (Python 3.12+). All packages live under `scripts/` with a shared `pyproject.toml`.

### Packages

- `warden/` — Kubernetes-to-Warden monitoring integration (discover, seed, compare, delete monitors)
- `jellyfin/` — Jellyfin media mover with metadata preservation (move downloads to library, preserve ProviderIds, delete old entries)

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
