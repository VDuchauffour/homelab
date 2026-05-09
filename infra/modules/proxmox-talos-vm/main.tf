locals {
  cp_by_name     = { for n in var.control_plane_nodes : n.name => n }
  worker_by_name = { for n in var.worker_nodes : n.name => n }

  bootstrap_node_name = var.control_plane_nodes[0].name
  bootstrap_node_ip   = split("/", var.control_plane_nodes[0].ip)[0]

  cp_endpoints = [for n in var.control_plane_nodes : split("/", n.ip)[0]]
  all_node_ips = concat(
    [for n in var.control_plane_nodes : split("/", n.ip)[0]],
    [for n in var.worker_nodes : split("/", n.ip)[0]],
  )
}

resource "talos_machine_secrets" "this" {
  talos_version = var.talos_version
}

data "talos_machine_configuration" "control_plane" {
  for_each = local.cp_by_name

  cluster_name       = var.cluster_name
  cluster_endpoint   = var.cluster_endpoint
  machine_type       = "controlplane"
  machine_secrets    = talos_machine_secrets.this.machine_secrets
  talos_version      = var.talos_version
  kubernetes_version = var.kubernetes_version

  config_patches = concat(
    var.config_patches_control_plane,
    [yamlencode({
      machine = {
        network = {
          hostname = each.value.name
          interfaces = [{
            interface = "eth0"
            addresses = [each.value.ip]
            routes = [{
              network = "0.0.0.0/0"
              gateway = each.value.gateway
            }]
          }]
          nameservers = var.dns_servers
        }
      }
    })],
  )
}

data "talos_machine_configuration" "worker" {
  for_each = local.worker_by_name

  cluster_name       = var.cluster_name
  cluster_endpoint   = var.cluster_endpoint
  machine_type       = "worker"
  machine_secrets    = talos_machine_secrets.this.machine_secrets
  talos_version      = var.talos_version
  kubernetes_version = var.kubernetes_version

  config_patches = concat(
    var.config_patches_worker,
    [yamlencode({
      machine = {
        network = {
          hostname = each.value.name
          interfaces = [{
            interface = "eth0"
            addresses = [each.value.ip]
            routes = [{
              network = "0.0.0.0/0"
              gateway = each.value.gateway
            }]
          }]
          nameservers = var.dns_servers
        }
      }
    })],
  )
}

data "talos_client_configuration" "this" {
  cluster_name         = var.cluster_name
  client_configuration = talos_machine_secrets.this.client_configuration
  endpoints            = local.cp_endpoints
  nodes                = local.all_node_ips
}

resource "proxmox_virtual_environment_file" "control_plane_config" {
  for_each = local.cp_by_name

  content_type = "snippets"
  datastore_id = var.snippet_datastore_id
  node_name    = var.proxmox_node

  source_raw {
    data      = data.talos_machine_configuration.control_plane[each.key].machine_configuration
    file_name = "${var.cluster_name}-${each.key}.yaml"
  }
}

resource "proxmox_virtual_environment_file" "worker_config" {
  for_each = local.worker_by_name

  content_type = "snippets"
  datastore_id = var.snippet_datastore_id
  node_name    = var.proxmox_node

  source_raw {
    data      = data.talos_machine_configuration.worker[each.key].machine_configuration
    file_name = "${var.cluster_name}-${each.key}.yaml"
  }
}

resource "proxmox_virtual_environment_vm" "control_plane" {
  for_each = local.cp_by_name

  name        = each.value.name
  description = "Talos control-plane (cluster: ${var.cluster_name}) — managed by Terraform"
  tags        = concat(var.tags, ["control-plane"])

  node_name       = var.proxmox_node
  vm_id           = each.value.vm_id
  stop_on_destroy = true

  agent {
    enabled = true
  }

  cpu {
    cores = each.value.cpu
    type  = "x86-64-v2-AES"
  }

  memory {
    dedicated = each.value.memory_mb
    floating  = each.value.memory_mb
  }

  disk {
    datastore_id = var.datastore_id
    file_id      = var.image_file_id
    interface    = "virtio0"
    iothread     = true
    discard      = "on"
    size         = each.value.disk_gb
  }

  network_device {
    bridge      = each.value.bridge
    model       = "virtio"
    vlan_id     = each.value.vlan_id
    mac_address = each.value.mac
  }

  operating_system {
    type = "l26"
  }

  initialization {
    datastore_id = var.datastore_id
    interface    = "ide2"

    ip_config {
      ipv4 {
        address = "dhcp" # Talos applies its real network config from the machineconfig user-data
      }
    }

    user_data_file_id = proxmox_virtual_environment_file.control_plane_config[each.key].id
  }
}

resource "proxmox_virtual_environment_vm" "worker" {
  for_each = local.worker_by_name

  name        = each.value.name
  description = "Talos worker (cluster: ${var.cluster_name}) — managed by Terraform"
  tags        = concat(var.tags, ["worker"])

  node_name       = var.proxmox_node
  vm_id           = each.value.vm_id
  stop_on_destroy = true

  agent {
    enabled = true
  }

  cpu {
    cores = each.value.cpu
    type  = "x86-64-v2-AES"
  }

  memory {
    dedicated = each.value.memory_mb
    floating  = each.value.memory_mb
  }

  disk {
    datastore_id = var.datastore_id
    file_id      = var.image_file_id
    interface    = "virtio0"
    iothread     = true
    discard      = "on"
    size         = each.value.disk_gb
  }

  network_device {
    bridge      = each.value.bridge
    model       = "virtio"
    vlan_id     = each.value.vlan_id
    mac_address = each.value.mac
  }

  operating_system {
    type = "l26"
  }

  initialization {
    datastore_id = var.datastore_id
    interface    = "ide2"

    ip_config {
      ipv4 {
        address = "dhcp"
      }
    }

    user_data_file_id = proxmox_virtual_environment_file.worker_config[each.key].id
  }
}

resource "talos_machine_configuration_apply" "control_plane" {
  for_each = local.cp_by_name

  client_configuration        = talos_machine_secrets.this.client_configuration
  machine_configuration_input = data.talos_machine_configuration.control_plane[each.key].machine_configuration
  node                        = split("/", each.value.ip)[0]

  depends_on = [proxmox_virtual_environment_vm.control_plane]
}

resource "talos_machine_configuration_apply" "worker" {
  for_each = local.worker_by_name

  client_configuration        = talos_machine_secrets.this.client_configuration
  machine_configuration_input = data.talos_machine_configuration.worker[each.key].machine_configuration
  node                        = split("/", each.value.ip)[0]

  depends_on = [proxmox_virtual_environment_vm.worker]
}

resource "talos_machine_bootstrap" "this" {
  client_configuration = talos_machine_secrets.this.client_configuration
  node                 = local.bootstrap_node_ip

  depends_on = [talos_machine_configuration_apply.control_plane]
}

resource "talos_cluster_kubeconfig" "this" {
  client_configuration = talos_machine_secrets.this.client_configuration
  node                 = local.bootstrap_node_ip

  depends_on = [talos_machine_bootstrap.this]
}
