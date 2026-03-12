# -----------------------------------------------------------------------------
# Network Module — Outputs
# -----------------------------------------------------------------------------

output "vcn_id" {
  description = "OCID of the VCN"
  value       = oci_core_vcn.main.id
}

output "public_subnet_id" {
  description = "OCID of the public subnet"
  value       = oci_core_subnet.public.id
}

output "security_list_id" {
  description = "OCID of the public security list"
  value       = oci_core_security_list.public.id
}
