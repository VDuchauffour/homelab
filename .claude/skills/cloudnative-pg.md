# CloudNativePG Database Operations

Manage PostgreSQL databases using CloudNativePG operator with Barman Cloud Plugin backups.

## Usage

```
/cloudnative-pg <create|backup|restore|connect>
```

## Current Cluster

- **Cluster**: `cnpg-cluster0` in `cnpg-clusters` namespace (1 instance)
- **Storage**: `zfs-vm-pool-dynamic` (10Gi, dynamically provisioned ZFS)
- **Databases**: See `kubernetes/cluster/cloudnative-pg/*.yaml`
- **Backups**: Barman Cloud Plugin to MinIO (`cnpg-backups` bucket), daily at 2:00 AM UTC, 30d retention

## Create Database Cluster

Create a `Cluster` resource:

```yaml
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: <app-name>-db
  namespace: <namespace>
  annotations:
    cnpg.io/skipEmptyWalArchiveCheck: enabled
spec:
  instances: 1  # or 3 for HA

  postgresql:
    parameters:
      max_connections: "100"
      shared_buffers: "256MB"

  storage:
    size: 10Gi
    storageClass: zfs-vm-pool-dynamic

  bootstrap:
    initdb:
      database: <database-name>
      owner: <username>
      secret:
        name: <app-name>-db-credentials

  plugins:
    - name: barman-cloud.cloudnative-pg.io
      isWALArchiver: true
      parameters:
        barmanObjectName: <objectstore-name>
```

## Create Credentials Secret

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: <app-name>-db-credentials
  namespace: <namespace>
  labels:
    cnpg.io/reload: 'true'
type: kubernetes.io/basic-auth
stringData:
  username: <username>
  password: <password>
```

## Connect to Database

### From within cluster

Service DNS: `<cluster-name>-rw.<namespace>.svc.cluster.local`

Connection string:

```
postgresql://<username>:<password>@<cluster-name>-rw:5432/<database>
```

### Using pgAdmin

pgAdmin is deployed at `kubernetes/apps/pgadmin/`

### Port forward

```shell
kubectl port-forward -n <namespace> svc/<cluster-name>-rw 5432:5432
psql -h localhost -U <username> -d <database>
```

## Check Status

```shell
# Full cluster status (includes backup info, WAL archiving, instances)
kubectl cnpg status cnpg-cluster0 -n cnpg-clusters

# Cluster resource
kubectl get cluster -n <namespace>

# Pod status
kubectl get pods -n <namespace> -l cnpg.io/cluster=<cluster-name>

# Database CRs
kubectl get database -n cnpg-clusters
```

## Backup & Restore (Barman Cloud Plugin)

Backups use the [Barman Cloud Plugin](https://cloudnative-pg.io/plugin-barman-cloud/) deployed at `kubernetes/infra/plugin-barman-cloud/`.

### Infrastructure

- **Plugin**: Helm chart `cnpg/plugin-barman-cloud` v0.5.0 in `cnpg-system` namespace
- **ObjectStore CR**: `cnpg-minio-store` in `cnpg-clusters` namespace
- **ScheduledBackup CR**: `cnpg-cluster0-daily` -- daily at 2:00 AM UTC
- **Destination**: MinIO bucket `cnpg-backups` at `http://minio.minio.svc.cluster.local:9000`
- **Credentials**: Secret `minio-cnpg-credentials` in `cnpg-clusters` (keys: `ACCESS_KEY_ID`, `ACCESS_SECRET_KEY`)
- **Retention**: 30 days
- **WAL compression**: gzip, 2 parallel workers

### Check Backup Status

```shell
kubectl cnpg status cnpg-cluster0 -n cnpg-clusters
kubectl get backup -n cnpg-clusters
kubectl get scheduledbackup -n cnpg-clusters
kubectl get objectstore -n cnpg-clusters
```

### Trigger Manual Backup

```yaml
apiVersion: postgresql.cnpg.io/v1
kind: Backup
metadata:
  name: manual-backup
  namespace: cnpg-clusters
spec:
  cluster:
    name: cnpg-cluster0
  method: plugin
  pluginConfiguration:
    name: barman-cloud.cloudnative-pg.io
```

### Restore from Backup (New Cluster)

Bootstrap a new cluster from an existing backup:

```yaml
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: cnpg-cluster0-restore
  namespace: cnpg-clusters
  annotations:
    cnpg.io/skipEmptyWalArchiveCheck: enabled
spec:
  instances: 1
  storage:
    size: 10Gi
    storageClass: zfs-vm-pool-dynamic

  bootstrap:
    recovery:
      source: origin

  plugins:
    - name: barman-cloud.cloudnative-pg.io
      isWALArchiver: true
      parameters:
        barmanObjectName: cnpg-minio-store

  externalClusters:
    - name: origin
      plugin:
        name: barman-cloud.cloudnative-pg.io
        parameters:
          barmanObjectName: cnpg-minio-store
          serverName: cnpg-cluster0
```

### Point-In-Time Recovery (PITR)

Add `recoveryTarget` to the bootstrap recovery section:

```yaml
bootstrap:
  recovery:
    source: origin
    recoveryTarget:
      targetTime: "2026-02-06 12:00:00 UTC"
```

### Logical Backup (pg_dumpall)

For migration or cross-version upgrades:

```shell
# Dump all databases
kubectl exec -n cnpg-clusters cnpg-cluster0-1 -c postgres -- pg_dumpall -U postgres --clean > /tmp/cnpg-dumpall.sql

# Restore (pipe via stdin, read-only filesystem in container)
cat /tmp/cnpg-dumpall.sql | kubectl exec -i -n cnpg-clusters cnpg-cluster0-1 -c postgres -- psql -U postgres
```

## Adding a New Database

1. Generate a password: `openssl rand -base64 32`
2. Create a credentials secret + `Database` CR in `kubernetes/cluster/cloudnative-pg/<app>.yaml`
3. Add a managed role in `cluster0.yaml` under `spec.managed.roles`
4. Store the password as an environment variable (e.g. `CLOUDNATIVE_PG_<APP>_PASSWORD`)
5. Apply with `vals eval -f <file> | kubectl apply -f -`

## Reference

- Operator: `kubernetes/infra/cloudnative-pg/`
- Barman Cloud Plugin: `kubernetes/infra/plugin-barman-cloud/`
- Cluster + Secrets: `kubernetes/cluster/cloudnative-pg/cluster0.yaml`
- Backup config: `kubernetes/cluster/cloudnative-pg/backup.yaml`
- Database CRs: `kubernetes/cluster/cloudnative-pg/<app>.yaml`
- Example secret: `kubernetes/infra/cloudnative-pg/manifests/secret.yaml`
