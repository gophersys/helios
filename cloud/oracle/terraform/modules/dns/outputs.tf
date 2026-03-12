# -----------------------------------------------------------------------------
# DNS Module — Outputs
# -----------------------------------------------------------------------------

# codectl.dev
output "codectl_apex_record_id" {
  description = "Cloudflare record ID for the codectl.dev apex A record"
  value       = cloudflare_dns_record.codectl_apex.id
}

output "codectl_wildcard_record_id" {
  description = "Cloudflare record ID for the *.codectl.dev wildcard A record"
  value       = cloudflare_dns_record.codectl_wildcard.id
}

output "codectl_apex_fqdn" {
  description = "Fully qualified domain name for codectl.dev apex"
  value       = var.domain_codectl
}

output "codectl_wildcard_fqdn" {
  description = "Fully qualified domain name for *.codectl.dev"
  value       = "*.${var.domain_codectl}"
}

# mateosegura.com
output "mateosegura_apex_record_id" {
  description = "Cloudflare record ID for the mateosegura.com apex A record"
  value       = cloudflare_dns_record.mateosegura_apex.id
}

output "mateosegura_wildcard_record_id" {
  description = "Cloudflare record ID for the *.mateosegura.com wildcard A record"
  value       = cloudflare_dns_record.mateosegura_wildcard.id
}

output "mateosegura_apex_fqdn" {
  description = "Fully qualified domain name for mateosegura.com apex"
  value       = var.domain_mateosegura
}

output "mateosegura_wildcard_fqdn" {
  description = "Fully qualified domain name for *.mateosegura.com"
  value       = "*.${var.domain_mateosegura}"
}
