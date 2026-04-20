#
# Compute-unit contract — every variable below matches the v1 contract
# at providers/compute-unit/contract.yaml. See that file for semantics.
#

variable "name" {
  description = "Unique human-readable instance name (kebab-case, 1-30 chars)."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{0,29}$", var.name))
    error_message = "name must be kebab-case, 1-30 chars, starting with a lowercase letter."
  }
}

variable "arch" {
  description = "CPU architecture. One of: amd64, arm64."
  type        = string

  validation {
    condition     = contains(["amd64", "arm64"], var.arch)
    error_message = "arch must be amd64 or arm64."
  }
}

variable "cpu_count" {
  description = "Integer vCPU count."
  type        = number

  validation {
    condition     = var.cpu_count >= 1 && floor(var.cpu_count) == var.cpu_count
    error_message = "cpu_count must be an integer >= 1."
  }
}

variable "memory_gb" {
  description = "GB of RAM."
  type        = number

  validation {
    condition     = var.memory_gb >= 1
    error_message = "memory_gb must be >= 1."
  }
}

variable "disk_gb" {
  description = "Root disk size in GB."
  type        = number

  validation {
    condition     = var.disk_gb >= 47
    error_message = "disk_gb must be >= 47 (OCI boot volume minimum)."
  }
}

variable "storage_class" {
  description = "ssd | nvme | hdd. OCI provides no user-selectable storage class — value is accepted but effectively a no-op."
  type        = string
  default     = "ssd"
}

variable "network" {
  description = "public | tailnet | private. Controls assign_public_ip + subnet choice."
  type        = string
  default     = "tailnet"

  validation {
    condition     = contains(["public", "tailnet", "private"], var.network)
    error_message = "network must be public, tailnet, or private."
  }
}

variable "os" {
  description = "linux-ubuntu | linux-debian | linux-fedora | windows-server — maps to an OCI image via var.image_ocid."
  type        = string
  default     = "linux-ubuntu"
}

variable "role" {
  description = "cluster | service | builder (or project-specific)."
  type        = string
  default     = "cluster"
}

variable "tags" {
  description = "Free-form key/value tags applied as OCI freeform_tags."
  type        = map(string)
  default     = {}
}

variable "tailnet_auth_key" {
  description = "Pre-auth key for on-boot Tailscale join. Empty string disables. Injected into cloud-init user_data."
  type        = string
  sensitive   = true
  default     = ""
}

variable "ssh_public_key" {
  description = "Public key seeded into cloud-init authorized_keys. Ignored for imported instances (see lifecycle.ignore_changes)."
  type        = string
  default     = ""
}

#
# OCI-specific extensions. These don't appear in the compute-unit
# contract because they are provider-scoped.
#

variable "compartment_ocid" {
  description = "OCI compartment OCID where the instance lives."
  type        = string
}

variable "availability_domain" {
  description = "OCI availability domain, e.g. 'FEQI:PHX-AD-1'."
  type        = string
}

variable "subnet_ocid" {
  description = "OCI subnet OCID the primary VNIC attaches to."
  type        = string
}

variable "shape" {
  description = "OCI instance shape, e.g. 'VM.Standard.A1.Flex' or 'VM.Standard.E2.1.Micro'."
  type        = string
}

variable "image_ocid" {
  description = "OCI image OCID used at provision. Ignored for imported instances (see lifecycle.ignore_changes)."
  type        = string
  default     = ""
}

variable "prevent_destroy" {
  description = "When true, terraform's lifecycle block refuses to destroy the resource — intended for irreplaceable A1.Flex free-tier nodes. Cannot be toggled after creation (lifecycle meta is static)."
  type        = bool
  default     = false
}

variable "assign_public_ip" {
  description = "Whether to attach a public IP to the primary VNIC. Defaults based on var.network if unset."
  type        = bool
  default     = null
}

variable "hostname_label" {
  description = "OCI DNS label (<= 20 chars, alphanumeric + hyphen). Defaults to var.name truncated. Imported instances often have the label already set."
  type        = string
  default     = ""
}
