variable "cluster_name" {
  description = "Talos / Kubernetes cluster name."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$", var.cluster_name))
    error_message = "cluster_name must be a valid DNS label."
  }
}

variable "cluster_endpoint" {
  description = "Kubernetes API endpoint URL (e.g. \"https://192.168.1.40:6443\"). For single-CP clusters this is the CP node's IP. For HA, it should be a VIP or load balancer."
  type        = string
}

variable "talos_version" {
  description = "Talos version to render machine config against (e.g. \"v1.10.0\"). Leave null to use the provider default. Must match the version of the boot image."
  type        = string
  default     = null
}

variable "kubernetes_version" {
  description = "Kubernetes version (e.g. \"1.32.0\"). Leave null to use Talos default."
  type        = string
  default     = null
}

variable "proxmox_node" {
  description = "Name of the Proxmox node where VMs will be created."
  type        = string
}

variable "image_file_id" {
  description = "Pre-uploaded Talos `nocloud` image, e.g. \"local:iso/nocloud-amd64.raw\". Download from https://factory.talos.dev/."
  type        = string

  validation {
    condition     = can(regex("^[^:]+:iso/.+$", var.image_file_id))
    error_message = "image_file_id must be \"<storage>:iso/<filename>\"."
  }
}

variable "datastore_id" {
  description = "Datastore for VM disks (e.g. \"local-lvm\", \"local-zfs\")."
  type        = string
  default     = "local-lvm"
}

variable "snippet_datastore_id" {
  description = "Datastore for cloud-init/machineconfig snippets. Must have the \"snippets\" content type enabled."
  type        = string
  default     = "local"
}

variable "control_plane_nodes" {
  description = "List of control-plane node specs. Exactly one is required for this single-CP module."
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

  validation {
    condition     = length(var.control_plane_nodes) == 1
    error_message = "This module is single-CP only — provide exactly one control-plane node."
  }

  validation {
    condition     = alltrue([for n in var.control_plane_nodes : can(regex("^([0-9]{1,3}\\.){3}[0-9]{1,3}/[0-9]{1,2}$", n.ip))])
    error_message = "Each control-plane node's `ip` must be in CIDR notation (e.g. \"192.168.1.40/24\")."
  }
}

variable "worker_nodes" {
  description = "List of worker node specs. Empty list creates a CP-only cluster (workloads can run on the CP if it's untainted)."
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

  validation {
    condition     = alltrue([for n in var.worker_nodes : can(regex("^([0-9]{1,3}\\.){3}[0-9]{1,3}/[0-9]{1,2}$", n.ip))])
    error_message = "Each worker node's `ip` must be in CIDR notation."
  }
}

variable "dns_servers" {
  description = "DNS servers configured in each node's Talos machine config."
  type        = list(string)
  default     = ["1.1.1.1", "8.8.8.8"]
}

variable "config_patches_control_plane" {
  description = "Additional Talos machine-config patches applied to control-plane nodes (each entry is a YAML or JSON string)."
  type        = list(string)
  default     = []
}

variable "config_patches_worker" {
  description = "Additional Talos machine-config patches applied to worker nodes."
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Tags applied to every VM."
  type        = list(string)
  default     = ["talos", "terraform"]
}
