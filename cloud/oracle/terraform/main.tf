# -----------------------------------------------------------------------------
# Main Configuration — OCI K3s Cluster (6 Nodes)
# -----------------------------------------------------------------------------
# Provisions: VCN + subnet, 6 compute instances, Cloudflare DNS (2 zones),
# SSH key pair, and an Ansible inventory file for downstream config mgmt.
#
# Nodes:
#   server-00    A1.Flex  (ARM64)     K3s control plane
#   agent-00     A1.Flex  (ARM64)     K3s worker
#   agent-01     E4.Flex  (x86_64)    K3s worker (IB Gateway)
#   agent-02     E2.1.Micro (x86_64)  K3s worker (light workloads)
#   sentinel-00  E2.1.Micro (x86_64)  Bastion / monitoring
#   sentinel-01  E2.1.Micro (x86_64)  Backup bastion
# -----------------------------------------------------------------------------

# =============================================================================
# Providers
# =============================================================================

provider "oci" {
  tenancy_ocid     = var.oci_tenancy_ocid
  user_ocid        = var.oci_user_ocid
  fingerprint      = var.oci_fingerprint
  private_key_path = var.oci_private_key_path
  region           = var.oci_region
}

provider "cloudflare" {
  api_token = var.cloudflare_api_token
}

# =============================================================================
# SSH Key Pair
# =============================================================================
# Generated once by Terraform and written to a local file. The public key is
# injected into all instances via cloud-init metadata.
# =============================================================================

resource "tls_private_key" "ssh" {
  algorithm = "ED25519"
}

resource "local_sensitive_file" "ssh_private_key" {
  content         = tls_private_key.ssh.private_key_openssh
  filename        = "${path.module}/cluster-key.pem"
  file_permission = "0600"
}

resource "local_file" "ssh_public_key" {
  content         = tls_private_key.ssh.public_key_openssh
  filename        = "${path.module}/cluster-key.pub"
  file_permission = "0644"
}

# =============================================================================
# Modules
# =============================================================================

module "network" {
  source = "./modules/network"

  compartment_ocid  = var.oci_compartment_ocid
  ssh_allowed_cidrs = var.ssh_allowed_cidrs
}

module "compute" {
  source = "./modules/compute"

  compartment_ocid          = var.oci_compartment_ocid
  subnet_id                 = module.network.public_subnet_id
  ssh_public_key            = tls_private_key.ssh.public_key_openssh
  tailscale_auth_key        = var.tailscale_auth_key
  availability_domain_index = var.availability_domain_index

  # E2.1.Micro AD spread (one per micro instance)
  micro_availability_domain_indexes = var.micro_availability_domain_indexes

  # server-00 sizing
  server_00_ocpus          = var.server_00_ocpus
  server_00_memory_gb      = var.server_00_memory_gb
  server_00_boot_volume_gb = var.server_00_boot_volume_gb

  # agent-00 sizing
  agent_00_ocpus          = var.agent_00_ocpus
  agent_00_memory_gb      = var.agent_00_memory_gb
  agent_00_boot_volume_gb = var.agent_00_boot_volume_gb

  # agent-01 sizing (E4.Flex)
  agent_01_ocpus          = var.agent_01_ocpus
  agent_01_memory_gb      = var.agent_01_memory_gb
  agent_01_boot_volume_gb = var.agent_01_boot_volume_gb

  # E2.1.Micro sizing (shared)
  micro_boot_volume_gb = var.micro_boot_volume_gb
}

module "dns" {
  source = "./modules/dns"

  cloudflare_zone_id_codectl    = var.cloudflare_zone_id_codectl
  cloudflare_zone_id_mateosegura = var.cloudflare_zone_id_mateosegura
  domain_codectl                = var.domain_codectl
  domain_mateosegura            = var.domain_mateosegura
  server_public_ip              = module.compute.server_00_public_ip
}

# =============================================================================
# Ansible Inventory Generation
# =============================================================================
# Writes a JSON inventory file consumable by ansible-inventory --list.
# Groups map to K3s roles for the Ansible playbooks that follow Terraform.
# =============================================================================

resource "local_file" "ansible_inventory" {
  filename        = "${path.module}/../ansible/inventory/terraform_inventory.json"
  file_permission = "0644"
  content = jsonencode({
    all = {
      children = ["servers", "agents", "sentinels"]
    }
    servers = {
      hosts = {
        "server-00" = {
          ansible_host = module.compute.server_00_public_ip
          ansible_user = "ubuntu"
          private_ip   = module.compute.server_00_private_ip
          k3s_role     = "server"
          tailscale    = true
        }
      }
    }
    agents = {
      hosts = {
        "agent-00" = {
          ansible_host = module.compute.agent_00_public_ip
          ansible_user = "ubuntu"
          private_ip   = module.compute.agent_00_private_ip
          k3s_role     = "agent"
          tailscale    = true
        }
        "agent-01" = {
          ansible_host = module.compute.agent_01_public_ip
          ansible_user = "ubuntu"
          private_ip   = module.compute.agent_01_private_ip
          k3s_role     = "agent"
          tailscale    = true
        }
        "agent-02" = {
          ansible_host = module.compute.agent_02_public_ip
          ansible_user = "ubuntu"
          private_ip   = module.compute.agent_02_private_ip
          k3s_role     = "agent"
          tailscale    = true
        }
      }
    }
    sentinels = {
      hosts = {
        "sentinel-00" = {
          ansible_host = module.compute.sentinel_00_public_ip
          ansible_user = "ubuntu"
          private_ip   = module.compute.sentinel_00_private_ip
          k3s_role     = "none"
          tailscale    = true
        }
        "sentinel-01" = {
          ansible_host = module.compute.sentinel_01_public_ip
          ansible_user = "ubuntu"
          private_ip   = module.compute.sentinel_01_private_ip
          k3s_role     = "none"
          tailscale    = false
        }
      }
    }

    _meta = {
      hostvars = {}
    }
  })
}
