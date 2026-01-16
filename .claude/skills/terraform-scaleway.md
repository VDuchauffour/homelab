# Terraform Scaleway Operations

Manage the Scaleway reverse proxy infrastructure.

## Usage

```
/terraform-scaleway <plan|apply|destroy>
```

## Architecture

```
Internet -> Caddy (80/443) -> frps:8080 -> homelab services
                                  ^
                             frps:7000 <- homelab frpc clients
```

Components:

- **Caddy**: TLS termination, reverse proxy (auto HTTPS via Let's Encrypt)
- **CrowdSec**: Collaborative security with IP reputation
- **FRP Server (frps)**: Receives tunneled connections from homelab

## Steps

### Plan

```shell
cd infra/modules/scaleway-proxy

INSTANCE_NAME="proxy"
DOMAIN_NAME="example.com"
USERNAME="admin"
PASSWORD_HASH=$(mkpasswd -m sha-512 'your-password')
AUTH_TOKEN="your-frp-auth-token"
FRP_DASHBOARD_PASSWORD="dashboard-password"
CROWDSEC_API_KEY=$(tr -dc A-Za-z0-9 </dev/urandom | head -c 32)
ACME_EMAIL="admin@example.com"

terraform plan \
  -var "instance_name=$INSTANCE_NAME" \
  -var "domain_name=$DOMAIN_NAME" \
  -var "username=$USERNAME" \
  -var "password_hash=$PASSWORD_HASH" \
  -var "auth_token=$AUTH_TOKEN" \
  -var "frp_dashboard_password=$FRP_DASHBOARD_PASSWORD" \
  -var "crowdsec_api_key=$CROWDSEC_API_KEY" \
  -var "acme_email=$ACME_EMAIL"
```

### Apply

Same variables as plan, but with:

```shell
terraform apply -auto-approve \
  -var "instance_name=$INSTANCE_NAME" \
  # ... rest of vars
```

### Post-Apply

SSH into the instance and start the proxy stack:

```shell
ssh <username>@<instance-ip>
cd "$HOME_DIR/proxy"
docker compose up -d --build
```

### Destroy

```shell
terraform destroy -auto-approve \
  -var "instance_name=$INSTANCE_NAME" \
  # ... rest of vars (can use empty strings for most)
```

## Files

- `main.tf`: Instance, security groups, DNS records
- `variables.tf`: Input variables
- `outputs.tf`: Instance IP output
- `cloud-init.yaml.tftpl`: Cloud-init configuration
- `compose.yaml.tftpl`: Docker Compose for Caddy, CrowdSec, FRP
- `Caddyfile.tftpl`: Caddy reverse proxy configuration
