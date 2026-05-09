variable "proxmox_insecure" {
  description = "Skip TLS verification when talking to the Proxmox API. Set true only for self-signed certs you trust."
  type        = bool
  default     = false
}

variable "proxmox_ssh_username" {
  description = "SSH username on the Proxmox node (used by the provider for snippet uploads)."
  type        = string
  default     = "root"
}

variable "proxmox_node" {
  description = "Name of the Proxmox node where the VM will be created (e.g. \"pve\")."
  type        = string
}

variable "name" {
  description = "VM name (also the cloud-init hostname)."
  type        = string
  default     = "k8s-worker-1"
}

variable "image_file_id" {
  description = "Pre-uploaded Ubuntu 26.04 cloud image, e.g. \"local:iso/ubuntu-26.04-server-cloudimg-amd64.img\"."
  type        = string
}

variable "datastore_id" {
  description = "Datastore for the VM disk (e.g. \"local-lvm\", \"local-zfs\")."
  type        = string
  default     = "local-lvm"
}

variable "cpu_cores" {
  description = "Number of vCPU cores. Workers run pods, so default is generous."
  type        = number
  default     = 8
}

variable "memory_mb" {
  description = "Memory in MiB. 16 GiB suits most workload mixes."
  type        = number
  default     = 16384
}

variable "disk_size_gb" {
  description = "Boot disk size in GiB. Sized for container images + ephemeral pod storage."
  type        = number
  default     = 64
}

variable "network_bridge" {
  description = "Linux bridge for the primary NIC."
  type        = string
  default     = "vmbr0"
}

variable "ip_address" {
  description = "Static IPv4 with CIDR (recommended for stable kubelet identity). Leave null for DHCP."
  type        = string
  default     = null
}

variable "gateway" {
  description = "Default gateway IPv4. Required when ip_address is set; ignored for DHCP."
  type        = string
  default     = null
}

variable "dns_servers" {
  description = "DNS servers for cloud-init."
  type        = list(string)
  default     = ["1.1.1.1", "8.8.8.8"]
}

variable "search_domain" {
  description = "DNS search domain. Leave null to omit."
  type        = string
  default     = null
}

variable "username" {
  description = "Cloud-init user with passwordless sudo."
  type        = string
  default     = "ubuntu"
}

variable "ssh_public_keys" {
  description = "SSH public keys authorized for the cloud-init user."
  type        = list(string)
}

variable "timezone" {
  description = "System timezone."
  type        = string
  default     = "Europe/Paris"
}

variable "additional_packages" {
  description = "Extra apt packages to install via cloud-init."
  type        = list(string)
  default = [
    "curl",
    "ca-certificates",
    "gnupg",
    "open-iscsi",
    "nfs-common",
  ]
}

variable "additional_runcmd" {
  description = "Extra cloud-init runcmd entries. Use this to join the node to an existing cluster. See terraform.tfvars.example for snippets."
  type        = list(string)
  default     = []
}
