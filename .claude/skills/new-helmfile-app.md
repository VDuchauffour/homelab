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
└── manifests/          # Optional: PVs, secrets, etc.
    ├── pv.yaml
    └── secret.yaml
```

## Steps

1. Create the app directory structure:

   ```shell
   mkdir -p kubernetes/apps/<app-name>/manifests
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
   service:
     type: ClusterIP
     port: 8080

   persistence:
     enabled: true
     storageClass: openebs-hostpath

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

4. If using external storage, create `manifests/pv.yaml`:

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
   ```

## Conventions

- Namespace: Use `<app-name>` or group namespaces like `media-center`
- Domain: `<app-name>.home.arpa` for local access
- TLS: Use `mkcert-ca` cluster issuer for local TLS
- Storage: Prefer `openebs-hostpath` or ZFS storage classes
