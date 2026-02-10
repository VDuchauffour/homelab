# An opinionated Kubernetes-based homelab

This repository contains all the declarations necessary for the operation of my homelab. It uses Kubernetes as applications orchestrator.

## Key Technologies

| Component | Technology |
|-----------|------------|
| Container Orchestration | Kubernetes |
| Package Management | Helmfile + Helm |
| Storage | OpenEBS ZFS-LocalPV (configs), NFS CSI (shared media) |
| Database | CloudNativePG (PostgreSQL) + Barman Cloud Plugin (backups to MinIO) |
| Ingress | Traefik |
| TLS | cert-manager (mkcert CA for local, Let's Encrypt for public) |
| GPU | Intel Device Plugins (iGPU/QSV) |
| Monitoring | kube-prometheus-stack |
| Auth | TinyAuth |
| External Proxy | Caddy + FRP + CrowdSec (Scaleway) |
| IaC | Terraform |

## Kubernetes

The entire homelab is managed with Kubernetes. Here's the structure of the folder:

```shell
kubernetes
├── apps      # user-facing application workloads
├── cluster   # cluster-level configuration and shared resources
└── infra     # cluster-wide infrastructure services
```

### Deployed components

<details>
<summary>Apps</summary>

| | App | Description |
|:--:|-----|-------------|
| <img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/bazarr.png" width="24"> | bazarr | Subtitle management for media |
| <img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/dozzle.png" width="24"> | dozzle | Real-time log viewer for containers |
| <img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/glance.png" width="24"> | glance | Personal dashboard |
| <img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/headlamp.png" width="24"> | headlamp | Kubernetes web UI |
| <img src="https://raw.githubusercontent.com/komodorio/helm-dashboard/refs/heads/main/images/logo.png" width="24"> | helm-dashboard | Helm charts management UI |
| <img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/jellyfin.png" width="24"> | jellyfin | Media server with live TV |
| <img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/jellyseerr.png" width="24"> | jellyseerr | Media request management |
| <img src="https://raw.githubusercontent.com/kanbn/kan/refs/heads/main/apps/web/public/favicon.ico" width="24"> | kan | Kanban board |
| <img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/lidarr.png" width="24"> | lidarr | Music collection manager |
| <img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/linkding.png" width="24"> | linkding | Minimal bookmark manager |
| <img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/linkwarden.png" width="24"> | linkwarden | Collaborative bookmark manager |
| <img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/n8n.png" width="24"> | n8n | Workflow automation platform |
| <img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/pgadmin.png" width="24"> | pgadmin | PostgreSQL management UI |
| <img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/prowlarr.png" width="24"> | prowlarr | Indexer manager for arr suite |
| <img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/qbittorrent.png" width="24"> | qbittorrent-vpn | BitTorrent client with VPN |
| <img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/radarr.png" width="24"> | radarr | Movie collection manager |
| <img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/sonarr.png" width="24"> | sonarr | TV show collection manager |
| <img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/scrutiny.png" width="24"> | scrutiny | Hard drive S.M.A.R.T health monitoring |
| <img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/stirling-pdf.png" width="24"> | stirling-pdf | PDF manipulation toolkit |
| <img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/tdarr.png" width="24"> | tdarr | Media transcoding optimizer |
| <img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/uptime-kuma.png" width="24"> | uptime-kuma | Uptime monitoring dashboard |
| <img src="https://raw.githubusercontent.com/ad4mts/zfdash/refs/heads/main/src/data/icons/zfs-gui.png" width="24"> | zfdash | ZFS monitoring dashboard |
| <img src="./kubernetes/apps/glance/assets/favicons/vibe-kanban.png" width="24"> | vibe-kanban | Kanban project management for vibe coding |

</details>

<details>
<summary>Infrastructure Tools</summary>

| | Tool | Description |
|:--:|------|-------------|
| <img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/cert-manager.png" width="24"> | cert-manager | TLS certificate automation |
| <img src="https://raw.githubusercontent.com/cloudnative-pg/cloudnative-pg.github.io/refs/heads/main/assets/images/hero_image.png" width="24"> | cloudnative-pg | PostgreSQL operator for K8s |
| <img src="https://upload.wikimedia.org/wikipedia/commons/thumb/8/85/Intel_logo_2023.svg/1280px-Intel_logo_2023.svg.png" width="24"> | intel-device-plugins | GPU and device plugin for Intel hardware |
| <img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/prometheus.png" width="24"> | kube-prometheus-stack | Monitoring and alerting stack |
| <img src="https://raw.githubusercontent.com/minio/minio/master/.github/logo.svg?sanitize=true" width="24"> | minio | High-performance blob storage |
| <img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/kubernetes.png" width="24"> | nfs-csi-driver | NFS CSI driver for RWX volumes |
| <img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/kubernetes.png" width="24"> | nfs-server | In-cluster NFS server for shared media |
| <img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/kubernetes.png" width="24"> | node-feature-discovery | Hardware feature discovery |
| <img src="https://raw.githubusercontent.com/cncf/artwork/master/projects/openebs/stacked/color/openebs-stacked-color.png" width="24"> | openebs | Container-native storage solution |
| <img src="https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/passbolt.png" width="24"> | passbolt | Team password manager |
| <img src="https://raw.githubusercontent.com/cloudnative-pg/cloudnative-pg.github.io/refs/heads/main/assets/images/hero_image.png" width="24"> | plugin-barman-cloud | Backup plugin for CloudNativePG (WAL archiving + base backups to MinIO) |

</details>

### Postgres

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

### Storage

The cluster uses two storage backends optimized for different use cases:

| StorageClass | Backend | Access Mode | Use Case |
|--------------|---------|-------------|----------|
| `zfs-vm-pool-dynamic` | OpenEBS ZFS-LocalPV | RWO | App configs, databases |
| `nfs-tank-media` | NFS CSI | RWX | Shared media (arr suite, Jellyfin) |

All storage uses **Retain** reclaim policy to prevent accidental data loss. You can see the [kubectl plugin for openebs](https://openebs.io/docs/user-guides/kubectl-openebs#install-kubectl-plugin) to help you to manage the storage volumes.

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

### GPUs management

To watch the usage of iGPU (through Intel QSV or VAAPI) use the command `intel_gpu_top` from the package `intel-gpu-tools`.

You can also check supported VAAPI profiles with `vainfo` from the package `libva-utils`.

You can verify OpenCL availability with `clinfo` from the package `clinfo`.

With the Intel GPU devices and operator, you can info the GPU status with the command:

```shell
kubectl get gpudeviceplugins
```

You can get more info about that [here](https://intel.github.io/intel-device-plugins-for-kubernetes/cmd/gpu_plugin/README.html).

### Headlamp

Generate an admin token to log in:

```shell
kubectl create token headlamp-admin -n kube-system
```

### Passbolt

Once the chart is apply, run the following command to set up an admin user:

```shell
kubectl exec -it -n passbolt <passbolt-pod-name> -- su -c "bin/cake passbolt register_user -u <email> -f <firstname> -l <lastname> -r admin" -s /bin/bash www-data
```

### Recreate CA for local network

```shell
CERT_DIR=$(mkcert -CAROOT)
kubectl create secret tls mkcert-ca-key-pair -n cert-manager --cert=$CERT_DIR/rootCA.pem --key=$CERT_DIR/rootCA-key.pem
kubectl apply -f cluster/cert-manager/manifests/mkcert-ca-issuer.yaml
```

In the ingress, adding the following annotation with cert-manager will:

- Create a Certificate resource
- Issue a leaf cert signed by your mkcert CA
- Manage renewals automatically
- Maintain the qbittorrent-mkcert-tls Secret

```yaml
ingress:
  enabled: true
  className: traefik
  annotations:
    kubernetes.io/ingress.class: traefik
    cert-manager.io/cluster-issuer: mkcert-ca
```

## Infrastructure

### Reverse proxy

The homelab is exposed to the Internet through a reverse proxy hosted on Scaleway. The stack runs entirely in Docker:

- **Caddy** handles TLS termination and reverse proxying (auto HTTPS via Let's Encrypt)
- **CrowdSec** provides collaborative security with IP reputation and behavior analysis
- **FRP server** (frps) receives tunneled connections from homelab services

Resources are provisioned using Terraform and are defined in `infra/`. You'll need a [Scaleway config file](https://cli.scaleway.com/config/).

#### Architecture

```
Internet → Caddy (80/443) → frps:8080 (services) or frps:7500 (dashboard)
                                 ↑
                            frps:7000 ← homelab frpc clients
```

The FRP dashboard is accessible at `https://frp.<domain>`.

Generate the password hash with:

```shell
docker run --rm caddy:2-alpine caddy hash-password --plaintext 'your-password'
```

Then set `basic_auth_user`, `basic_auth_hash`, `subdomains_with_basic_auth` and `subdomains_without_basic_auth` in your `terraform.tfvars`.

To use docker without `sudo` run login as user and run `newgrp docker`.

#### Deployment

```shell
cd ./infra/modules/scaleway-proxy

cp ./terraform.tfvars.example ./terraform.tfvars
# edit the file with the relevant values

terraform init
terraform plan
terraform apply
```

Once the instance is ready, run:

```shell
cd "$HOME_DIR/proxy"
docker compose up -d --build
```

#### Destroy

```shell
cd ./infra/modules/scaleway-proxy
terraform destroy
```

## Password generation recommandation

```shell
pwgen -scyn 32 1
or
openssl rand -base64 32
```

## Acknowledgments

- Some charts are inspired by [rtomik's helm-charts repository](https://github.com/rtomik/helm-charts)
- The FRP server setup is inspired by [jpfranca-br's repository](https://github.com/jpfranca-br/frps-setup)
