terraform {
  required_version = ">= 1.6.0"

  required_providers {
    proxmox = {
      source  = "bpg/proxmox"
      version = ">= 0.99.0, < 1.0.0"
    }
    talos = {
      source  = "siderolabs/talos"
      version = ">= 0.6.0, < 1.0.0"
    }
  }
}

provider "proxmox" {
  insecure = var.proxmox_insecure

  ssh {
    username    = var.proxmox_ssh_username
    private_key = var.proxmox_ssh_private_key_file != null ? file(pathexpand(var.proxmox_ssh_private_key_file)) : null
    agent       = var.proxmox_ssh_private_key_file == null

    node {
      name    = var.proxmox_node
      address = var.proxmox_node_address
    }
  }
}

provider "talos" {}

module "talos_cluster" {
  source = "../.."

  cluster_name       = var.cluster_name
  cluster_endpoint   = var.cluster_endpoint
  talos_version      = var.talos_version
  kubernetes_version = var.kubernetes_version

  proxmox_node         = var.proxmox_node
  image_file_id        = var.image_file_id
  datastore_id         = var.datastore_id
  snippet_datastore_id = var.snippet_datastore_id

  control_plane_nodes = var.control_plane_nodes
  worker_nodes        = var.worker_nodes

  dns_servers = var.dns_servers

  config_patches_control_plane = var.config_patches_control_plane
  config_patches_worker        = var.config_patches_worker
}

output "kubeconfig" {
  description = "Save with: terraform output -raw kubeconfig > ~/.kube/config-<cluster>"
  value       = module.talos_cluster.kubeconfig
  sensitive   = true
}

output "talosconfig" {
  description = "Save with: terraform output -raw talosconfig > ~/.talos/config"
  value       = module.talos_cluster.talosconfig
  sensitive   = true
}

output "control_plane_ips" {
  value = module.talos_cluster.control_plane_ips
}

output "worker_ips" {
  value = module.talos_cluster.worker_ips
}
