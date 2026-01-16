terraform {
  required_version = ">= 1.2.0, < 2.0.0"
  required_providers {
    scaleway = {
      source  = "scaleway/scaleway"
      version = "~> 2.0"
    }
  }
}

provider "scaleway" {
  zone   = var.zone
  region = var.region
}

resource "scaleway_instance_ip" "public_ip" {
  zone = var.zone
}

resource "scaleway_instance_server" "dev" {
  name  = var.instance_name
  type  = var.instance_type
  image = var.image_id
  zone  = var.zone

  ip_id = scaleway_instance_ip.public_ip.id

  cloud_init = templatefile("cloud-init.yaml.tftpl", {
    init_script            = file("init.sh")
    compose_file           = file("compose.yaml")
    dockerfile_frps        = file("Dockerfile.frps")
    caddyfile              = templatefile("Caddyfile", { DOMAIN_NAME = var.domain_name })
    domain_name            = var.domain_name
    username               = var.username
    password_hash          = var.password_hash
    auth_token             = var.auth_token
    frp_dashboard_password = var.frp_dashboard_password
  })

  tags = var.tags

  root_volume {
    size_in_gb = var.root_volume_size
  }
}

resource "scaleway_domain_record" "apex" {
  dns_zone = var.domain_name
  name     = ""
  type     = "A"
  data     = scaleway_instance_ip.public_ip.address
  ttl      = 3600
}

resource "scaleway_domain_record" "wildcard" {
  dns_zone = var.domain_name
  name     = "*"
  type     = "A"
  data     = scaleway_instance_ip.public_ip.address
  ttl      = 3600
}
