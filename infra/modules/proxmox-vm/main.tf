locals {
  # bpg/proxmox rejects a gateway when address = "dhcp", so it must be unset (null) in that case.
  ipv4_address = var.ip_address != null ? var.ip_address : "dhcp"
  ipv4_gateway = var.ip_address != null ? var.gateway : null

  user_data = templatefile("${path.module}/cloud-init.yaml.tftpl", {
    hostname            = var.name
    username            = var.username
    ssh_public_keys     = var.ssh_public_keys
    user_password       = var.user_password
    additional_packages = var.additional_packages
    run_apt_upgrade     = var.run_apt_upgrade
    additional_runcmd   = var.additional_runcmd
    timezone            = var.timezone
  })

  meta_data = <<-EOT
    instance-id: ${var.name}
    local-hostname: ${var.name}
  EOT
}

resource "proxmox_virtual_environment_file" "user_data" {
  content_type = "snippets"
  datastore_id = var.snippet_datastore_id
  node_name    = var.proxmox_node

  source_raw {
    data      = local.user_data
    file_name = "${var.name}-user-data.yaml"
  }
}

resource "proxmox_virtual_environment_file" "meta_data" {
  content_type = "snippets"
  datastore_id = var.snippet_datastore_id
  node_name    = var.proxmox_node

  source_raw {
    data      = local.meta_data
    file_name = "${var.name}-meta-data.yaml"
  }
}

resource "proxmox_virtual_environment_vm" "this" {
  name        = var.name
  description = var.description
  tags        = var.tags

  node_name       = var.proxmox_node
  vm_id           = var.vm_id
  started         = var.started
  on_boot         = var.on_boot
  stop_on_destroy = true # required so `terraform destroy` can stop a running VM

  agent {
    enabled = true # populates the ipv4_addresses attribute used by the primary_ipv4 output
  }

  cpu {
    cores   = var.cpu_cores
    sockets = var.cpu_sockets
    type    = var.cpu_type
  }

  memory {
    dedicated = var.memory_mb
    floating  = var.memory_mb # floating == dedicated enables ballooning
  }

  disk {
    datastore_id = var.datastore_id
    file_id      = var.image_file_id
    interface    = var.disk_interface
    iothread     = true
    discard      = "on"
    size         = var.disk_size_gb
  }

  network_device {
    bridge      = var.network_bridge
    model       = var.network_model
    vlan_id     = var.network_vlan_id
    mac_address = var.network_mac_address
    firewall    = var.network_firewall
  }

  operating_system {
    type = "l26" # Linux 2.6+ kernel — Proxmox enum value, correct for all modern Ubuntu releases
  }

  initialization {
    datastore_id = var.datastore_id
    interface    = "ide2"

    dns {
      servers = var.dns_servers
      domain  = var.search_domain
    }

    ip_config {
      ipv4 {
        address = local.ipv4_address
        gateway = local.ipv4_gateway
      }
    }

    user_data_file_id = proxmox_virtual_environment_file.user_data.id
    meta_data_file_id = proxmox_virtual_environment_file.meta_data.id
  }

  lifecycle {
    precondition {
      condition     = var.ip_address == null || var.gateway != null
      error_message = "When `ip_address` is set, `gateway` must also be provided."
    }
  }
}
