# -----------------------------------------------------------------------------
# DNS Module — Variables
# -----------------------------------------------------------------------------

variable "cloudflare_zone_id_codectl" {
  description = "Cloudflare zone ID for codectl.dev"
  type        = string
}

variable "cloudflare_zone_id_mateosegura" {
  description = "Cloudflare zone ID for mateosegura.com"
  type        = string
}

variable "domain_codectl" {
  description = "Primary domain (e.g. codectl.dev)"
  type        = string
}

variable "domain_mateosegura" {
  description = "Secondary domain (e.g. mateosegura.com)"
  type        = string
}

variable "server_public_ip" {
  description = "Public IP of the K3s server to point DNS records at"
  type        = string
}
