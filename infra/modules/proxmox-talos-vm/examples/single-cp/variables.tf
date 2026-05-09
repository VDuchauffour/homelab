variable "proxmox_insecure" {
  description = "Skip TLS verification when talking to the Proxmox API. Set true for self-signed certs you trust."
  type        = bool
  default     = true
}

variable "proxmox_ssh_username" {
  description = "SSH username on the Proxmox node (used by the provider for snippet uploads)."
  type        = string
  default     = "root"
}

variable "proxmox_ssh_private_key_file" {
  description = "Path to a private SSH key for the Proxmox node. When set, ssh-agent is bypassed. Leave null to use the agent."
  type        = string
  default     = null
}

variable "proxmox_node" {
  description = "Proxmox node name (e.g. \"pve\")."
  type        = string
}

variable "proxmox_node_address" {
  description = "SSH-reachable address of the Proxmox node (e.g. \"192.168.1.100\")."
  type        = string
}

variable "cluster_name" {
  description = "Talos / Kubernetes cluster name."
  type        = string
  default     = "homelab"
}

variable "cluster_endpoint" {
  description = "Kubernetes API endpoint URL. For single-CP, use \"https://<cp-ip>:6443\"."
  type        = string
}

variable "talos_version" {
  description = "Talos version matching the boot image (e.g. \"v1.10.0\"). Look it up at factory.talos.dev for the image you downloaded."
  type        = string
  default     = null
}

variable "kubernetes_version" {
  description = "Kubernetes version (e.g. \"1.32.0\"). Leave null for Talos default."
  type        = string
  default     = null
}

variable "image_file_id" {
  description = "Pre-uploaded Talos nocloud image, e.g. \"local:iso/nocloud-amd64.raw\"."
  type        = string
}

variable "datastore_id" {
  description = "Datastore for VM disks."
  type        = string
  default     = "local-lvm"
}

variable "snippet_datastore_id" {
  description = "Datastore for cloud-init snippets (must have Snippets content enabled)."
  type        = string
  default     = "local"
}

variable "control_plane_nodes" {
  description = "Exactly one CP node for this single-CP module."
  type = list(object({
    name      = string
    vm_id     = optional(number)
    cpu       = optional(number, 4)
    memory_mb = optional(number, 8192)
    disk_gb   = optional(number, 32)
    bridge    = optional(string, "vmbr0")
    vlan_id   = optional(number)
    ip        = string
    gateway   = string
    mac       = optional(string)
  }))
}

variable "worker_nodes" {
  description = "Worker nodes (zero or more)."
  type = list(object({
    name      = string
    vm_id     = optional(number)
    cpu       = optional(number, 4)
    memory_mb = optional(number, 8192)
    disk_gb   = optional(number, 64)
    bridge    = optional(string, "vmbr0")
    vlan_id   = optional(number)
    ip        = string
    gateway   = string
    mac       = optional(string)
  }))
  default = []
}

variable "dns_servers" {
  description = "DNS servers configured in each node's Talos machine config."
  type        = list(string)
  default     = ["1.1.1.1", "8.8.8.8"]
}

variable "config_patches_control_plane" {
  description = "Extra Talos machine-config patches for control-plane nodes (YAML/JSON strings)."
  type        = list(string)
  default     = []
}

variable "config_patches_worker" {
  description = "Extra Talos machine-config patches for worker nodes."
  type        = list(string)
  default     = []
}
