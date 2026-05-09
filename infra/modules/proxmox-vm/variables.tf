variable "name" {
  description = "VM name (also used as the cloud-init hostname). Must be a valid DNS label."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$", var.name))
    error_message = "name must be a valid DNS label (lowercase letters, digits, hyphens; 1-63 chars; no leading/trailing hyphen)."
  }
}

variable "vm_id" {
  description = "Proxmox VM ID. Must be unique on the node. Leave null to let Proxmox auto-assign."
  type        = number
  default     = null
}

variable "proxmox_node" {
  description = "Name of the Proxmox node where the VM will be created (e.g. \"pve\")."
  type        = string
}

variable "description" {
  description = "VM description shown in the Proxmox UI."
  type        = string
  default     = "Managed by Terraform"
}

variable "tags" {
  description = "Tags applied to the VM. Proxmox sorts them alphabetically."
  type        = list(string)
  default     = ["terraform"]
}

variable "started" {
  description = "Whether the VM should be running. Set false to provision but not start."
  type        = bool
  default     = true
}

variable "on_boot" {
  description = "Whether the VM should start automatically when the Proxmox node boots."
  type        = bool
  default     = true
}

variable "cpu_cores" {
  description = "Number of vCPU cores per socket."
  type        = number
  default     = 8

  validation {
    condition     = var.cpu_cores >= 1 && var.cpu_cores <= 128
    error_message = "cpu_cores must be between 1 and 128."
  }
}

variable "cpu_sockets" {
  description = "Number of CPU sockets."
  type        = number
  default     = 1
}

variable "cpu_type" {
  description = "CPU type. \"x86-64-v2-AES\" is recommended for modern Linux. \"host\" passes through host CPU features (best perf, breaks live migration)."
  type        = string
  default     = "x86-64-v2-AES"
}

variable "memory_mb" {
  description = "Memory in MiB. Used for both `dedicated` and `floating` (ballooning enabled by default)."
  type        = number
  default     = 16384

  validation {
    condition     = var.memory_mb >= 512
    error_message = "memory_mb must be at least 512 MiB."
  }
}

variable "datastore_id" {
  description = "Datastore for the VM disk and the cloud-init drive (e.g. \"local-lvm\", \"local-zfs\")."
  type        = string
  default     = "local-lvm"
}

variable "image_file_id" {
  description = "Pre-uploaded cloud image to clone as the boot disk. Format: \"<storage>:iso/<filename>\" — e.g. \"local:iso/ubuntu-26.04-server-cloudimg-amd64.img\"."
  type        = string

  validation {
    condition     = can(regex("^[^:]+:iso/.+\\.(img|qcow2|raw|vmdk)$", var.image_file_id))
    error_message = "image_file_id must be of the form \"<storage>:iso/<filename>\" with a .img/.qcow2/.raw/.vmdk extension."
  }
}

variable "disk_size_gb" {
  description = "Boot disk size in GiB. Must be greater than or equal to the source cloud image."
  type        = number
  default     = 64
}

variable "disk_interface" {
  description = "Boot disk interface. \"virtio0\" is recommended for performance."
  type        = string
  default     = "virtio0"
}

variable "snippet_datastore_id" {
  description = "Datastore for cloud-init snippet uploads. Must have the \"snippets\" content type enabled in Proxmox (Datacenter → Storage → Edit → Content → Snippets)."
  type        = string
  default     = "local"
}

variable "network_bridge" {
  description = "Linux bridge for the primary NIC (e.g. \"vmbr0\")."
  type        = string
  default     = "vmbr0"
}

variable "network_model" {
  description = "Network device model. \"virtio\" is recommended."
  type        = string
  default     = "virtio"
}

variable "network_vlan_id" {
  description = "VLAN tag for the primary NIC. Leave null for untagged."
  type        = number
  default     = null
}

variable "network_mac_address" {
  description = "MAC address for the primary NIC. Leave null to let Proxmox auto-generate (recommended)."
  type        = string
  default     = null
}

variable "network_firewall" {
  description = "Whether the Proxmox firewall is enabled on the primary NIC."
  type        = bool
  default     = false
}

variable "ip_address" {
  description = "Static IPv4 with CIDR (e.g. \"192.168.1.50/24\"). Leave null for DHCP."
  type        = string
  default     = null

  validation {
    condition     = var.ip_address == null || can(regex("^([0-9]{1,3}\\.){3}[0-9]{1,3}/[0-9]{1,2}$", var.ip_address))
    error_message = "ip_address must be in CIDR notation (e.g. \"192.168.1.50/24\") or null for DHCP."
  }
}

variable "gateway" {
  description = "Default gateway IPv4. Required when ip_address is set; ignored when DHCP is used."
  type        = string
  default     = null
}

variable "dns_servers" {
  description = "DNS servers configured via cloud-init."
  type        = list(string)
  default     = ["1.1.1.1", "8.8.8.8"]
}

variable "search_domain" {
  description = "DNS search domain for cloud-init. Leave null to omit."
  type        = string
  default     = null
}

variable "username" {
  description = "User created on first boot via cloud-init. Granted passwordless sudo."
  type        = string
  default     = "ubuntu"
}

variable "ssh_public_keys" {
  description = "SSH public keys authorized for the cloud-init user. At least one key is strongly recommended."
  type        = list(string)
  default     = []
}

variable "user_password" {
  description = "Optional password for the cloud-init user. Leave null to disable password login (SSH-key only, recommended)."
  type        = string
  default     = null
  sensitive   = true
}

variable "additional_packages" {
  description = "Extra apt packages to install via cloud-init. `qemu-guest-agent` is always installed."
  type        = list(string)
  default     = []
}

variable "run_apt_upgrade" {
  description = "Run `apt-get upgrade` on first boot."
  type        = bool
  default     = true
}

variable "additional_runcmd" {
  description = "Extra cloud-init `runcmd` entries appended after qemu-guest-agent enablement. Each entry must be a single shell command."
  type        = list(string)
  default     = []
}

variable "timezone" {
  description = "System timezone (e.g. \"Europe/Paris\"). Leave null to keep the cloud image default (UTC)."
  type        = string
  default     = null
}
