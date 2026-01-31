# An opinionated Kubernetes-based homelab

This repository contains all the declarations necessary for the operation of my homelab. It uses Kubernetes as applications orchestrator.

## Infrastructure

### Reverse proxy

The homelab is exposed to the Internet through a reverse proxy hosted on Scaleway. The stack runs entirely in Docker:

- **Caddy** handles TLS termination and reverse proxying (auto HTTPS via Let's Encrypt)
- **CrowdSec** provides collaborative security with IP reputation and behavior analysis
- **FRP server** (frps) receives tunneled connections from homelab services

Resources are provisioned using Terraform and are defined in `infra/`. You'll need a [Scaleway config file](https://cli.scaleway.com/config/).

#### Architecture

```
Internet → Caddy (80/443) → frps:8080 (services) or frps:7500 (dashboard)
                                 ↑
                            frps:7000 ← homelab frpc clients
```

The FRP dashboard is accessible at `https://frp.<domain>`.

Generate the password hash with:

```shell
docker run --rm caddy:2-alpine caddy hash-password --plaintext 'your-password'
```

Then set `basic_auth_user`, `basic_auth_hash`, `subdomains_with_basic_auth` and `subdomains_without_basic_auth` in your `terraform.tfvars`.

To use docker without `sudo` run login as user and run `newgrp docker`.

#### Deployment

```shell
cd ./infra/modules/scaleway-proxy

cp ./terraform.tfvars.example ./terraform.tfvars
# edit the file with the relevant values

terraform init
terraform plan
terraform apply
```

Once the instance is ready, run:

```shell
cd "$HOME_DIR/proxy"
docker compose up -d --build
```

#### Destroy

```shell
cd ./infra/modules/scaleway-proxy
terraform destroy
```

## Kubernetes

The entire homelab is managed with Kubernetes. Here's the structure of the folder:

```shell
kubernetes
├── apps      # user-facing application workloads
├── cluster   # cluster-level configuration and shared resources
└── infra     # cluster-wide infrastructure services
```

### Postgres

All postgres database runs in a [CloudnativePG cluster](https://cloudnative-pg.io/). You can see the [kubectl plugin](https://cloudnative-pg.io/documentation/1.20/kubectl-plugin/) to help you to manage the Postgres cluster and databases.

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
