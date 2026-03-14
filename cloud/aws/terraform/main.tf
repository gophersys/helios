# ─────────────────────────────────────────────────────────────────────────────
# AWS Infrastructure
#
# Two resources, both t4g.small (Graviton2 ARM), sharing 750 hrs/month free:
#
#   1. arm-builder  — On-demand Docker builder (stop/start, ~10 hrs/month)
#   2. agent-02     — Always-on K3s agent node  (~730 hrs/month)
#                     Total: ~740 hrs/month < 750 free cap
#
# The builder is a standalone Docker host accessed via SSH.
# The agent joins the K3s cluster over Tailscale (same mesh as OCI nodes).
#
# Free tier: t4g.small is free for 750 hrs/month through December 2026.
# After that: ~$12/mo each at on-demand rates, or stop the agent.
#
# Monthly cost (while on free tier):
#   Compute: $0 (750 hrs shared between builder + agent)
#   EBS:     ~$5.60 (50 GB builder + 20 GB agent @ gp3)
#   IPv4:    ~$7.30 (2 public IPs @ $3.65/mo each)
#   Total:   ~$13/mo
# ─────────────────────────────────────────────────────────────────────────────

provider "aws" {
  region = var.aws_region
}

# ── Data Sources ─────────────────────────────────────────────────────────────

# Latest Ubuntu 24.04 ARM64 AMI
data "aws_ami" "ubuntu_arm64" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-arm64-server-*"]
  }

  filter {
    name   = "architecture"
    values = ["arm64"]
  }

  filter {
    name   = "state"
    values = ["available"]
  }
}

# Default VPC (every AWS account has one)
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# ── Security Group ───────────────────────────────────────────────────────────

resource "aws_security_group" "arm_builder" {
  name        = "arm-builder"
  description = "On-demand ARM builder — SSH access for Docker builds"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = var.ssh_allowed_cidrs
  }

  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name      = "arm-builder"
    ManagedBy = "terraform"
  }
}

# ── SSH Key Pair ─────────────────────────────────────────────────────────────

resource "aws_key_pair" "arm_builder" {
  key_name   = "arm-builder"
  public_key = var.builder_ssh_public_key

  tags = {
    Name      = "arm-builder"
    ManagedBy = "terraform"
  }
}

# ── Cloud-Init User Data ─────────────────────────────────────────────────────

locals {
  user_data = <<-USERDATA
    #!/bin/bash
    set -euo pipefail

    # Install Docker
    apt-get update -qq
    apt-get install -y -qq docker.io > /dev/null 2>&1
    usermod -aG docker ubuntu
    systemctl enable docker
    systemctl start docker

    # Install BuildKit
    BUILDKIT_VERSION="v0.21.1"
    curl -sSL "https://github.com/moby/buildkit/releases/download/$${BUILDKIT_VERSION}/buildkit-$${BUILDKIT_VERSION}.linux-arm64.tar.gz" \
        | tar -xz -C /usr/local/
    mkdir -p /run/buildkit /etc/buildkit

    # BuildKit config
    cat > /etc/buildkit/buildkitd.toml <<'BK'
    [worker.oci]
      enabled = true
      gc = true
      gckeepbytes = 5000000000
    [worker.containerd]
      enabled = false
    BK

    # BuildKit systemd service
    cat > /etc/systemd/system/buildkit.service <<'BKS'
    [Unit]
    Description=BuildKit daemon
    After=network.target docker.service
    [Service]
    ExecStart=/usr/local/bin/buildkitd \
        --addr tcp://0.0.0.0:9999 \
        --addr unix:///run/buildkit/buildkitd.sock \
        --config /etc/buildkit/buildkitd.toml
    Restart=always
    RestartSec=5
    [Install]
    WantedBy=multi-user.target
    BKS

    systemctl daemon-reload
    systemctl enable buildkit
    systemctl start buildkit

    # Idle shutdown — stops instance after 10 min of inactivity
    cat > /usr/local/bin/idle-shutdown.sh <<'IDLE'
    #!/usr/bin/env bash
    set -euo pipefail
    IDLE_LIMIT=600
    if who | grep -q .; then touch /tmp/idle-check; exit 0; fi
    if docker ps -q 2>/dev/null | grep -q .; then touch /tmp/idle-check; exit 0; fi
    [ ! -f /tmp/idle-check ] && { touch /tmp/idle-check; exit 0; }
    IDLE_SINCE=$(stat -c %Y /tmp/idle-check)
    NOW=$(date +%s)
    IDLE_SECS=$((NOW - IDLE_SINCE))
    if [ $${IDLE_SECS} -ge $${IDLE_LIMIT} ]; then
        logger -t idle-shutdown "Idle for $${IDLE_SECS}s. Stopping."
        shutdown -h now
    fi
    IDLE
    chmod +x /usr/local/bin/idle-shutdown.sh
    echo "* * * * * root /usr/local/bin/idle-shutdown.sh" > /etc/cron.d/idle-shutdown

    touch /tmp/idle-check
    touch /run/builder-ready
  USERDATA
}

# ── EC2 Instance ─────────────────────────────────────────────────────────────

resource "aws_instance" "arm_builder" {
  ami                         = data.aws_ami.ubuntu_arm64.id
  instance_type               = var.builder_instance_type
  key_name                    = aws_key_pair.arm_builder.key_name
  vpc_security_group_ids      = [aws_security_group.arm_builder.id]
  subnet_id                   = data.aws_subnets.default.ids[0]
  associate_public_ip_address = true
  user_data                   = local.user_data

  root_block_device {
    volume_size           = var.builder_volume_size_gb
    volume_type           = "gp3"
    delete_on_termination = false # Docker cache survives instance termination
    tags = {
      Name      = "arm-builder-root"
      ManagedBy = "terraform"
    }
  }

  tags = {
    Name      = "arm-builder"
    ManagedBy = "terraform"
    Role      = "docker-builder"
    AutoStop  = "true"
  }

  # The builder is designed to be stopped/started. Don't recreate on AMI change.
  lifecycle {
    ignore_changes = [ami, user_data]
  }
}

# ─────────────────────────────────────────────────────────────────────────────
# K3s Agent Node — always-on worker that joins the cluster over Tailscale
#
# Shares the t4g.small free tier with the builder. The builder uses ~10 hrs/mo,
# leaving ~740 hrs for this node (730 needed for 24/7 in a 30-day month).
#
# Cloud-init installs Tailscale + K3s agent. Once provisioned, the node appears
# in `kubectl get nodes` alongside the OCI nodes — same certs, same DNS, same
# service mesh, fully transparent.
# ─────────────────────────────────────────────────────────────────────────────

locals {
  agent_user_data = <<-USERDATA
    #!/bin/bash
    set -euo pipefail
    export DEBIAN_FRONTEND=noninteractive

    # ── Base packages ──────────────────────────────────────────────────────
    apt-get update -qq
    apt-get install -y -qq curl ca-certificates jq fail2ban \
        open-iscsi nfs-common apparmor apparmor-utils > /dev/null 2>&1

    # ── Kernel modules for K3s ─────────────────────────────────────────────
    cat > /etc/modules-load.d/k3s.conf <<MOD
    br_netfilter
    overlay
    iscsi_tcp
    MOD
    modprobe br_netfilter && modprobe overlay && modprobe iscsi_tcp

    # ── Sysctl for container networking ────────────────────────────────────
    cat > /etc/sysctl.d/99-k3s.conf <<SYSCTL
    net.bridge.bridge-nf-call-iptables  = 1
    net.bridge.bridge-nf-call-ip6tables = 1
    net.ipv4.ip_forward = 1
    fs.inotify.max_user_instances = 512
    fs.inotify.max_user_watches   = 524288
    SYSCTL
    sysctl --system > /dev/null 2>&1

    # ── Tailscale ──────────────────────────────────────────────────────────
    curl -fsSL https://tailscale.com/install.sh | sh
    tailscale up --auth-key="${var.tailscale_auth_key}" --hostname=agent-02

    # Wait for Tailscale to get an IP
    for i in $(seq 1 30); do
      TAILSCALE_IP=$(tailscale ip -4 2>/dev/null || true)
      [ -n "$TAILSCALE_IP" ] && break
      sleep 2
    done

    # ── K3s Agent ──────────────────────────────────────────────────────────
    curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION="v1.32.4+k3s1" sh -s - agent \
        --server "${var.k3s_server_url}" \
        --token "${var.k3s_token}" \
        --node-name agent-02 \
        --node-ip "$TAILSCALE_IP" \
        --flannel-iface tailscale0

    # ── Services ───────────────────────────────────────────────────────────
    systemctl enable fail2ban && systemctl start fail2ban
    systemctl enable iscsid && systemctl start iscsid

    hostnamectl set-hostname agent-02
  USERDATA
}

resource "aws_instance" "agent_02" {
  ami                         = data.aws_ami.ubuntu_arm64.id
  instance_type               = var.agent_instance_type
  key_name                    = aws_key_pair.arm_builder.key_name # reuse same key
  vpc_security_group_ids      = [aws_security_group.arm_builder.id]
  subnet_id                   = data.aws_subnets.default.ids[0]
  associate_public_ip_address = true
  user_data                   = local.agent_user_data

  root_block_device {
    volume_size           = var.agent_volume_size_gb
    volume_type           = "gp3"
    delete_on_termination = false
    tags = {
      Name      = "agent-02-root"
      ManagedBy = "terraform"
    }
  }

  tags = {
    Name      = "agent-02"
    ManagedBy = "terraform"
    Role      = "k3s-agent"
  }

  lifecycle {
    ignore_changes = [ami, user_data]
  }
}
