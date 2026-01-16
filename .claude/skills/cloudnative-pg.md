# CloudNativePG Database Operations

Manage PostgreSQL databases using CloudNativePG operator.

## Usage

```
/cloudnative-pg <create|backup|restore|connect>
```

## Create Database Cluster

Create a `Cluster` resource:

```yaml
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: <app-name>-db
  namespace: <namespace>
spec:
  instances: 1  # or 3 for HA

  postgresql:
    parameters:
      max_connections: "100"
      shared_buffers: "256MB"

  storage:
    size: 10Gi
    storageClass: openebs-hostpath

  bootstrap:
    initdb:
      database: <database-name>
      owner: <username>
      secret:
        name: <app-name>-db-credentials

  superuserSecret:
    name: <app-name>-db-superuser
```

## Create Credentials Secret

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: <app-name>-db-credentials
  namespace: <namespace>
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
# Cluster status
kubectl get cluster -n <namespace>

# Pod status
kubectl get pods -n <namespace> -l cnpg.io/cluster=<cluster-name>

# Describe cluster
kubectl describe cluster -n <namespace> <cluster-name>
```

## Backup & Restore

Refer to CloudNativePG documentation for backup configurations with object storage.

## Reference

- Operator: `kubernetes/infra/cloudnative-pg/`
- Example secret: `kubernetes/infra/cloudnative-pg/manifests/secret.yaml`
