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
- `compose.yaml.tftpl`: Docker Compose for Pangolin, Gerbil, Traefik
- `config.yml.tftpl`: Pangolin configuration
- `traefik_config.yml.tftpl`: Traefik static configuration
- `dynamic_config.yml.tftpl`: Traefik dynamic configuration
