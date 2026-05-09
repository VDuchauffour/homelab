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
    agent    = true
    username = var.proxmox_ssh_username
  }
}

module "worker" {
  source = "../.."

  name         = var.name
  proxmox_node = var.proxmox_node
  description  = "Kubernetes worker node — managed by Terraform"
  tags         = ["k8s", "worker", "terraform"]

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
  description = "Proxmox VM ID of the worker."
  value       = module.worker.vm_id
}

output "primary_ipv4" {
  description = "Primary IPv4 address of the worker (becomes available after qemu-guest-agent starts)."
  value       = module.worker.primary_ipv4
}

output "ssh_command" {
  description = "Convenience SSH command. For DHCP (ip_address = null), use module.worker.primary_ipv4 after first apply."
  value = (
    var.ip_address != null
    ? "ssh ${var.username}@${split("/", var.ip_address)[0]}"
    : "ssh ${var.username}@${module.worker.primary_ipv4}"
  )
}
