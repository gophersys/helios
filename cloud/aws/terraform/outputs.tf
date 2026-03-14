# ── ARM Builder ───────────────────────────────────────────────────────────────

output "builder_instance_id" {
  description = "EC2 instance ID for the ARM builder"
  value       = aws_instance.arm_builder.id
}

output "builder_public_ip" {
  description = "Public IP of the ARM builder (changes on stop/start)"
  value       = aws_instance.arm_builder.public_ip
}

# ── K3s Agent ────────────────────────────────────────────────────────────────

output "agent_02_instance_id" {
  description = "EC2 instance ID for the K3s agent"
  value       = aws_instance.agent_02.id
}

output "agent_02_public_ip" {
  description = "Public IP of the K3s agent"
  value       = aws_instance.agent_02.public_ip
}

# ── Shared ───────────────────────────────────────────────────────────────────

output "security_group_id" {
  description = "Security group ID"
  value       = aws_security_group.arm_builder.id
}

output "builder_ami" {
  description = "AMI used for ARM instances"
  value       = data.aws_ami.ubuntu_arm64.id
}

output "aws_region" {
  description = "AWS region"
  value       = var.aws_region
}
