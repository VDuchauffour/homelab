output "talosconfig" {
  description = "talosctl client configuration. Save with `terraform output -raw talosconfig > ~/.talos/config`."
  value       = data.talos_client_configuration.this.talos_config
  sensitive   = true
}

output "kubeconfig" {
  description = "Kubernetes admin kubeconfig. Save with: terraform output -raw kubeconfig > ~/.kube/config-<cluster>"
  value       = talos_cluster_kubeconfig.this.kubeconfig_raw
  sensitive   = true
}

output "cluster_endpoint" {
  description = "Kubernetes API endpoint."
  value       = var.cluster_endpoint
}

output "control_plane_ips" {
  description = "Control-plane node IPs (without CIDR)."
  value       = [for n in var.control_plane_nodes : split("/", n.ip)[0]]
}

output "worker_ips" {
  description = "Worker node IPs (without CIDR)."
  value       = [for n in var.worker_nodes : split("/", n.ip)[0]]
}

output "control_plane_vm_ids" {
  description = "Proxmox VM IDs of control-plane nodes."
  value       = { for k, vm in proxmox_virtual_environment_vm.control_plane : k => vm.vm_id }
}

output "worker_vm_ids" {
  description = "Proxmox VM IDs of worker nodes."
  value       = { for k, vm in proxmox_virtual_environment_vm.worker : k => vm.vm_id }
}

output "machine_secrets" {
  description = "Talos machine secrets (PKI). Treat as sensitive — anyone with this can take over the cluster."
  value       = talos_machine_secrets.this.machine_secrets
  sensitive   = true
}
