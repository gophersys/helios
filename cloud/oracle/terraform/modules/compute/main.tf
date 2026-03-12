# -----------------------------------------------------------------------------
# Compute Module — 6 OCI Instances for K3s Cluster
# -----------------------------------------------------------------------------
# - server-00:    A1.Flex    (ARM64)  — K3s control plane
# - agent-00:     A1.Flex    (ARM64)  — K3s worker
# - agent-01:     E4.Flex    (x86_64) — K3s worker (IB Gateway)
# - agent-02:     E2.1.Micro (x86_64) — K3s worker (light workloads)
# - sentinel-00:  E2.1.Micro (x86_64) — Bastion / monitoring (NOT in K3s)
# - sentinel-01:  E2.1.Micro (x86_64) — Backup bastion (NOT in K3s)
# -----------------------------------------------------------------------------

terraform {
  required_providers {
    oci = {
      source = "oracle/oci"
    }
  }
}

# =============================================================================
# Availability Domains
# =============================================================================
# A1.Flex and E4.Flex use the primary AD. E2.1.Micro instances are spread
# across multiple ADs to avoid Always Free per-AD limits.
# =============================================================================

data "oci_identity_availability_domains" "ads" {
  compartment_id = var.compartment_ocid
}

locals {
  # Primary AD for flex instances
  ad_name = data.oci_identity_availability_domains.ads.availability_domains[var.availability_domain_index].name

  # Per-micro-instance ADs (agent-02, sentinel-00, sentinel-01)
  micro_ad_names = [
    for idx in var.micro_availability_domain_indexes :
    data.oci_identity_availability_domains.ads.availability_domains[idx].name
  ]
}

# =============================================================================
# Image Data Sources — Auto-resolve Ubuntu 22.04 for each architecture
# =============================================================================
# No manual OCID lookup required. These data sources find the latest Canonical
# Ubuntu 22.04 image for the target CPU architecture.
# =============================================================================

# ARM64 image for A1.Flex instances (server-00, agent-00)
data "oci_core_images" "ubuntu_arm64" {
  compartment_id           = var.compartment_ocid
  operating_system         = "Canonical Ubuntu"
  operating_system_version = "22.04"
  shape                    = "VM.Standard.A1.Flex"
  sort_by                  = "TIMECREATED"
  sort_order               = "DESC"
}

# x86_64 image for E2.1.Micro instances (agent-02, sentinel-00, sentinel-01)
data "oci_core_images" "ubuntu_x86_micro" {
  compartment_id           = var.compartment_ocid
  operating_system         = "Canonical Ubuntu"
  operating_system_version = "22.04"
  shape                    = "VM.Standard.E2.1.Micro"
  sort_by                  = "TIMECREATED"
  sort_order               = "DESC"
}

# x86_64 image for E4.Flex instance (agent-01)
data "oci_core_images" "ubuntu_x86_e4" {
  compartment_id           = var.compartment_ocid
  operating_system         = "Canonical Ubuntu"
  operating_system_version = "22.04"
  shape                    = "VM.Standard.E4.Flex"
  sort_by                  = "TIMECREATED"
  sort_order               = "DESC"
}

locals {
  ubuntu_arm64_image_id    = data.oci_core_images.ubuntu_arm64.images[0].id
  ubuntu_x86_micro_image_id = data.oci_core_images.ubuntu_x86_micro.images[0].id
  ubuntu_x86_e4_image_id   = data.oci_core_images.ubuntu_x86_e4.images[0].id
}

# =============================================================================
# server-00 — K3s Control Plane (A1.Flex ARM64)
# =============================================================================

resource "oci_core_instance" "server_00" {
  compartment_id      = var.compartment_ocid
  availability_domain = local.ad_name
  display_name        = "server-00"
  shape               = "VM.Standard.A1.Flex"

  shape_config {
    ocpus         = var.server_00_ocpus
    memory_in_gbs = var.server_00_memory_gb
  }

  source_details {
    source_type             = "image"
    source_id               = local.ubuntu_arm64_image_id
    boot_volume_size_in_gbs = var.server_00_boot_volume_gb
  }

  create_vnic_details {
    subnet_id        = var.subnet_id
    assign_public_ip = true
    display_name     = "server-00-vnic"
    hostname_label   = "server-00"
  }

  metadata = {
    ssh_authorized_keys = var.ssh_public_key
    user_data = base64encode(templatefile(
      "${path.module}/cloud-init/k3s-common.yaml",
      { hostname = "server-00" }
    ))
  }

  freeform_tags = {
    project = "infrastructure"
    role    = "k3s-server"
    tier    = "free"
  }

  # ⚠️  ARM A1.Flex instances are IRREPLACEABLE on OCI free tier.
  # Capacity is nearly impossible to re-acquire once released.
  # NEVER remove prevent_destroy without explicit owner approval.
  lifecycle {
    prevent_destroy = true
  }
}

# =============================================================================
# agent-00 — K3s Worker (A1.Flex ARM64)
# =============================================================================

resource "oci_core_instance" "agent_00" {
  compartment_id      = var.compartment_ocid
  availability_domain = local.ad_name
  display_name        = "agent-00"
  shape               = "VM.Standard.A1.Flex"

  shape_config {
    ocpus         = var.agent_00_ocpus
    memory_in_gbs = var.agent_00_memory_gb
  }

  source_details {
    source_type             = "image"
    source_id               = local.ubuntu_arm64_image_id
    boot_volume_size_in_gbs = var.agent_00_boot_volume_gb
  }

  create_vnic_details {
    subnet_id        = var.subnet_id
    assign_public_ip = true
    display_name     = "agent-00-vnic"
    hostname_label   = "agent-00"
  }

  metadata = {
    ssh_authorized_keys = var.ssh_public_key
    user_data = base64encode(templatefile(
      "${path.module}/cloud-init/k3s-common.yaml",
      { hostname = "agent-00" }
    ))
  }

  freeform_tags = {
    project = "infrastructure"
    role    = "k3s-agent"
    tier    = "free"
  }

  # ⚠️  ARM A1.Flex instances are IRREPLACEABLE on OCI free tier.
  # Capacity is nearly impossible to re-acquire once released.
  # NEVER remove prevent_destroy without explicit owner approval.
  lifecycle {
    prevent_destroy = true
  }
}

# =============================================================================
# agent-01 — K3s Worker / IB Gateway (E4.Flex x86_64, PAID)
# =============================================================================

resource "oci_core_instance" "agent_01" {
  compartment_id      = var.compartment_ocid
  availability_domain = local.ad_name
  display_name        = "agent-01"
  shape               = "VM.Standard.E4.Flex"

  shape_config {
    ocpus         = var.agent_01_ocpus
    memory_in_gbs = var.agent_01_memory_gb
  }

  source_details {
    source_type             = "image"
    source_id               = local.ubuntu_x86_e4_image_id
    boot_volume_size_in_gbs = var.agent_01_boot_volume_gb
  }

  create_vnic_details {
    subnet_id        = var.subnet_id
    assign_public_ip = true
    display_name     = "agent-01-vnic"
    hostname_label   = "agent-01"
  }

  metadata = {
    ssh_authorized_keys = var.ssh_public_key
    user_data = base64encode(templatefile(
      "${path.module}/cloud-init/k3s-common.yaml",
      { hostname = "agent-01" }
    ))
  }

  freeform_tags = {
    project = "infrastructure"
    role    = "k3s-agent"
    tier    = "paid"
  }

  lifecycle {
    create_before_destroy = true
  }
}

# =============================================================================
# agent-02 — K3s Worker / Light Workloads (E2.1.Micro x86_64)
# =============================================================================

resource "oci_core_instance" "agent_02" {
  compartment_id      = var.compartment_ocid
  availability_domain = local.micro_ad_names[0]
  display_name        = "agent-02"
  shape               = "VM.Standard.E2.1.Micro"

  source_details {
    source_type             = "image"
    source_id               = local.ubuntu_x86_micro_image_id
    boot_volume_size_in_gbs = var.micro_boot_volume_gb
  }

  create_vnic_details {
    subnet_id        = var.subnet_id
    assign_public_ip = true
    display_name     = "agent-02-vnic"
    hostname_label   = "agent-02"
  }

  metadata = {
    ssh_authorized_keys = var.ssh_public_key
    user_data = base64encode(templatefile(
      "${path.module}/cloud-init/k3s-common.yaml",
      { hostname = "agent-02" }
    ))
  }

  freeform_tags = {
    project = "infrastructure"
    role    = "k3s-agent"
    tier    = "free"
  }

  lifecycle {
    create_before_destroy = true
  }
}

# =============================================================================
# sentinel-00 — Bastion / Monitoring (E2.1.Micro x86_64, NOT in K3s)
# =============================================================================

resource "oci_core_instance" "sentinel_00" {
  compartment_id      = var.compartment_ocid
  availability_domain = local.micro_ad_names[1]
  display_name        = "sentinel-00"
  shape               = "VM.Standard.E2.1.Micro"

  source_details {
    source_type             = "image"
    source_id               = local.ubuntu_x86_micro_image_id
    boot_volume_size_in_gbs = var.micro_boot_volume_gb
  }

  create_vnic_details {
    subnet_id        = var.subnet_id
    assign_public_ip = true
    display_name     = "sentinel-00-vnic"
    hostname_label   = "sentinel-00"
  }

  metadata = {
    ssh_authorized_keys = var.ssh_public_key
    user_data = base64encode(templatefile(
      "${path.module}/cloud-init/k3s-common.yaml",
      { hostname = "sentinel-00" }
    ))
  }

  freeform_tags = {
    project = "infrastructure"
    role    = "sentinel"
    tier    = "free"
  }

  lifecycle {
    create_before_destroy = true
  }
}

# =============================================================================
# sentinel-01 — Backup Bastion (E2.1.Micro x86_64, NOT in K3s)
# =============================================================================

resource "oci_core_instance" "sentinel_01" {
  compartment_id      = var.compartment_ocid
  availability_domain = local.micro_ad_names[2]
  display_name        = "sentinel-01"
  shape               = "VM.Standard.E2.1.Micro"

  source_details {
    source_type             = "image"
    source_id               = local.ubuntu_x86_micro_image_id
    boot_volume_size_in_gbs = var.micro_boot_volume_gb
  }

  create_vnic_details {
    subnet_id        = var.subnet_id
    assign_public_ip = true
    display_name     = "sentinel-01-vnic"
    hostname_label   = "sentinel-01"
  }

  metadata = {
    ssh_authorized_keys = var.ssh_public_key
    user_data = base64encode(templatefile(
      "${path.module}/cloud-init/k3s-common.yaml",
      { hostname = "sentinel-01" }
    ))
  }

  freeform_tags = {
    project = "infrastructure"
    role    = "sentinel"
    tier    = "free"
  }

  lifecycle {
    create_before_destroy = true
  }
}
