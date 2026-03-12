# -----------------------------------------------------------------------------
# Compute Module — Outputs
# -----------------------------------------------------------------------------

# server-00
output "server_00_public_ip" {
  description = "Public IP of server-00 (K3s control plane)"
  value       = oci_core_instance.server_00.public_ip
}

output "server_00_private_ip" {
  description = "Private IP of server-00"
  value       = oci_core_instance.server_00.private_ip
}

output "server_00_id" {
  description = "OCID of server-00"
  value       = oci_core_instance.server_00.id
}

# agent-00
output "agent_00_public_ip" {
  description = "Public IP of agent-00 (K3s worker, ARM)"
  value       = oci_core_instance.agent_00.public_ip
}

output "agent_00_private_ip" {
  description = "Private IP of agent-00"
  value       = oci_core_instance.agent_00.private_ip
}

output "agent_00_id" {
  description = "OCID of agent-00"
  value       = oci_core_instance.agent_00.id
}

# agent-01
output "agent_01_public_ip" {
  description = "Public IP of agent-01 (K3s worker, IB Gateway)"
  value       = oci_core_instance.agent_01.public_ip
}

output "agent_01_private_ip" {
  description = "Private IP of agent-01"
  value       = oci_core_instance.agent_01.private_ip
}

output "agent_01_id" {
  description = "OCID of agent-01"
  value       = oci_core_instance.agent_01.id
}

# agent-02
output "agent_02_public_ip" {
  description = "Public IP of agent-02 (K3s worker, light)"
  value       = oci_core_instance.agent_02.public_ip
}

output "agent_02_private_ip" {
  description = "Private IP of agent-02"
  value       = oci_core_instance.agent_02.private_ip
}

output "agent_02_id" {
  description = "OCID of agent-02"
  value       = oci_core_instance.agent_02.id
}

# sentinel-00
output "sentinel_00_public_ip" {
  description = "Public IP of sentinel-00 (bastion/monitoring)"
  value       = oci_core_instance.sentinel_00.public_ip
}

output "sentinel_00_private_ip" {
  description = "Private IP of sentinel-00"
  value       = oci_core_instance.sentinel_00.private_ip
}

output "sentinel_00_id" {
  description = "OCID of sentinel-00"
  value       = oci_core_instance.sentinel_00.id
}

# sentinel-01
output "sentinel_01_public_ip" {
  description = "Public IP of sentinel-01 (backup bastion)"
  value       = oci_core_instance.sentinel_01.public_ip
}

output "sentinel_01_private_ip" {
  description = "Private IP of sentinel-01"
  value       = oci_core_instance.sentinel_01.private_ip
}

output "sentinel_01_id" {
  description = "OCID of sentinel-01"
  value       = oci_core_instance.sentinel_01.id
}
