output "vm_id" {
  description = "Proxmox VM ID assigned to the VM."
  value       = proxmox_virtual_environment_vm.this.vm_id
}

output "name" {
  description = "VM name (also the cloud-init hostname)."
  value       = proxmox_virtual_environment_vm.this.name
}

output "node_name" {
  description = "Proxmox node hosting the VM."
  value       = proxmox_virtual_environment_vm.this.node_name
}

output "ipv4_addresses" {
  description = "All IPv4 addresses reported by the QEMU guest agent, grouped per network interface."
  value       = proxmox_virtual_environment_vm.this.ipv4_addresses
}

output "primary_ipv4" {
  description = "First non-loopback IPv4 address reported by the QEMU guest agent. Becomes available after first boot once qemu-guest-agent is running."
  value = try(
    [
      for addrs in proxmox_virtual_environment_vm.this.ipv4_addresses : addrs[0]
      if length(addrs) > 0 && addrs[0] != "127.0.0.1"
    ][0],
    null
  )
}

output "mac_addresses" {
  description = "MAC addresses for each network interface."
  value       = proxmox_virtual_environment_vm.this.mac_addresses
}

output "user_data_file_id" {
  description = "Proxmox file ID of the generated cloud-init user-data snippet (useful for debugging)."
  value       = proxmox_virtual_environment_file.user_data.id
}

output "meta_data_file_id" {
  description = "Proxmox file ID of the generated cloud-init meta-data snippet (useful for debugging)."
  value       = proxmox_virtual_environment_file.meta_data.id
}
