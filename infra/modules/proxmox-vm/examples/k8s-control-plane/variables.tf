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

variable "proxmox_ssh_private_key_file" {
  description = "Path to a private SSH key for the Proxmox node (e.g. \"~/.ssh/id_ed25519\"). When set, this is used directly and ssh-agent is bypassed. Leave null to use ssh-agent instead."
  type        = string
  default     = null
}

variable "proxmox_node" {
  description = "Name of the Proxmox node where the VM will be created (e.g. \"pve\")."
  type        = string
}

variable "proxmox_node_address" {
  description = "SSH-reachable address of the Proxmox node (e.g. \"192.168.1.100\"). Defaults to the API endpoint hostname when omitted, which often differs from the SSH-reachable address."
  type        = string
}

variable "name" {
  description = "VM name (also the cloud-init hostname)."
  type        = string
  default     = "k8s-cp-1"
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
  description = "Number of vCPU cores. Control planes are typically less CPU-hungry than workers."
  type        = number
  default     = 4
}

variable "memory_mb" {
  description = "Memory in MiB. 8 GiB is a comfortable baseline for kube-apiserver + etcd + scheduler + controller-manager."
  type        = number
  default     = 8192
}

variable "disk_size_gb" {
  description = "Boot disk size in GiB. Control planes don't host workload data, so 32 GiB is usually plenty."
  type        = number
  default     = 32
}

variable "network_bridge" {
  description = "Linux bridge for the primary NIC."
  type        = string
  default     = "vmbr0"
}

variable "ip_address" {
  description = "Static IPv4 with CIDR. REQUIRED — workers must be able to resolve the control plane at a stable address."
  type        = string

  validation {
    condition     = can(regex("^([0-9]{1,3}\\.){3}[0-9]{1,3}/[0-9]{1,2}$", var.ip_address))
    error_message = "ip_address must be in CIDR notation (e.g. \"192.168.1.40/24\"). Control planes do not support DHCP."
  }
}

variable "gateway" {
  description = "Default gateway IPv4."
  type        = string
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
  description = "Extra cloud-init runcmd entries. Use this to install k3s/RKE2/kubeadm. See terraform.tfvars.example for snippets."
  type        = list(string)
  default     = []
}
