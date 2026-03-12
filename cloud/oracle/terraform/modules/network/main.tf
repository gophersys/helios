# -----------------------------------------------------------------------------
# Network Module — VCN, Subnet, Internet Gateway, Security List
# -----------------------------------------------------------------------------
# Single public subnet topology for the K3s cluster.
# All nodes get public IPs; Tailscale handles the overlay mesh.
# -----------------------------------------------------------------------------

terraform {
  required_providers {
    oci = {
      source = "oracle/oci"
    }
  }
}

# =============================================================================
# VCN
# =============================================================================

resource "oci_core_vcn" "main" {
  compartment_id = var.compartment_ocid
  cidr_blocks    = [var.vcn_cidr]
  display_name   = "k3s-vcn"
  dns_label      = "k3svcn"

  freeform_tags = {
    project = "infrastructure"
  }
}

# =============================================================================
# Internet Gateway
# =============================================================================

resource "oci_core_internet_gateway" "main" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.main.id
  display_name   = "k3s-igw"
  enabled        = true

  freeform_tags = {
    project = "infrastructure"
  }
}

# =============================================================================
# Route Table
# =============================================================================

resource "oci_core_route_table" "public" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.main.id
  display_name   = "k3s-public-rt"

  route_rules {
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
    network_entity_id = oci_core_internet_gateway.main.id
  }

  freeform_tags = {
    project = "infrastructure"
  }
}

# =============================================================================
# Security List
# =============================================================================

resource "oci_core_security_list" "public" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.main.id
  display_name   = "k3s-public-sl"

  # ---------------------------------------------------------------------------
  # Egress: allow all outbound traffic
  # ---------------------------------------------------------------------------
  egress_security_rules {
    destination = "0.0.0.0/0"
    protocol    = "all" # all protocols
    stateless   = false
  }

  # ---------------------------------------------------------------------------
  # Ingress: SSH (TCP 22)
  # ---------------------------------------------------------------------------
  dynamic "ingress_security_rules" {
    for_each = var.ssh_allowed_cidrs
    content {
      source    = ingress_security_rules.value
      protocol  = "6" # TCP
      stateless = false

      tcp_options {
        min = 22
        max = 22
      }
    }
  }

  # ---------------------------------------------------------------------------
  # Ingress: HTTP (TCP 80)
  # ---------------------------------------------------------------------------
  ingress_security_rules {
    source    = "0.0.0.0/0"
    protocol  = "6" # TCP
    stateless = false

    tcp_options {
      min = 80
      max = 80
    }
  }

  # ---------------------------------------------------------------------------
  # Ingress: HTTPS (TCP 443)
  # ---------------------------------------------------------------------------
  ingress_security_rules {
    source    = "0.0.0.0/0"
    protocol  = "6" # TCP
    stateless = false

    tcp_options {
      min = 443
      max = 443
    }
  }

  # ---------------------------------------------------------------------------
  # Ingress: K3s API Server (TCP 6443)
  # ---------------------------------------------------------------------------
  ingress_security_rules {
    source    = "0.0.0.0/0"
    protocol  = "6" # TCP
    stateless = false

    tcp_options {
      min = 6443
      max = 6443
    }
  }

  # ---------------------------------------------------------------------------
  # Ingress: Tailscale WireGuard (UDP 41641)
  # ---------------------------------------------------------------------------
  ingress_security_rules {
    source    = "0.0.0.0/0"
    protocol  = "17" # UDP
    stateless = false

    udp_options {
      min = 41641
      max = 41641
    }
  }

  # ---------------------------------------------------------------------------
  # Ingress: ICMP (all types — needed for path MTU discovery)
  # ---------------------------------------------------------------------------
  ingress_security_rules {
    source    = "0.0.0.0/0"
    protocol  = "1" # ICMP
    stateless = false
  }

  freeform_tags = {
    project = "infrastructure"
  }
}

# =============================================================================
# Public Subnet
# =============================================================================

resource "oci_core_subnet" "public" {
  compartment_id             = var.compartment_ocid
  vcn_id                     = oci_core_vcn.main.id
  cidr_block                 = var.public_subnet_cidr
  display_name               = "k3s-public-subnet"
  dns_label                  = "pub"
  route_table_id             = oci_core_route_table.public.id
  security_list_ids          = [oci_core_security_list.public.id]
  prohibit_public_ip_on_vnic = false

  freeform_tags = {
    project = "infrastructure"
  }
}
