# -----------------------------------------------------------------------------
# Input Variables
# -----------------------------------------------------------------------------
# All OCI and Cloudflare credentials can be supplied via TF_VAR_* env vars
# so devcontainer users don't need a separate .tfvars file.
#
# Example:  export TF_VAR_oci_tenancy_ocid="ocid1.tenancy.oc1..aaaa..."
# -----------------------------------------------------------------------------

# =============================================================================
# OCI Provider Credentials
# =============================================================================

variable "oci_tenancy_ocid" {
  description = "OCID of the OCI tenancy"
  type        = string
}

variable "oci_user_ocid" {
  description = "OCID of the OCI user for API authentication"
  type        = string
}

variable "oci_fingerprint" {
  description = "Fingerprint of the OCI API signing key"
  type        = string
}

variable "oci_private_key_path" {
  description = "Path to the OCI API signing private key PEM file"
  type        = string
}

variable "oci_region" {
  description = "OCI region identifier (e.g. us-phoenix-1, us-ashburn-1)"
  type        = string
}

variable "oci_compartment_ocid" {
  description = "OCID of the compartment where resources will be created"
  type        = string
}

# =============================================================================
# Availability Domains
# =============================================================================

variable "availability_domain_index" {
  description = "Default AD index (0-based) for A1.Flex and E4.Flex instances. Try 0, 1, 2 if capacity is exhausted."
  type        = number
  default     = 0
}

variable "micro_availability_domain_indexes" {
  description = "AD indexes for the three E2.1.Micro instances (agent-02, sentinel-00, sentinel-01). Spread across ADs to avoid Always Free limits per AD."
  type        = list(number)
  default     = [0, 1, 2]
}

# =============================================================================
# Cloudflare
# =============================================================================

variable "cloudflare_api_token" {
  description = "Cloudflare API token with DNS edit permissions for both zones"
  type        = string
  sensitive   = true
}

variable "cloudflare_zone_id_codectl" {
  description = "Cloudflare zone ID for codectl.dev"
  type        = string
}

variable "cloudflare_zone_id_mateosegura" {
  description = "Cloudflare zone ID for mateosegura.com"
  type        = string
}

# =============================================================================
# Tailscale
# =============================================================================

variable "tailscale_auth_key" {
  description = "Tailscale auth key (reusable, ephemeral) for node enrollment"
  type        = string
  sensitive   = true
}

# =============================================================================
# Domains
# =============================================================================

variable "domain_codectl" {
  description = "Primary domain for the cluster"
  type        = string
  default     = "codectl.dev"
}

variable "domain_mateosegura" {
  description = "Secondary domain for the cluster"
  type        = string
  default     = "mateosegura.com"
}

# =============================================================================
# SSH Access
# =============================================================================

variable "ssh_allowed_cidrs" {
  description = "CIDRs allowed to SSH into instances. Restrict to your IP in production."
  type        = list(string)
  default     = ["0.0.0.0/0"] # TODO: restrict to your IP, e.g. ["203.0.113.42/32"]
}

# =============================================================================
# Sizing — server-00 (A1.Flex ARM64, K3s server)
# =============================================================================

variable "server_00_ocpus" {
  description = "Number of OCPUs for server-00"
  type        = number
  default     = 2
}

variable "server_00_memory_gb" {
  description = "Memory in GB for server-00"
  type        = number
  default     = 12
}

variable "server_00_boot_volume_gb" {
  description = "Boot volume size in GB for server-00"
  type        = number
  default     = 50
}

# =============================================================================
# Sizing — agent-00 (A1.Flex ARM64, K3s agent)
# =============================================================================

variable "agent_00_ocpus" {
  description = "Number of OCPUs for agent-00"
  type        = number
  default     = 2
}

variable "agent_00_memory_gb" {
  description = "Memory in GB for agent-00"
  type        = number
  default     = 12
}

variable "agent_00_boot_volume_gb" {
  description = "Boot volume size in GB for agent-00"
  type        = number
  default     = 50
}

# =============================================================================
# Sizing — agent-01 (E4.Flex x86_64, IB Gateway)
# =============================================================================

variable "agent_01_ocpus" {
  description = "Number of OCPUs for agent-01"
  type        = number
  default     = 1
}

variable "agent_01_memory_gb" {
  description = "Memory in GB for agent-01"
  type        = number
  default     = 16
}

variable "agent_01_boot_volume_gb" {
  description = "Boot volume size in GB for agent-01"
  type        = number
  default     = 50
}

# =============================================================================
# Sizing — E2.1.Micro instances (agent-02, sentinel-00, sentinel-01)
# =============================================================================

variable "micro_boot_volume_gb" {
  description = "Boot volume size in GB for E2.1.Micro instances"
  type        = number
  default     = 50
}
