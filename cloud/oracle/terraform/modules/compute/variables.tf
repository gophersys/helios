# -----------------------------------------------------------------------------
# Compute Module — Variables
# -----------------------------------------------------------------------------

variable "availability_domain_index" {
  description = "AD index for A1.Flex and E4.Flex instances (0-based). Try 0, 1, 2 if capacity is exhausted."
  type        = number
  default     = 0
}

variable "micro_availability_domain_indexes" {
  description = "AD indexes for the three E2.1.Micro instances. Spread across ADs to avoid Always Free limits."
  type        = list(number)
  default     = [0, 1, 2]

  validation {
    condition     = length(var.micro_availability_domain_indexes) == 3
    error_message = "Exactly 3 AD indexes required (agent-02, sentinel-00, sentinel-01)."
  }
}

variable "compartment_ocid" {
  description = "OCID of the compartment where instances are created"
  type        = string
}

variable "subnet_id" {
  description = "OCID of the subnet to attach instances to"
  type        = string
}

variable "ssh_public_key" {
  description = "SSH public key to inject into instances"
  type        = string
}

variable "tailscale_auth_key" {
  description = "Tailscale auth key for node enrollment"
  type        = string
  sensitive   = true
}

# =============================================================================
# server-00 Sizing (A1.Flex ARM64)
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
# agent-00 Sizing (A1.Flex ARM64)
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
# agent-01 Sizing (E4.Flex x86_64)
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
# E2.1.Micro Sizing (shared for agent-02, sentinel-00, sentinel-01)
# =============================================================================

variable "micro_boot_volume_gb" {
  description = "Boot volume size in GB for E2.1.Micro instances"
  type        = number
  default     = 50
}
