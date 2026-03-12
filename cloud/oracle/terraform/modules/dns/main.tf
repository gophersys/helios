# -----------------------------------------------------------------------------
# DNS Module — Cloudflare DNS Records (Two Zones)
# -----------------------------------------------------------------------------
# Creates A records for both codectl.dev and mateosegura.com:
#   - Apex record (domain → server public IP)
#   - Wildcard record (*.domain → server public IP)
#
# Both are DNS-only (not proxied) so cert-manager can use DNS-01 challenges
# and direct TCP connections (K3s API, SSH) work without Cloudflare tunneling.
# -----------------------------------------------------------------------------

terraform {
  required_providers {
    cloudflare = {
      source = "cloudflare/cloudflare"
    }
  }
}

# =============================================================================
# codectl.dev — Apex + Wildcard
# =============================================================================

resource "cloudflare_dns_record" "codectl_apex" {
  zone_id = var.cloudflare_zone_id_codectl
  name    = var.domain_codectl
  content = var.server_public_ip
  type    = "A"
  ttl     = 300
  proxied = false
  comment = "K3s server — managed by Terraform"
}

resource "cloudflare_dns_record" "codectl_wildcard" {
  zone_id = var.cloudflare_zone_id_codectl
  name    = "*.${var.domain_codectl}"
  content = var.server_public_ip
  type    = "A"
  ttl     = 300
  proxied = false
  comment = "K3s wildcard ingress — managed by Terraform"
}

# =============================================================================
# mateosegura.com — Apex + Wildcard
# =============================================================================

resource "cloudflare_dns_record" "mateosegura_apex" {
  zone_id = var.cloudflare_zone_id_mateosegura
  name    = var.domain_mateosegura
  content = var.server_public_ip
  type    = "A"
  ttl     = 300
  proxied = false
  comment = "K3s server — managed by Terraform"
}

resource "cloudflare_dns_record" "mateosegura_wildcard" {
  zone_id = var.cloudflare_zone_id_mateosegura
  name    = "*.${var.domain_mateosegura}"
  content = var.server_public_ip
  type    = "A"
  ttl     = 300
  proxied = false
  comment = "K3s wildcard ingress — managed by Terraform"
}
