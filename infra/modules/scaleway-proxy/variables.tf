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

variable "ssh_public_keys" {
  description = "List of SSH public keys to authorize"
  type        = list(string)
}

variable "acme_email" {
  description = "Email for ACME certificate registration"
  type        = string
}

variable "pangolin_secret" {
  description = "Secret key for Pangolin server encryption (min 32 chars, generate with: openssl rand -base64 48)"
  type        = string
  sensitive   = true
}

variable "pangolin_pg_user" {
  description = "PostgreSQL username for Pangolin"
  type        = string
  default     = "pangolin"
}

variable "pangolin_pg_password" {
  description = "PostgreSQL password for Pangolin (generate with: openssl rand -base64 32)"
  type        = string
  sensitive   = true
}

variable "scaleway_access_key" {
  description = "Scaleway API access key for DNS challenge (from ~/.config/scw/config.yaml)"
  type        = string
  sensitive   = true
}

variable "scaleway_secret_key" {
  description = "Scaleway API secret key for DNS challenge (from ~/.config/scw/config.yaml)"
  type        = string
  sensitive   = true
}

variable "crowdsec_bouncer_key" {
  description = "API key for the CrowdSec Traefik bouncer plugin (generate with: openssl rand -base64 32)"
  type        = string
  sensitive   = true
}

variable "crowdsec_firewall_bouncer_key" {
  description = "API key for the CrowdSec host firewall bouncer (generate with: openssl rand -base64 32)"
  type        = string
  sensitive   = true
}

variable "crowdsec_capi_whitelisted_cidrs" {
  description = "CIDR ranges to exempt from CrowdSec CAPI community bans (e.g. mobile carrier ranges to avoid CGNAT false positives)"
  type        = list(string)
  default     = []
}

variable "crowdsec_webui_machine_password" {
  description = "Machine account password for CrowdSec Web UI to authenticate with LAPI (generate with: openssl rand -hex 32)"
  type        = string
  sensitive   = true
}

variable "crowdsec_webui_basic_auth" {
  description = "Htpasswd-format credentials for CrowdSec Web UI basic auth (generate with: htpasswd -nB admin)"
  type        = string
  sensitive   = true
}

variable "crowdsec_console_enrollment_id" {
  description = "Enrollment ID for the CrowdSec Console dashboard (from https://app.crowdsec.net)"
  type        = string
  default     = ""
}

variable "pangolin_backup_retention_days" {
  description = "Number of days to retain Pangolin database backups in the S3 bucket (lifecycle expiration)"
  type        = number
  default     = 30
}
