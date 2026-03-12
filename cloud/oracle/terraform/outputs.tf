# -----------------------------------------------------------------------------
# Root Outputs
# -----------------------------------------------------------------------------

# =============================================================================
# SSH
# =============================================================================

output "ssh_private_key_path" {
  description = "Path to the generated SSH private key"
  value       = local_sensitive_file.ssh_private_key.filename
}

output "ssh_public_key_path" {
  description = "Path to the generated SSH public key"
  value       = local_file.ssh_public_key.filename
}

# =============================================================================
# Compute — Public IPs
# =============================================================================

output "server_00_public_ip" {
  description = "Public IP of server-00 (K3s control plane)"
  value       = module.compute.server_00_public_ip
}

output "agent_00_public_ip" {
  description = "Public IP of agent-00 (K3s worker, ARM)"
  value       = module.compute.agent_00_public_ip
}

output "agent_01_public_ip" {
  description = "Public IP of agent-01 (K3s worker, IB Gateway)"
  value       = module.compute.agent_01_public_ip
}

output "agent_02_public_ip" {
  description = "Public IP of agent-02 (K3s worker, light)"
  value       = module.compute.agent_02_public_ip
}

output "sentinel_00_public_ip" {
  description = "Public IP of sentinel-00 (bastion/monitoring)"
  value       = module.compute.sentinel_00_public_ip
}

output "sentinel_01_public_ip" {
  description = "Public IP of sentinel-01 (backup bastion)"
  value       = module.compute.sentinel_01_public_ip
}

# =============================================================================
# Network
# =============================================================================

output "vcn_id" {
  description = "OCID of the VCN"
  value       = module.network.vcn_id
}

output "public_subnet_id" {
  description = "OCID of the public subnet"
  value       = module.network.public_subnet_id
}

# =============================================================================
# DNS
# =============================================================================

output "dns_codectl_apex_fqdn" {
  description = "Apex FQDN for codectl.dev"
  value       = module.dns.codectl_apex_fqdn
}

output "dns_mateosegura_apex_fqdn" {
  description = "Apex FQDN for mateosegura.com"
  value       = module.dns.mateosegura_apex_fqdn
}

# =============================================================================
# Inventory
# =============================================================================

output "ansible_inventory_path" {
  description = "Path to the generated Ansible inventory file"
  value       = local_file.ansible_inventory.filename
}
