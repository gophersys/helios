#
# providers/oracle/modules/compute/main.tf
#
# One OCI VM instance that fulfills the compute-unit contract.
#
# Implementation notes:
#   - Two resource blocks ("protected" / "destroyable") are count-guarded
#     by var.prevent_destroy. Terraform's `lifecycle { prevent_destroy
#     = true }` meta-argument cannot be set dynamically, so the module
#     duplicates the block to expose the flag to callers. Irreplaceable
#     A1.Flex free-tier nodes set var.prevent_destroy = true; everything
#     else leaves it false (default).
#   - ignore_changes covers every field that is provision-time-only
#     (image, metadata, VNIC hostname) so an `import` of a pre-existing
#     instance reaches zero-diff without forcing us to know the exact
#     original provision inputs.
#

locals {
  # Resolve assign_public_ip: if caller passed null, derive from network.
  # "public"  → true  (expose to internet)
  # "tailnet" → true  (need WAN egress to reach Tailscale control + peers)
  # "private" → false (subnet-only)
  # Callers can override by setting the variable explicitly.
  assign_public_ip_effective = (
    var.assign_public_ip != null ? var.assign_public_ip :
    var.network == "private" ? false : true
  )

  hostname_label_effective = (
    var.hostname_label != "" ? var.hostname_label :
    substr(replace(var.name, "_", "-"), 0, 20)
  )

  # OCI flex shapes (A1.Flex, E4.Flex, E5.Flex, etc.) require a
  # shape_config with explicit ocpu + memory. Non-flex shapes
  # (E2.1.Micro, etc.) must NOT carry shape_config.
  is_flex_shape = can(regex("\\.Flex$", var.shape))

  freeform_tags = merge(
    var.tags,
    {
      "gophersys:role"         = var.role
      "gophersys:arch"         = var.arch
      "gophersys:network"      = var.network
      "gophersys:os"           = var.os
      "gophersys:managed-by"   = "terraform"
      "gophersys:compute-unit" = "v1"
    },
  )

  # cloud-init user_data payload. Runs Tailscale bootstrap if an auth
  # key is supplied, and seeds authorized_keys if a public key was
  # passed. Both are no-ops for imported pre-existing instances (see
  # lifecycle.ignore_changes below — metadata is frozen after import).
  user_data_rendered = base64encode(templatefile(
    "${path.module}/cloud-init.yaml.tmpl",
    {
      tailnet_auth_key = var.tailnet_auth_key
      ssh_public_key   = var.ssh_public_key
      hostname         = var.name
    },
  ))
}

#
# Protected variant — prevent_destroy = true. Used for A1.Flex.
# count is 1 iff var.prevent_destroy.
#
resource "oci_core_instance" "protected" {
  count = var.prevent_destroy ? 1 : 0

  compartment_id      = var.compartment_ocid
  availability_domain = var.availability_domain
  display_name        = var.name
  shape               = var.shape

  dynamic "shape_config" {
    for_each = local.is_flex_shape ? [1] : []
    content {
      ocpus         = var.cpu_count
      memory_in_gbs = var.memory_gb
    }
  }

  create_vnic_details {
    subnet_id        = var.subnet_ocid
    assign_public_ip = local.assign_public_ip_effective
    hostname_label   = local.hostname_label_effective
    display_name     = "${var.name}-primary-vnic"
  }

  source_details {
    source_type             = "image"
    source_id               = var.image_ocid
    boot_volume_size_in_gbs = var.disk_gb
  }

  metadata = {
    ssh_authorized_keys = var.ssh_public_key
    user_data           = local.user_data_rendered
  }

  freeform_tags = local.freeform_tags

  lifecycle {
    prevent_destroy = true

    # Imported-instance tolerance: these fields are known-after-provision
    # and typically diverge from the module's inputs. We accept whatever
    # the live instance already has.
    ignore_changes = [
      source_details,
      metadata,
      create_vnic_details[0].hostname_label,
      create_vnic_details[0].display_name,
      defined_tags,
      freeform_tags,
    ]
  }
}

#
# Destroyable variant — no prevent_destroy. Used for everything not
# irreplaceable (E4.Flex, E2.1.Micro, etc.). count is 1 iff NOT
# var.prevent_destroy.
#
resource "oci_core_instance" "destroyable" {
  count = var.prevent_destroy ? 0 : 1

  compartment_id      = var.compartment_ocid
  availability_domain = var.availability_domain
  display_name        = var.name
  shape               = var.shape

  dynamic "shape_config" {
    for_each = local.is_flex_shape ? [1] : []
    content {
      ocpus         = var.cpu_count
      memory_in_gbs = var.memory_gb
    }
  }

  create_vnic_details {
    subnet_id        = var.subnet_ocid
    assign_public_ip = local.assign_public_ip_effective
    hostname_label   = local.hostname_label_effective
    display_name     = "${var.name}-primary-vnic"
  }

  source_details {
    source_type             = "image"
    source_id               = var.image_ocid
    boot_volume_size_in_gbs = var.disk_gb
  }

  metadata = {
    ssh_authorized_keys = var.ssh_public_key
    user_data           = local.user_data_rendered
  }

  freeform_tags = local.freeform_tags

  lifecycle {
    ignore_changes = [
      source_details,
      metadata,
      create_vnic_details[0].hostname_label,
      create_vnic_details[0].display_name,
      defined_tags,
      freeform_tags,
    ]
  }
}

#
# Primary VNIC data source — looked up via vnic_attachments so outputs
# can surface private_ip and public_ip uniformly across protected /
# destroyable variants.
#

data "oci_core_vnic_attachments" "primary" {
  compartment_id = var.compartment_ocid
  instance_id    = local.instance.id
}

# Every OCI instance has at least one VNIC; no count guard — errors if
# missing, which means something catastrophic upstream.
data "oci_core_vnic" "primary" {
  vnic_id = data.oci_core_vnic_attachments.primary.vnic_attachments[0].vnic_id
}
