# proxmox-talos-vm

Terraform module that provisions a complete **single-control-plane Talos
Kubernetes cluster** on Proxmox VE.

One `terraform apply` produces:

- N×1 control-plane VM + N workers (boot from the Talos `nocloud` image)
- Talos PKI + machineconfig generated and injected as cloud-init `user-data`
- All nodes come up with their final network config (no DHCP)
- First control plane is bootstrapped (etcd starts)
- `kubeconfig` and `talosconfig` available as outputs

## Architecture

```
talos_machine_secrets   ─┐
talos_machine_config × N ─┼─► proxmox_file (snippet) × N ─► proxmox_vm × N
                         │                                       │
                         └──► talos_machine_config_apply × N ─────┤
                                                                  │
                          talos_machine_bootstrap (first CP) ◄────┘
                                  │
                          talos_cluster_kubeconfig
```

## Prerequisites

1. **Talos `nocloud` image uploaded to Proxmox.** Download from the [Talos
   image factory](https://factory.talos.dev/) — pick **Cloud → Nocloud**, raw
   disk, amd64, and grab the URL. On the Proxmox node:

   ```bash
   cd /var/lib/vz/template/iso/
   wget -O nocloud-amd64.raw.xz https://factory.talos.dev/image/.../nocloud-amd64.raw.xz
   xz -d nocloud-amd64.raw.xz
   ```

   Then reference as `image_file_id = "local:iso/nocloud-amd64.raw"`.

2. **Snippets enabled on the snippet datastore.** Datacenter → Storage →
   `local` → Edit → Content → check **Snippets**.

3. **Proxmox provider auth** (env vars in `.envrc`):

   ```bash
   export PROXMOX_VE_ENDPOINT="https://192.168.1.100:8006/"
   export PROXMOX_VE_API_TOKEN="terraform@pve!automation=..."
   export PROXMOX_VE_INSECURE="true" # if Proxmox cert is self-signed
   export PROXMOX_VE_SSH_USERNAME="root"
   ```

4. **Talos version pinning.** The Talos image, the `talos_version` variable,
   and the provider must agree. Look up the image's version at
   factory.talos.dev when you download it, and pass that to `talos_version`.

5. **Network reachability.** The machine running Terraform must reach each
   node IP on TCP/50000 (Talos API) for `_apply` and `_bootstrap` to work.

## Usage

```hcl
terraform {
  required_version = ">= 1.6.0"
  required_providers {
    proxmox = { source = "bpg/proxmox", version = ">= 0.99.0, < 1.0.0" }
    talos   = { source = "siderolabs/talos", version = ">= 0.6.0, < 1.0.0" }
  }
}

provider "proxmox" {
  insecure = true
  ssh {
    username    = "root"
    private_key = file(pathexpand("~/.ssh/proxmox"))
    node {
      name    = "pve"
      address = "192.168.1.100"
    }
  }
}

provider "talos" {}

module "talos_cluster" {
  source = "../../modules/proxmox-talos-vm"

  cluster_name     = "homelab"
  cluster_endpoint = "https://192.168.1.40:6443"
  talos_version    = "v1.10.0"

  proxmox_node  = "pve"
  image_file_id = "local:iso/nocloud-amd64.raw"
  datastore_id  = "local-zfs"

  control_plane_nodes = [
    {
      name      = "talos-cp1"
      cpu       = 4
      memory_mb = 8192
      disk_gb   = 32
      ip        = "192.168.1.40/24"
      gateway   = "192.168.1.1"
    },
  ]

  worker_nodes = [
    {
      name      = "talos-w1"
      cpu       = 8
      memory_mb = 16384
      disk_gb   = 64
      ip        = "192.168.1.41/24"
      gateway   = "192.168.1.1"
    },
    {
      name      = "talos-w2"
      cpu       = 8
      memory_mb = 16384
      disk_gb   = 64
      ip        = "192.168.1.42/24"
      gateway   = "192.168.1.1"
    },
  ]

  dns_servers = ["192.168.1.10", "1.1.1.1"]
}

output "kubeconfig"   { value = module.talos_cluster.kubeconfig,   sensitive = true }
output "talosconfig"  { value = module.talos_cluster.talosconfig,  sensitive = true }
```

After `terraform apply`:

```bash
# Save credentials
terraform output -raw talosconfig >~/.talos/config
terraform output -raw kubeconfig >~/.kube/config-homelab

export KUBECONFIG=~/.kube/config-homelab
kubectl get nodes
talosctl --talosconfig=~/.talos/config -n 192.168.1.40 dashboard
```

## Inputs (key ones)

| Variable | Default | Notes |
|---|---|---|
| `cluster_name` | (required) | DNS-label format |
| `cluster_endpoint` | (required) | `https://<cp-ip>:6443` for single-CP |
| `talos_version` | `null` | Pin to match your `nocloud` image version |
| `kubernetes_version` | `null` | Defaults to whatever Talos ships |
| `image_file_id` | (required) | `<storage>:iso/<filename>` of pre-uploaded Talos nocloud image |
| `proxmox_node` | (required) | |
| `datastore_id` | `local-lvm` | VM disk storage |
| `snippet_datastore_id` | `local` | Must have Snippets content enabled |
| `control_plane_nodes` | (required, length=1) | List of objects: `name`, `ip`, `gateway`, optional cpu/memory/disk/vm_id/mac/vlan_id |
| `worker_nodes` | `[]` | Same shape as CP nodes |
| `dns_servers` | `["1.1.1.1", "8.8.8.8"]` | Written into each node's machineconfig |
| `config_patches_control_plane` | `[]` | List of YAML/JSON patch strings (e.g. install disk, custom CNI, registries) |
| `config_patches_worker` | `[]` | |

## Outputs

| Output | Description |
|---|---|
| `kubeconfig` | Admin kubeconfig (sensitive) |
| `talosconfig` | talosctl client config (sensitive) |
| `cluster_endpoint` | API endpoint URL |
| `control_plane_ips` / `worker_ips` | Lists of node IPs |
| `control_plane_vm_ids` / `worker_vm_ids` | Maps of name→Proxmox VM ID |
| `machine_secrets` | Cluster PKI (sensitive — treat like a root credential) |

## Common config patches

### Install disk

By default Talos installs to `/dev/sda`. To use a different disk:

```hcl
config_patches_control_plane = [
  yamlencode({
    machine = {
      install = {
        disk = "/dev/vda"
      }
    }
  })
]
```

### Allow workloads on the control plane (single-node clusters)

```hcl
config_patches_control_plane = [
  yamlencode({
    cluster = {
      allowSchedulingOnControlPlanes = true
    }
  })
]
```

### Add a registry mirror

```hcl
config_patches_control_plane = [
  yamlencode({
    machine = {
      registries = {
        mirrors = {
          "docker.io" = { endpoints = ["https://my-registry.local"] }
        }
      }
    }
  })
]
```

## Gotchas

1. **Talos version drift.** The boot image, the `talos_version` variable, and
   `data.talos_machine_configuration` must agree. If the image is `v1.10.0`
   but you set `talos_version = "v1.9.0"`, the node refuses to apply config.
2. **`talos_machine_configuration_apply` waits up to ~10 min for the API.**
   The first apply takes 1–3 minutes typically (image boots, kernel loads,
   Talos brings up its API). If it times out, the IP is wrong, the node didn't
   boot, or the network config in the patch doesn't match the network reality.
3. **`talos_machine_bootstrap` is one-shot.** It runs etcd-init exactly once
   per cluster. Re-running terraform apply doesn't re-bootstrap (the resource
   is idempotent). If bootstrap fails, fix the cause and run
   `terraform taint module.<x>.talos_machine_bootstrap.this` then re-apply.
4. **No SSH on Talos nodes — period.** Use `talosctl` for everything. There
   is no shell, no users, no Linux package manager.
5. **Reaching nodes from outside the homelab.** `talos_machine_configuration_apply`
   talks to TCP/50000 on each node. If you run Terraform from a remote
   machine, ensure routing/firewall allows it.

## Themes

Some themes are available [here](https://github.com/IT-BAER/proxmorph).
