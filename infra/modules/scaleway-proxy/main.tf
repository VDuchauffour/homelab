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

  # WireGuard (Gerbil tunnel)
  inbound_rule {
    action   = "accept"
    port     = 51820
    protocol = "UDP"
  }

  # WireGuard (Gerbil client relay)
  inbound_rule {
    action   = "accept"
    port     = 21820
    protocol = "UDP"
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
    backup_script = templatefile("backup-db.sh.tftpl", {
      pangolin_backup_bucket = scaleway_object_bucket.pangolin_backups.name
      region                 = var.region
      scaleway_access_key    = var.scaleway_access_key
      scaleway_secret_key    = var.scaleway_secret_key
      pangolin_pg_user       = var.pangolin_pg_user
    })
    compose_file = templatefile("compose.yaml.tftpl", {
      scaleway_access_key                 = var.scaleway_access_key
      scaleway_secret_key                 = var.scaleway_secret_key
      pangolin_pg_user                    = var.pangolin_pg_user
      pangolin_pg_password                = var.pangolin_pg_password
      crowdsec_bouncer_key                = var.crowdsec_bouncer_key
      crowdsec_firewall_bouncer_key       = var.crowdsec_firewall_bouncer_key
      crowdsec_webui_machine_password     = var.crowdsec_webui_machine_password
      crowdsec_blocklist_bouncer_key      = var.crowdsec_blocklist_bouncer_key
      crowdsec_blocklist_machine_password = var.crowdsec_blocklist_machine_password
    })
    pangolin_config = templatefile("config.yml.tftpl", {
      domain_name          = var.domain_name
      acme_email           = var.acme_email
      pangolin_secret      = var.pangolin_secret
      pangolin_pg_user     = var.pangolin_pg_user
      pangolin_pg_password = var.pangolin_pg_password
    })
    traefik_static_config = templatefile("traefik_config.yml.tftpl", {
      acme_email = var.acme_email
    })
    traefik_dynamic_config = templatefile("dynamic_config.yml.tftpl", {
      domain_name               = var.domain_name
      crowdsec_bouncer_key      = var.crowdsec_bouncer_key
      crowdsec_webui_basic_auth = var.crowdsec_webui_basic_auth
    })
    domain_name                         = var.domain_name
    username                            = var.username
    password_hash                       = var.password_hash
    ssh_public_keys                     = var.ssh_public_keys
    crowdsec_firewall_bouncer_key       = var.crowdsec_firewall_bouncer_key
    crowdsec_capi_whitelisted_cidrs     = var.crowdsec_capi_whitelisted_cidrs
    crowdsec_webui_machine_password     = var.crowdsec_webui_machine_password
    crowdsec_blocklist_machine_password = var.crowdsec_blocklist_machine_password
  })

  tags = var.tags

  root_volume {
    size_in_gb = var.root_volume_size
  }
}

resource "scaleway_object_bucket" "pangolin_backups" {
  name   = "${var.instance_name}-pangolin-backups"
  region = var.region

  lifecycle_rule {
    enabled = true

    expiration {
      days = var.pangolin_backup_retention_days
    }
  }

  tags = {
    managed-by = "terraform"
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
