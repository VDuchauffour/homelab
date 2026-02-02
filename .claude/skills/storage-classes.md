# Storage Configuration

Configure persistent storage for applications.

## Usage

```
/storage-classes
```

## Available Storage Classes

| StorageClass | Backend | Access Mode | Use Case |
|--------------|---------|-------------|----------|
| `zfs-vm-pool-dynamic` | OpenEBS ZFS-LocalPV | RWO | App configs, databases |
| `nfs-tank-media` | NFS CSI | RWX | Shared media (dynamic) |
| `nfs-media-library` | NFS CSI | RWX | Shared media (static) |

All storage uses **Retain** reclaim policy.

## ZFS-LocalPV (Default for Apps)

High-performance local storage backed by ZFS. Use for app configs, databases, and any RWO workload.

```yaml
persistence:
  enabled: true
  storageClass: zfs-vm-pool-dynamic
  size: 1Gi
```

Features:

- Compression (lz4)
- Snapshots support
- Dynamic provisioning
- Data stored at `/vm-pool/<pvc-uuid>`

## NFS Storage (Shared Media)

ReadWriteMany (RWX) volumes for media shared across pods.

### Dynamic NFS PVC

Creates subdirectory per PVC under NFS share:

```yaml
persistence:
  media:
    enabled: true
    storageClass: nfs-tank-media
    accessMode: ReadWriteMany
    size: 100Gi
```

### Static NFS PVC (Existing Data)

For apps that need the root of `/mnt/tank/media` (arr suite, Jellyfin):

```yaml
persistence:
  media:
    enabled: true
    existingClaim: media-library
```

Static PVs are defined in `kubernetes/cluster/persistent-volumes/media.yaml`.

## Common Patterns

### Media Applications (Jellyfin, Sonarr, etc.)

Separate config (ZFS) and media (NFS) storage:

```yaml
persistence:
  config:
    enabled: true
    storageClass: zfs-vm-pool-dynamic
  media:
    enabled: true
    existingClaim: media-library
    mountPath: /media
```

### Database Applications

Use ZFS for performance:

```yaml
persistence:
  enabled: true
  storageClass: zfs-vm-pool-dynamic
  size: 10Gi
```

### CloudNativePG

```yaml
storage:
  size: 10Gi
  storageClass: zfs-vm-pool-dynamic
```

## Check Storage

```shell
# List storage classes
kubectl get storageclass

# List PVs with reclaim policy
kubectl get pv -o custom-columns='NAME:.metadata.name,RECLAIM:.spec.persistentVolumeReclaimPolicy,SC:.spec.storageClassName'

# List PVCs in namespace
kubectl get pvc -n <namespace>

# Fix reclaim policy if needed
kubectl patch pv <pv-name> -p '{"spec":{"persistentVolumeReclaimPolicy":"Retain"}}'
```

## Reference

- ZFS-LocalPV: `kubernetes/infra/openebs/`
- NFS Server: `kubernetes/infra/nfs-server/`
- NFS CSI Driver: `kubernetes/infra/nfs-csi-driver/`
- Static Media PVs: `kubernetes/cluster/persistent-volumes/media.yaml`
