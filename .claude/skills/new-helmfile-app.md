# Create New Helmfile Application

Scaffold a new application following the project's conventions.

## Usage

```
/new-helmfile-app <app-name> <namespace> <chart-repo-url> <chart-name> <chart-version>
```

## App Structure

```
kubernetes/apps/<app-name>/
├── helmfile.yaml       # Helmfile release definition
├── values.yaml         # Helm values override
└── manifests/          # Optional: app-specific K8s resources only
```

**Note:** Most apps don't need a `manifests/` folder. Use it only for app-specific resources that can't be configured via Helm values (e.g., extra Services, ConfigMaps).

## What Goes Where

| Resource Type | Location |
|---------------|----------|
| StorageClasses | `kubernetes/cluster/storageclasses/` |
| Shared PVs (media) | `kubernetes/cluster/persistent-volumes/` |
| CNPG Clusters | `kubernetes/cluster/cloudnative-pg/` |
| Certificates | `kubernetes/cluster/certificates/` |
| Namespaces | `kubernetes/cluster/namespaces/` |
| App Secrets | `kubernetes/apps/<app>/manifests/secret.yaml` |
| Infra Secrets | `kubernetes/infra/<component>/manifests/secret.yaml` |
| App-specific extras | `kubernetes/apps/<app>/manifests/` |

## Steps

1. Create the app directory:

   ```shell
   mkdir -p kubernetes/apps/<app-name>
   ```

2. Create `helmfile.yaml`:

   ```yaml
   ---
   repositories:
     - name: <repo-name>
       url: <chart-repo-url>

   releases:
     - name: <app-name>
       namespace: <namespace>
       createNamespace: true
       chart: <repo-name>/<chart-name>
       version: <chart-version>
       values:
         - values.yaml
   ```

3. Create `values.yaml` with common patterns:

   ```yaml
   ---
   persistence:
     enabled: true
     storageClass: zfs-vm-pool-dynamic

   ingress:
     enabled: true
     className: traefik
     annotations:
       kubernetes.io/ingress.class: traefik
       cert-manager.io/cluster-issuer: mkcert-ca
     hosts:
       - host: <app-name>.home.arpa
         paths:
           - path: /
             pathType: Prefix
     tls:
       - hosts:
           - <app-name>.home.arpa
         secretName: <app-name>-mkcert-tls
   ```

## Storage Patterns

### App Config (most apps)

Use dynamic provisioning - no manifests needed:

```yaml
persistence:
  enabled: true
  storageClass: zfs-vm-pool-dynamic
  size: 1Gi
```

### Shared Media (arr apps, Jellyfin)

Reference existing static PVC:

```yaml
persistence:
  media:
    enabled: true
    existingClaim: media-library
    mountPath: /media
```

### Database (CloudNativePG)

Add cluster to `kubernetes/cluster/cloudnative-pg/`:

```yaml
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: <app-name>-db
  namespace: cnpg-clusters
spec:
  instances: 1
  storage:
    size: 5Gi
    storageClass: zfs-vm-pool-dynamic
```

## Conventions

- Namespace: Use `<app-name>` or group namespaces like `arr`, `media-center`
- Domain: `<app-name>.home.arpa` for local access
- TLS: Use `mkcert-ca` cluster issuer
- Storage: Use `zfs-vm-pool-dynamic` for configs, `media-library` PVC for shared media
