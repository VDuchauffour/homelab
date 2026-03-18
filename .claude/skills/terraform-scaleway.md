# Terraform Scaleway Operations

Manage the Scaleway reverse proxy infrastructure.

## Usage

```
/terraform-scaleway <plan|apply|destroy>
```

## Architecture

```
Internet -> Traefik (80/443) -> Pangolin -> Gerbil (WireGuard)
                                                ^
                                           Newt clients <- homelab services
```

Components:

- **Pangolin**: Tunnel management platform with web dashboard
- **Gerbil**: WireGuard-based tunnel controller
- **Traefik**: Reverse proxy with automatic HTTPS via Let's Encrypt

## Steps

### Plan

```shell
cd infra/modules/scaleway-proxy

INSTANCE_NAME="proxy"
DOMAIN_NAME="example.com"
USERNAME="admin"
PASSWORD_HASH=$(mkpasswd -m sha-512 'your-password')
ACME_EMAIL="admin@example.com"
PANGOLIN_SECRET=$(openssl rand -base64 48)

terraform plan \
  -var "instance_name=$INSTANCE_NAME" \
  -var "domain_name=$DOMAIN_NAME" \
  -var "username=$USERNAME" \
  -var "password_hash=$PASSWORD_HASH" \
  -var "acme_email=$ACME_EMAIL" \
  -var "pangolin_secret=$PANGOLIN_SECRET"
```

### Apply

Same variables as plan, but with:

```shell
terraform apply -auto-approve \
  -var "instance_name=$INSTANCE_NAME" \
  # ... rest of vars
```

### Post-Apply

SSH into the instance and start Pangolin:

```shell
ssh <username>@<instance-ip>
cd "$HOME_DIR/pangolin"
docker compose up -d
```

Then complete the initial setup at `https://pangolin.<domain>/auth/initial-setup`.

After the proxy is running, update the CoreDNS split-horizon config in the K8s cluster so in-cluster traffic resolves correctly:

1. Set `PANGOLIN_PROXY_IP` in `.envrc` to the new instance IP (from `terraform output`)
2. Set `TRAEFIK_CLUSTER_IP` to the Traefik service ClusterIP (`kubectl get svc traefik -n kube-system -o jsonpath='{.spec.clusterIP}'`)
3. Apply CoreDNS config: `vals eval -f kubernetes/cluster/coredns/coredns-custom.yaml | kubectl apply -f -`
4. Restart CoreDNS: `kubectl rollout restart deployment coredns -n kube-system`
5. Deploy Newt + blueprint: `cd kubernetes/infra/pangolin-newt && helmfile apply`

### Destroy

```shell
terraform destroy -auto-approve \
  -var "instance_name=$INSTANCE_NAME" \
  # ... rest of vars (can use empty strings for most)
```

## Pangolin DB Backup

Pangolin's PostgreSQL database is backed up weekly to a Scaleway Object Storage bucket (`<instance_name>-pangolin-backups`) in `fr-par`.

- **Schedule**: Weekly on Sunday at 3:00 AM (cron in `/etc/cron.d/pangolin-db-backup`)
- **Script**: `/home/<username>/pangolin/backup-db.sh` — dumps via `docker exec postgres pg_dump`, gzips, uploads to S3
- **Retention**: 30 days (bucket lifecycle rule, configurable via `pangolin_backup_retention_days`)
- **Credentials**: Reuses existing Scaleway access/secret keys (same as Traefik DNS challenge)
- **Logs**: `/var/log/pangolin-backup.log`

### Manual Backup

```shell
ssh <username>@<instance-ip>
/home/<username>/pangolin/backup-db.sh
```

### Restore on New Instance

After `terraform apply` + `docker compose up -d` on a fresh instance:

```shell
# List available backups
export AWS_ACCESS_KEY_ID="<scaleway_access_key>"
export AWS_SECRET_ACCESS_KEY="<scaleway_secret_key>"
aws s3 ls s3://<instance_name>-pangolin-backups/ --endpoint-url https://s3.fr-par.scw.cloud

# Download the latest dump
aws s3 cp s3://<instance_name>-pangolin-backups/pangolin-db-<timestamp>.sql.gz /tmp/ --endpoint-url https://s3.fr-par.scw.cloud

# Stop Pangolin (keep Postgres running)
docker stop pangolin gerbil traefik

# Restore
gunzip -c /tmp/pangolin-db-<timestamp>.sql.gz | docker exec -i postgres psql -U <pangolin_pg_user> -d pangolin

# Restart all services
docker compose -f ~/pangolin/compose.yaml up -d
```

## Files

- `main.tf`: Instance, security groups, DNS records, S3 backup bucket
- `variables.tf`: Input variables
- `outputs.tf`: Instance IP output
- `cloud-init.yaml.tftpl`: Cloud-init configuration
- `compose.yaml.tftpl`: Docker Compose for Pangolin, Gerbil, Traefik, CrowdSec
- `config.yml.tftpl`: Pangolin configuration
- `traefik_config.yml.tftpl`: Traefik static configuration
- `dynamic_config.yml.tftpl`: Traefik dynamic configuration
- `backup-db.sh.tftpl`: Pangolin DB backup script (weekly dump to S3)
- `init.sh`: Instance initialization (Docker, CrowdSec firewall bouncer)
