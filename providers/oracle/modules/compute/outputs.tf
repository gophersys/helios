#
# Compute-unit contract outputs. Every provider emits these.
# Implementation-specific: the protected/destroyable split means we
# pick the one that actually exists via try() / one().
#

locals {
  instance = one(concat(oci_core_instance.protected, oci_core_instance.destroyable))
  primary_vnic = try(
    data.oci_core_vnic.primary[0],
    null,
  )
  # Whether the caller enabled Tailscale — derived from a sensitive
  # input, but the boolean "did we configure tailnet" is itself not
  # sensitive. nonsensitive() strips the taint so outputs that only
  # depend on the BOOLEAN (never on the key itself) aren't marked
  # sensitive.
  tailnet_enabled = nonsensitive(var.tailnet_auth_key != "")
  tailnet_fqdn    = "${var.name}.mateosegura.ts.net"
}

output "id" {
  description = "OCID of the compute instance."
  value       = local.instance.id
}

output "private_ip" {
  description = "Primary VNIC private IP."
  value       = try(local.primary_vnic.private_ip_address, "")
}

output "public_ip" {
  description = "Primary VNIC public IP; empty string if none attached."
  value       = try(local.primary_vnic.public_ip_address, "")
}

output "tailnet_name" {
  description = "Tailscale hostname in mateosegura.ts.net if Tailscale was pre-authed on first boot; empty if var.tailnet_auth_key was empty."
  value       = local.tailnet_enabled ? local.tailnet_fqdn : ""
}

output "fqdn" {
  description = "Stable resolvable name. Prefers tailnet FQDN, falls back to OCI hostname_label-based DNS."
  value = coalesce(
    local.tailnet_enabled ? local.tailnet_fqdn : null,
    "${var.hostname_label != "" ? var.hostname_label : var.name}.subnet.vcn.oraclevcn.com",
  )
}

#
# Implementation-specific extras — not in the compute-unit contract
# but useful for debugging / cross-module reference.
#

output "shape" {
  description = "OCI shape (echo of var.shape)."
  value       = var.shape
}

output "availability_domain" {
  description = "OCI availability domain (echo of var.availability_domain)."
  value       = var.availability_domain
}
