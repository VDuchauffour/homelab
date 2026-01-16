# Storage Configuration

Configure persistent storage for applications.

## Usage

```
/storage-classes
```

## Available Storage Classes

### OpenEBS (Dynamic Provisioning)

```yaml
persistence:
  storageClass: openebs-hostpath
```

- Default dynamic provisioner
- Suitable for most applications
- Data stored on node's filesystem

### ZFS Storage Classes

Custom storage classes for ZFS pools:

```yaml
# Example from jellyfin
persistence:
  config:
    storageClass: zfs-vm-pool-jellyfin-config
  media:
    storageClass: zfs-tank-jellyfin
```

## Create PersistentVolume (Static)

For pre-existing storage or specific paths:

```yaml
apiVersion: v1
kind: PersistentVolume
metadata:
  name: pv-<app-name>
spec:
  capacity:
    storage: 10Gi
  accessModes:
    - ReadWriteOnce
  persistentVolumeReclaimPolicy: Retain
  storageClassName: <storage-class>
  hostPath:
    path: /path/to/data
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: pvc-<app-name>
  namespace: <namespace>
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: <storage-class>
  resources:
    requests:
      storage: 10Gi
  volumeName: pv-<app-name>
```

## Common Patterns

### Media Applications (Jellyfin, Sonarr, etc.)

Separate config and media storage:

```yaml
persistence:
  config:
    enabled: true
    storageClass: openebs-hostpath
  media:
    enabled: true
    storageClass: zfs-tank-media
    existingClaim: pvc-media-shared
```

### Database Applications

Use reliable storage:

```yaml
persistence:
  enabled: true
  storageClass: openebs-hostpath
  size: 10Gi
```

## Check Storage

```shell
# List storage classes
kubectl get storageclass

# List PVs
kubectl get pv

# List PVCs in namespace
kubectl get pvc -n <namespace>

# Describe PVC
kubectl describe pvc -n <namespace> <pvc-name>
```

## Reference Apps

- `kubernetes/apps/jellyfin/` - Multiple PVs for config/media/cache
- `kubernetes/apps/sonarr/` - Static PV with hostPath
- `kubernetes/infra/cloudnative-pg/` - Database storage
