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

output "dns_zone" {
  description = "DNS zone ID"
  value       = scaleway_domain_zone.main.id
}

output "dns_nameservers" {
  description = "DNS nameservers for the zone"
  value       = scaleway_domain_zone.main.ns
}
