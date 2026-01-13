variable "zone" {
  description = "Scaleway zone"
  type        = string
  default     = "fr-par-1"
}

variable "region" {
  description = "Scaleway region"
  type        = string
  default     = "fr-par"
}

variable "instance_name" {
  description = "Instance name"
  type        = string
  default     = "dev-instance"
}

variable "instance_type" {
  description = "Instance type"
  type        = string
  default     = "DEV1-S"
}

variable "image_id" {
  description = "Image ID (e.g., Ubuntu 22.04)"
  type        = string
  default     = "ubuntu_jammy" # or specific UUID
}

variable "root_volume_size" {
  description = "Root volume size in GB"
  type        = number
  default     = 20
}

variable "tags" {
  description = "Instance tags"
  type        = list(string)
  default     = ["terraform", "dev"]
}

variable "domain_name" {
  description = "Domain name to manage DNS for"
  type        = string
}
