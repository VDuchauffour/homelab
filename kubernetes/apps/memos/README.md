# Memos

A lightweight, self-hosted memo hub for capturing and sharing ideas.

## Features

- 📝 Simple note-taking with Markdown support
- 🔒 Privacy-first and self-hosted
- 🚀 Fast and lightweight
- 📱 Mobile app available
- 🔗 RESTful API
- 🗃️ PostgreSQL backend

## Architecture

- **Helm Chart**: Local copy of [usememos/helm](https://github.com/usememos/helm) (v0.2.0) with PostgreSQL support
- **App Version**: Memos v0.25.2
- **Database**: PostgreSQL (CloudNativePG cluster)
- **Storage**: ZFS-backed persistent volume (5Gi)
- **Ingress**: Traefik with local mkcert TLS

## Prerequisites

1. **Database Setup**: Create the database and user credentials:

```shell
# Add to your .envrc file
export CLOUDNATIVE_PG_MEMOS_PASSWORD="<generated-password>"

# Apply the database CR
vals eval -f ../../cluster/cloudnative-pg/memos.yaml | kubectl apply -f -

# Apply the updated cluster configuration with the memos role
vals eval -f ../../cluster/cloudnative-pg/cluster0.yaml | kubectl apply -f -
```

2. **Reload environment variables**:

```shell
direnv allow
```

## Deployment

Deploy Memos using Helmfile:

```shell
cd kubernetes/apps/memos
helmfile apply
```

The deployment will:

1. Create the database DSN secret (via presync hook)
2. Deploy the Memos application with PostgreSQL configuration
3. Set up ingress with TLS

## Access

Once deployed, access Memos at:

```
https://memos.<LOCAL_DOMAIN_NAME>
```

## Configuration

### Helm Chart

The official upstream chart doesn't support PostgreSQL natively, so we maintain a local copy with these modifications:

- **Deployment template**: Added `MEMOS_DRIVER` and `MEMOS_DSN` environment variables
- **Database connection**: Injected from `memos-db-dsn` secret

The connection string format:

```
postgres://memos:PASSWORD@cnpg-cluster0-rw.cnpg-clusters.svc.cluster.local:5432/memos
```

### Storage

Data is persisted in a ZFS-backed PVC:

- **StorageClass**: `zfs-vm-pool-dynamic`
- **Size**: 5Gi
- **Access Mode**: ReadWriteOnce

### Resources

Default resource limits:

- **CPU**: 500m (limit), 100m (request)
- **Memory**: 512Mi (limit), 128Mi (request)

## Updating the Chart

To update to a new upstream version:

1. Check for new releases at https://github.com/usememos/helm
2. Download the new chart files and update `charts/memos/`
3. Ensure the PostgreSQL env vars are preserved in `deployment.yaml`
4. Update the `version` and `appVersion` in `Chart.yaml`

## Uninstall

```shell
cd kubernetes/apps/memos
helmfile destroy
```

**Note**: The PVC will be retained due to the Retain reclaim policy. To fully clean up:

```shell
kubectl delete pvc -n memos memos
```

## References

- [Memos Website](https://usememos.com)
- [Memos GitHub](https://github.com/usememos/memos)
- [Memos Helm Chart](https://github.com/usememos/helm)
- [Memos Documentation](https://usememos.com/docs)
