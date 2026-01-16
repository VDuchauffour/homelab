# homelab

## Infrastructure

### Reverse proxy

The homelab is exposed to the Internet through a reverse proxy hosted on Scaleway. The stack runs entirely in Docker:

- **Caddy** handles TLS termination and reverse proxying (auto HTTPS via Let's Encrypt)
- **FRP server** (frps) receives tunneled connections from homelab services

Resources are provisioned using Terraform and are defined in `infra/modules/scaleway-proxy/`. You'll need a [Scaleway config file](https://cli.scaleway.com/config/) and to modify `ssh_authorized_keys` in `cloud-init.yaml.tftpl`.

#### Architecture

```
Internet → Caddy (80/443) → frps:8080 (services) or frps:7500 (dashboard)
                                 ↑
                            frps:7000 ← homelab frpc clients
```

The FRP dashboard is accessible at `https://frp.<domain>`.

To use docker without `sudo` run login as user and run `newgrp docker`.

#### Deployment

```shell
cd ./infra/modules/scaleway-proxy

INSTANCE_NAME="instance-name"
DOMAIN_NAME="example.com"
USERNAME="username"
PASSWORD_HASH=$(mkpasswd -m sha-512 'your-password')
AUTH_TOKEN="your-frp-auth-token"
FRP_DASHBOARD_PASSWORD="frp-dashboard-password"

terraform plan \
  -var "instance_name=$INSTANCE_NAME" \
  -var "domain_name=$DOMAIN_NAME" \
  -var "username=$USERNAME" \
  -var "password_hash=$PASSWORD_HASH" \
  -var "auth_token=$AUTH_TOKEN" \
  -var "frp_dashboard_password=$FRP_DASHBOARD_PASSWORD"

terraform apply \
  -auto-approve \
  -var "instance_name=$INSTANCE_NAME" \
  -var "domain_name=$DOMAIN_NAME" \
  -var "username=$USERNAME" \
  -var "password_hash=$PASSWORD_HASH" \
  -var "auth_token=$AUTH_TOKEN" \
  -var "frp_dashboard_password=$FRP_DASHBOARD_PASSWORD"
```

#### Destroy

```shell
cd ./infra/modules/scaleway-proxy
terraform destroy -auto-approve
```

## Kubernetes

The entire homelab is managed with Kubernetes.

### Recreate CA for local network

```shell
CERT_DIR=$(mkcert -CAROOT)
kubectl create secret tls mkcert-ca-key-pair -n cert-manager --cert=$CERT_DIR/rootCA.pem --key=$CERT_DIR/rootCA-key.pem
kubectl apply -f cluster/cert-manager/manifests/mkcert-ca-issuer.yaml
```

In the ingress, adding the following annotation with cert-manager will:

- Create a Certificate resource
- Issue a leaf cert signed by your mkcert CA
- Manage renewals automatically
- Maintain the qbittorrent-mkcert-tls Secret

```yaml
ingress:
  enabled: true
  className: traefik
  annotations:
    kubernetes.io/ingress.class: traefik
    cert-manager.io/cluster-issuer: mkcert-ca
```

### GPUs management

To watch the usage of iGPU (through Intel QSV or VAAPI) use the command `intel_gpu_top` from the package `intel-gpu-tools`.

You can also check supported VAAPI profiles with `vainfo` from the package `libva-utils`.

You can uerify OpenCL availability with `clinfo` from the package `clinfo`.

With the Intel GPU devices and operator, you can info the GPU status with the command:

```shell
kubectl get gpudeviceplugins
```

You can get more info about that [here](https://intel.github.io/intel-device-plugins-for-kubernetes/cmd/gpu_plugin/README.html).

## Password generation recommandation

```shell
pwgen -scyn 32 1
or
openssl rand -base64 32
```

## Acknowledgments

- Some charts are inspired by [rtomik's helm-charts repository](https://github.com/rtomik/helm-charts)
- The FRP server setup is inspired by [jpfranca-br's repository](https://github.com/jpfranca-br/frps-setup)
