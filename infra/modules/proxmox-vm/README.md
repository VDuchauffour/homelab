# proxmox-vm

Reusable Terraform module that provisions an Ubuntu cloud-image VM on Proxmox VE
using the [`bpg/proxmox`](https://registry.terraform.io/providers/bpg/proxmox/latest)
provider.

The defaults are tuned for **Kubernetes worker nodes** (8 vCPU, 16 GiB RAM,
64 GiB disk, virtio NIC, static IP), but every knob is configurable.

## What this module does

For each instance, the module:

1. Renders a cloud-init `user-data` snippet (hostname, user, SSH keys, packages,
   timezone, runcmd) and uploads it to the Proxmox snippet datastore.
2. Renders a cloud-init `meta-data` snippet (`instance-id`, `local-hostname`) and
   uploads it.
3. Creates a `proxmox_virtual_environment_vm` that:
   - Clones the boot disk from a pre-uploaded cloud image (`disk.file_id`).
   - Wires up the cloud-init drive on `ide2`
     (`initialization.user_data_file_id` / `meta_data_file_id`).
   - Installs `qemu-guest-agent` so the provider can report the VM's IP
     addresses back to Terraform.

## Prerequisites

### 1. Provider configuration (in the consumer/root module)

This module declares only `required_providers` — the consumer is responsible
for configuring the provider, **including the SSH block**. Snippet uploads
go over SSH even when API token auth is used for the API.

```hcl
provider "proxmox" {
  endpoint  = "https://pve.example.com:8006/"
  api_token = var.proxmox_api_token   # username@realm!token-id=token-secret
  insecure  = false                   # set true only for self-signed certs you trust

  ssh {
    agent    = true                   # use ssh-agent for key auth
    username = "root"                 # SSH user with permission to write snippets
  }
}
```

### 2. Environment variables for credentials

The `bpg/proxmox` provider reads these env vars when set, so secrets don't
need to live in Terraform code or `tfvars`:

```bash
# Add to .envrc (gitignored)
export PROXMOX_VE_ENDPOINT="https://pve.example.com:8006/"
export PROXMOX_VE_API_TOKEN="terraform@pve!automation=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
export PROXMOX_VE_SSH_AGENT="true"
export PROXMOX_VE_SSH_USERNAME="root"
# Set this if your Proxmox cert is self-signed:
# export PROXMOX_VE_INSECURE="true"
```

### 3. Snippets enabled on the Proxmox storage

`content_type = "snippets"` upload targets need the **Snippets** content type
enabled on the datastore. In the Proxmox web UI:

> Datacenter → Storage → `local` → Edit → Content → check **Snippets**

Without this, snippet upload fails with a 500 from the Proxmox API.

### 4. Ubuntu 26.04 cloud image uploaded to Proxmox

Upload the official Canonical cloud image to a Proxmox storage that has the
`iso` content type enabled. From a Proxmox node shell:

```bash
cd /var/lib/vz/template/iso/
wget https://cloud-images.ubuntu.com/releases/26.04/release/ubuntu-26.04-server-cloudimg-amd64.img
```

Then reference it via
`image_file_id = "local:iso/ubuntu-26.04-server-cloudimg-amd64.img"`.

> Use the `-cloudimg-` image — **not** the desktop or live-server ISO. Cloud
> images come with cloud-init pre-installed and expect the cloud-init drive on
> `ide2`.

## Examples

Two ready-to-run consumer configs live under [`examples/`](examples/):

| Path | Purpose | Key defaults |
|------|---------|--------------|
| [`examples/k8s-control-plane/`](examples/k8s-control-plane/) | Single control-plane node (k3s/RKE2 server) | 4 vCPU / 8 GiB / 32 GiB; **static IP required**; runcmd hints for k3s `--cluster-init` and RKE2 server |
| [`examples/k8s-worker/`](examples/k8s-worker/) | Worker node | 8 vCPU / 16 GiB / 64 GiB; static IP recommended (DHCP supported); runcmd hints for joining an existing k3s/RKE2 server |

Each example is a standalone root config with its own `provider "proxmox"`,
`variables.tf`, and `terraform.tfvars.example`:

```bash
cd infra/modules/proxmox-vm/examples/k8s-control-plane
cp terraform.tfvars.example terraform.tfvars
# edit terraform.tfvars with your values
terraform init
terraform apply
```

The provider's `endpoint` and `api_token` are read from
`PROXMOX_VE_ENDPOINT` / `PROXMOX_VE_API_TOKEN` env vars (set them in your
`.envrc`) — the examples do not require them in `tfvars`.

## Usage — Kubernetes worker

```hcl
terraform {
  required_version = ">= 1.6.0"
  required_providers {
    proxmox = {
      source  = "bpg/proxmox"
      version = ">= 0.99.0, < 1.0.0"
    }
  }
}

provider "proxmox" {
  ssh {
    agent    = true
    username = "root"
  }
}

module "k8s_worker_1" {
  source = "../../modules/proxmox-vm"

  name         = "k8s-worker-1"
  proxmox_node = "pve"
  description  = "Kubernetes worker node #1"
  tags         = ["k8s", "worker", "terraform"]

  # Boot from pre-uploaded Ubuntu 26.04 cloud image
  image_file_id = "local:iso/ubuntu-26.04-server-cloudimg-amd64.img"
  datastore_id  = "local-zfs"
  disk_size_gb  = 64

  # Resources (defaults are already tuned for K8s workers, override as needed)
  cpu_cores = 8
  memory_mb = 16384

  # Static IP on the homelab subnet
  network_bridge = "vmbr0"
  ip_address     = "192.168.1.41/24"
  gateway        = "192.168.1.1"
  dns_servers    = ["192.168.1.10", "1.1.1.1"]
  search_domain  = "home.arpa"

  # Cloud-init user
  username = "ubuntu"
  ssh_public_keys = [
    file("~/.ssh/id_ed25519.pub"),
  ]
  timezone = "Europe/Paris"

  additional_packages = [
    "curl",
    "ca-certificates",
    "gnupg",
    "open-iscsi", # required by some CSI drivers
    "nfs-common", # required for NFS PVs
  ]

  additional_runcmd = [
    # k3s install (example — uncomment and adjust):
    # "curl -sfL https://get.k3s.io | K3S_URL=https://k3s-server:6443 K3S_TOKEN=xxxxx sh -",
  ]
}

output "worker_ip" {
  value = module.k8s_worker_1.primary_ipv4
}
```

## Usage — DHCP variant

Drop `ip_address` and `gateway`:

```hcl
module "dev_vm" {
  source = "../../modules/proxmox-vm"

  name          = "dev-vm"
  proxmox_node  = "pve"
  image_file_id = "local:iso/ubuntu-26.04-server-cloudimg-amd64.img"

  cpu_cores       = 2
  memory_mb       = 2048
  disk_size_gb    = 16
  ssh_public_keys = [file("~/.ssh/id_ed25519.pub")]
  # ip_address omitted -> DHCP
}
```

## Inputs

The module exposes ~30 variables. See [`variables.tf`](variables.tf) for the
full reference. The most commonly tuned ones:

| Variable                 | Default                  | Notes |
|--------------------------|--------------------------|-------|
| `name`                   | (required)               | DNS-valid; used as hostname and snippet filename prefix |
| `proxmox_node`           | (required)               | Proxmox node name (e.g. `pve`) |
| `image_file_id`          | (required)               | Pre-uploaded cloud image, e.g. `local:iso/ubuntu-26.04-server-cloudimg-amd64.img` |
| `cpu_cores`              | `8`                      | |
| `memory_mb`              | `16384`                  | Set as both `dedicated` and `floating` (ballooning) |
| `disk_size_gb`           | `64`                     | Must be ≥ source image size |
| `datastore_id`           | `local-lvm`              | Where the VM disk and cloud-init drive live |
| `snippet_datastore_id`   | `local`                  | Must have **Snippets** content enabled |
| `network_bridge`         | `vmbr0`                  | |
| `ip_address`             | `null`                   | CIDR for static, `null` for DHCP |
| `gateway`                | `null`                   | Required when `ip_address` is set |
| `dns_servers`            | `["1.1.1.1", "8.8.8.8"]` | |
| `username`               | `ubuntu`                 | Cloud-init user with passwordless sudo |
| `ssh_public_keys`        | `[]`                     | List of SSH pubkeys to authorize |
| `additional_packages`    | `[]`                     | Extra apt packages (qemu-guest-agent is always installed) |
| `timezone`               | `null`                   | e.g. `"Europe/Paris"` |

## Outputs

| Output             | Description |
|--------------------|-------------|
| `vm_id`            | Proxmox VM ID assigned by the provider |
| `name`             | VM name |
| `node_name`        | Proxmox node hosting the VM |
| `primary_ipv4`     | First non-loopback IPv4 from the QEMU guest agent (set after first boot) |
| `ipv4_addresses`   | All IPv4 addresses reported per interface |
| `mac_addresses`    | NIC MAC addresses |
| `user_data_file_id`, `meta_data_file_id` | Snippet IDs (useful for debugging) |

## Gotchas

1. **`primary_ipv4` is unknown until the QEMU agent runs.** The first apply
   may show `(known after apply)` and may briefly error trying to read the IP
   if the agent isn't responsive yet. Re-run after a minute, or `depends_on`
   any consumer of `primary_ipv4` to avoid race conditions.
2. **Snippet datastore must support snippets.** `local` (directory storage)
   does; `local-lvm` does not. They are typically distinct datastores.
3. **Cloud image must support cloud-init.** Use Ubuntu's *cloud* image
   (`-cloudimg-`), not the desktop or live-server ISO. The cloud image is
   ~700 MiB, pre-installs cloud-init, and expects the cloud-init drive on
   `ide2` (which this module configures).
4. **`stop_on_destroy = true` is hardcoded** — without it, `terraform destroy`
   fails on a running VM.
5. **`dns.servers` is plural** (the singular `dns.server` was removed in
   bpg/proxmox v0.75.0). This module uses the current API.
6. **The Ubuntu 26.04 cloud image is amd64 by default.** For ARM nodes, use
   `ubuntu-26.04-server-cloudimg-arm64.img` and ensure the Proxmox node is
   ARM-capable.
