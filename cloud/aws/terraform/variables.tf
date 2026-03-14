# ── AWS Provider ──────────────────────────────────────────────────────────────

variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-west-2"
}

# ── ARM Builder ──────────────────────────────────────────────────────────────

variable "builder_instance_type" {
  description = "EC2 instance type for ARM builder (must be ARM/Graviton)"
  type        = string
  default     = "t4g.small" # 2 vCPU, 2 GB — free tier through Dec 2026
}

variable "builder_volume_size_gb" {
  description = "Root EBS volume size in GB (persists Docker cache across stop/start)"
  type        = number
  default     = 50
}

variable "builder_ssh_public_key" {
  description = "SSH public key for builder access (content, not path)"
  type        = string
}

variable "ssh_allowed_cidrs" {
  description = "CIDRs allowed to SSH into instances (default: anywhere)"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

# ── K3s Agent Node ───────────────────────────────────────────────────────────

variable "agent_instance_type" {
  description = "EC2 instance type for always-on K3s agent (must be ARM/Graviton)"
  type        = string
  default     = "t4g.small" # 2 vCPU, 2 GB — shares 750 hrs/month free with builder
}

variable "agent_volume_size_gb" {
  description = "Root EBS volume size in GB for K3s agent"
  type        = number
  default     = 20
}

variable "tailscale_auth_key" {
  description = "Tailscale auth key for K3s agent to join the mesh network (reusable, ephemeral)"
  type        = string
  sensitive   = true
}

variable "k3s_server_url" {
  description = "K3s server URL for agent to join (e.g. https://<tailscale-ip>:6443)"
  type        = string
}

variable "k3s_token" {
  description = "K3s node join token (from /var/lib/rancher/k3s/server/node-token on server)"
  type        = string
  sensitive   = true
}
