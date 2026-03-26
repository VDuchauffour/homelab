______________________________________________________________________

## name: restic-backups description: Manage app config backups using the unified Restic backup Helm chart. Use when adding, triggering, checking, or restoring Restic backups for Kubernetes apps backed up to RustFS. compatibility: Requires helmfile, helm, kubectl, and vals CLI tools metadata: author: homelab version: "1.0"

# Restic Backups

## Architecture

```
CronJob (orchestrator) -> scales down app -> creates inner Job (restic + PVC mounts) -> restic backup to RustFS -> scales app back up
```

Two backup modes:

- **Orchestrated** (default): Scales down the app, runs backup in an inner Job, scales back up via EXIT trap
- **Direct**: Simple CronJob with restic container directly mounting volumes (used for nfs-share)

## Key Files

- **Chart**: `kubernetes/cluster/backups/charts/restic-backups/`
- **Helmfile**: `kubernetes/cluster/backups/helmfile.yaml`
- **App values**: `kubernetes/cluster/backups/values.yaml`
- **Destination**: RustFS bucket `restic-backups` at `http://rustfs-svc.rustfs.svc.cluster.local:9000`

## Add a New App Backup

1. Add an entry to `kubernetes/cluster/backups/values.yaml` under `apps:`:

   ```yaml
   <app-name>:
     namespace: <namespace>
     schedule: "<cron-expression>"  # e.g. "5 3 * * 0" (Sunday 3:05 AM)
     targets:
       - type: deployment  # or statefulset
         name: <deployment-name>
     pvcs:
       - name: <pvc-name>
         mountPath: /data  # or /data/<subdir> for multi-PVC apps
   ```

2. Optional fields:

   ```yaml
     # For direct mode (no scale-down, e.g. NFS shares)
     mode: direct
     hostPaths:
       - name: <volume-name>
         path: /host/path
         mountPath: /data

     # Exclude patterns
     excludes:
       - "*.log"
       - "cache/*"

     # Apps sharing a namespace need unique RBAC names
     uniqueNames: true

     # Multiple PVCs
     pvcs:
       - name: config-pvc
         mountPath: /data/config
       - name: data-pvc
         mountPath: /data/app

     # Multiple scale targets (e.g. deployment + statefulset)
     targets:
       - type: deployment
         name: app-deploy
       - type: statefulset
         name: app-db
   ```

3. Deploy:

   ```shell
   cd kubernetes/cluster/backups
   helmfile apply
   ```

4. Verify:

   ```shell
   kubectl get cronjob restic-backup-<app-name> -n <namespace>
   kubectl get job restic-init-<app-name> -n <namespace>
   ```

## Schedule Convention

- Weekly on Sundays, staggered 5-minute intervals starting at 3:00 AM
- Retention: 2 weekly snapshots
- Check existing schedules in `values.yaml` to avoid overlap

## Trigger Backup Manually

Single app:

```shell
kubectl create job --from=cronjob/restic-backup-<app> manual-backup-<app> -n <namespace>
```

All apps:

```shell
kubectl get cronjobs -A --no-headers | grep restic-backup | awk '{print "kubectl create job --from=cronjob/" $2 " manual-backup-" substr($2, 15) " -n " $1}' | sh
```

**Warning**: Orchestrated backups scale down apps during backup. Running all simultaneously will briefly take down all apps.

## Delete Previous Manual Jobs

Before re-triggering, delete existing manual jobs:

```shell
kubectl get jobs -A --no-headers | grep manual-backup | awk '{print $1, $2}' | while read ns job; do kubectl delete job "$job" -n "$ns"; done
```

## Check Backup Status

```shell
# CronJob schedules
kubectl get cronjobs -A | grep restic

# Running/completed jobs
kubectl get jobs -A | grep restic

# Logs for a specific backup
kubectl logs job/manual-backup-<app> -n <namespace>

# Init job status (restic repo initialization)
kubectl get jobs -A | grep restic-init
```

## Restore from Backup

1. List available snapshots:

   ```shell
   # Run a temporary pod with restic and the app's credentials secret
   kubectl run restic-restore --rm -it \
     --image=restic/restic:0.17.3 \
     --overrides='{
       "spec": {
         "containers": [{
           "name": "restic-restore",
           "image": "restic/restic:0.17.3",
           "command": ["sh"],
           "stdin": true,
           "tty": true,
           "envFrom": [{"secretRef": {"name": "restic-rustfs-credentials"}}]
         }]
       }
     }' \
     -n <namespace>

   # Inside the pod:
   restic snapshots --tag <app-name>
   ```

2. Restore to a directory:

   ```shell
   # Inside the restic pod:
   restic restore latest --tag <app-name> --target /tmp/restore
   ```

3. Copy restored files to the app's PVC (scale down app first):

   ```shell
   kubectl cp <pod>:/tmp/restore/data /local/path
   # Then copy back to PVC or mount PVC in restore pod
   ```

## Environment Variables

Required in `.envrc`:

- `RUSTFS_ROOT_USER` — RustFS access key
- `RUSTFS_ROOT_PASSWORD` — RustFS secret key
- `RESTIC_PASSWORD` — Restic repository encryption password
- `SINGLE_NODE_NAME` — Node name for nodeSelector

## Current Backed-Up Apps (21)

| App | Namespace | Schedule | Mode |
|-----|-----------|----------|------|
| arr (6 apps) | arr | Sun 3:00 | orchestrated |
| filebrowser | filebrowser | Sun 3:05 | orchestrated |
| linkding | linkding | Sun 3:10 | orchestrated |
| linkwarden | linkwarden | Sun 3:15 | orchestrated |
| memos | memos | Sun 3:20 | orchestrated |
| n8n | n8n | Sun 3:25 | orchestrated |
| pgadmin | pgadmin | Sun 3:30 | orchestrated |
| pihole | pihole | Sun 3:35 | orchestrated |
| protonmail-bridge | protonmail-bridge | Sun 3:40 | orchestrated |
| slskd | slskd | Sun 3:45 | orchestrated |
| wakapi | wakapi | Sun 3:50 | orchestrated |
| helm-dashboard | kube-system | Sun 3:55 | orchestrated |
| jellyfin | media-center | Sun 3:00 | orchestrated |
| jellyseerr | media-center | Sun 4:00 | orchestrated |
| nfs-share | nfs-server-share | Sun 4:00 | direct |
| nextcloud | nextcloud | Sun 4:10 | orchestrated |
| privatebin | privatebin | Sun 4:20 | orchestrated |
| qbittorrent-vpn | qbittorrent-vpn | Sun 4:25 | orchestrated |
| scrutiny | scrutiny | Sun 4:30 | orchestrated |
| seafile | seafile | Sun 4:35 | orchestrated |
| zfdash | zfdash | Sun 4:45 | orchestrated |

## Troubleshooting

- **Inner job not created**: Check orchestrator logs for API errors (`kubectl logs job/manual-backup-<app> -n <namespace>`)
- **App stuck at 0 replicas**: The cleanup trap failed. Manually scale up: `kubectl scale deployment/<name> -n <namespace> --replicas=1`
- **Init job failed**: Check `kubectl logs job/restic-init-<app> -n <namespace>` — usually a credentials or connectivity issue with RustFS
- **Restic lock error**: A previous backup may have crashed. Run `restic unlock` from a temporary pod with the app's credentials
