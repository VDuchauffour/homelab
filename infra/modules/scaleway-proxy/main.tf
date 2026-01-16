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

resource "scaleway_instance_security_group" "proxy" {
  name                    = "${var.instance_name}-sg"
  zone                    = var.zone
  inbound_default_policy  = "drop"
  outbound_default_policy = "accept"

  # SSH
  inbound_rule {
    action   = "accept"
    port     = 22
    protocol = "TCP"
  }

  # HTTP
  inbound_rule {
    action   = "accept"
    port     = 80
    protocol = "TCP"
  }

  # HTTPS
  inbound_rule {
    action   = "accept"
    port     = 443
    protocol = "TCP"
  }

  # HTTPS UDP (HTTP/3 / QUIC)
  inbound_rule {
    action   = "accept"
    port     = 443
    protocol = "UDP"
  }

  # FRP tunnel
  inbound_rule {
    action   = "accept"
    port     = 7000
    protocol = "TCP"
  }

  # FRP SSH proxy
  inbound_rule {
    action   = "accept"
    port     = 6000
    protocol = "TCP"
  }
}

resource "scaleway_instance_server" "dev" {
  name  = var.instance_name
  type  = var.instance_type
  image = var.image_id
  zone  = var.zone

  ip_id             = scaleway_instance_ip.public_ip.id
  security_group_id = scaleway_instance_security_group.proxy.id

  cloud_init = templatefile("cloud-init.yaml.tftpl", {
    init_script = file("init.sh")
    compose_file = templatefile("compose.yaml.tftpl", {
      crowdsec_api_key = var.crowdsec_api_key
    })
    dockerfile_frps  = file("Dockerfile.frps")
    dockerfile_caddy = file("Dockerfile.caddy")
    acquis_yaml      = file("crowdsec/acquis.yaml")
    caddyfile = templatefile("Caddyfile.tftpl", {
      domain_name      = var.domain_name
      crowdsec_api_key = var.crowdsec_api_key
      acme_email       = var.acme_email
    })
    domain_name            = var.domain_name
    username               = var.username
    password_hash          = var.password_hash
    auth_token             = var.auth_token
    frp_dashboard_password = var.frp_dashboard_password
    crowdsec_api_key       = var.crowdsec_api_key
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
