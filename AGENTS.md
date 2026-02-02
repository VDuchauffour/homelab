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
| Storage | OpenEBS (ZFS-LocalPV), NFS (dynamic provisioner) |
| Database | CloudNativePG (PostgreSQL) |
| Ingress | Traefik |
| TLS | cert-manager (mkcert CA for local, Let's Encrypt for public) |
| GPU | Intel Device Plugins (iGPU/QSV) |
| Monitoring | kube-prometheus-stack, Beszel |
| Auth | Authentik |
| Secrets | Infisical |
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

## NFS Storage (RWX Volumes)

The cluster provides ReadWriteMany (RWX) volumes via an in-cluster NFS server backed by hostPath, following the OpenEBS NFS provisioning pattern. This is used for media storage shared across multiple pods (e.g., the "arr" suite and Jellyfin).

### Architecture

```
Pod → NFS CSI Driver → NFS Server Pod → hostPath (/mnt/tank/media)
```

- **StorageClass**: `nfs-tank-media`
- **NFS Server**: `nfs-server.nfs-server.svc.cluster.local`
- **Backend**: hostPath to `/mnt/tank/media` on joi node
- **Reclaim Policy**: `Retain`

### Components

1. **NFS Server** (`kubernetes/infra/nfs-server/`)

   - Deployment + Service exposing `/mnt/tank/media` via NFS
   - Pinned to joi node via nodeSelector

2. **NFS CSI Driver** (`kubernetes/infra/nfs-csi-driver/`)

   - kubernetes-csi/csi-driver-nfs for dynamic PVC provisioning
   - Creates subdirectories per PVC under the NFS share

### Deployment

```shell
kubectl apply -k kubernetes/infra/nfs-server/manifests/
cd kubernetes/infra/nfs-csi-driver && helmfile apply
```

### Usage Example

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: media-library
spec:
  accessModes: [ReadWriteMany]
  storageClassName: nfs-tank-media
  resources:
    requests:
      storage: 100Gi
```

### Accessing Existing Data

Dynamic PVCs create subdirectories under the NFS share. To access existing data at `/mnt/tank/media` directly, use a static PV/PVC or configure apps with hostPath.
