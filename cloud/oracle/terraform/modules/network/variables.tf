# -----------------------------------------------------------------------------
# Network Module — Variables
# -----------------------------------------------------------------------------

variable "compartment_ocid" {
  description = "OCID of the compartment where network resources are created"
  type        = string
}

variable "ssh_allowed_cidrs" {
  description = "CIDRs allowed to SSH into instances"
  type        = list(string)
}

variable "vcn_cidr" {
  description = "CIDR block for the VCN"
  type        = string
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidr" {
  description = "CIDR block for the public subnet"
  type        = string
  default     = "10.0.1.0/24"
}
