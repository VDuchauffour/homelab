output "instance_id" {
  description = "Instance ID"
  value       = scaleway_instance_server.dev.id
}

output "public_ip" {
  description = "Public IP address"
  value       = scaleway_instance_ip.public_ip.address
}

output "ssh_command" {
  description = "SSH command"
  value       = "ssh k@${scaleway_instance_ip.public_ip.address}"
}
