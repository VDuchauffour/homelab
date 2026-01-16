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

variable "username" {
  description = "Username for the instance"
  type        = string
  default     = "username"
}

variable "password_hash" {
  description = "SHA-512 hashed password for the user (generate with: mkpasswd -m sha-512 'password')"
  type        = string
  sensitive   = true
}

variable "auth_token" {
  description = "FRP authentication token"
  type        = string
  sensitive   = true
}

variable "frp_dashboard_password" {
  description = "FRP dashboard password"
  type        = string
  sensitive   = true
}
