# Homelab Documentation

A Kubernetes-based homelab with cloud infrastructure for secure external access.

## Architecture Overview

```
Internet → Scaleway Proxy (Caddy + CrowdSec + FRP) → Homelab K8s Cluster
```

- **External Access**: Scaleway-hosted reverse proxy with FRP tunneling
- **Internal**: Kubernetes cluster with Traefik ingress and cert-manager

## Project Structure

```
homelab/
├── kubernetes/
│   ├── apps/                    # User applications
│   ├── infra/                   # Infrastructure services
│   └── cluster/                 # Cluster-wide definitions
│
├── infra/
│   └── modules/
│       └── scaleway-proxy/      # Terraform for reverse proxy (Caddy, FRP, CrowdSec)
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
| Storage | OpenEBS ZFS-LocalPV (configs), NFS CSI (shared media) |
| Database | CloudNativePG (PostgreSQL) |
| Ingress | Traefik |
| TLS | cert-manager (mkcert CA for local, Let's Encrypt for public) |
| GPU | Intel Device Plugins (iGPU/QSV) |
| Monitoring | kube-prometheus-stack, Beszel |
| Auth | TinyAuth |
| External Proxy | Caddy + FRP + CrowdSec (Scaleway) |
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
- **Public access**: Let's Encrypt via Caddy (on Scaleway proxy)

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

The cluster uses two storage backends optimized for different use cases:

| StorageClass | Backend | Access Mode | Use Case |
|--------------|---------|-------------|----------|
| `zfs-vm-pool-dynamic` | OpenEBS ZFS-LocalPV | RWO | App configs, databases |
| `nfs-tank-media` | NFS CSI | RWX | Shared media (arr suite, Jellyfin) |

All storage uses **Retain** reclaim policy to prevent accidental data loss.

### ZFS-LocalPV (App Configs)

OpenEBS ZFS-LocalPV provides high-performance local storage backed by ZFS on the `vm-pool` dataset.

- **StorageClass**: `zfs-vm-pool-dynamic`
- **Features**: Compression (lz4), snapshots, dynamic provisioning
- **Location**: `/vm-pool/<pvc-uuid>` on joi node

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
- **Backend**: hostPath to `/mnt/tank/media` on joi node

#### Components

1. **NFS Server** (`kubernetes/infra/nfs-server/`)

   - Deployment + Service exposing `/mnt/tank/media` via NFS
   - Pinned to joi node via nodeSelector

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
