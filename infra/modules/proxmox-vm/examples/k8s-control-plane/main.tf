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

module "control_plane" {
  source = "../.."

  name         = var.name
  proxmox_node = var.proxmox_node
  description  = "Kubernetes control-plane node — managed by Terraform"
  tags         = ["k8s", "control-plane", "terraform"]

  image_file_id = var.image_file_id
  datastore_id  = var.datastore_id
  disk_size_gb  = var.disk_size_gb

  cpu_cores = var.cpu_cores
  memory_mb = var.memory_mb

  network_bridge = var.network_bridge
  ip_address     = var.ip_address
  gateway        = var.gateway
  dns_servers    = var.dns_servers
  search_domain  = var.search_domain

  username        = var.username
  ssh_public_keys = var.ssh_public_keys
  timezone        = var.timezone

  additional_packages = var.additional_packages
  additional_runcmd   = var.additional_runcmd
}

output "vm_id" {
  description = "Proxmox VM ID of the control plane."
  value       = module.control_plane.vm_id
}

output "primary_ipv4" {
  description = "Primary IPv4 address of the control plane (becomes available after qemu-guest-agent starts)."
  value       = module.control_plane.primary_ipv4
}

output "ssh_command" {
  description = "Convenience SSH command once the VM is up."
  value       = "ssh ${var.username}@${split("/", var.ip_address)[0]}"
}
