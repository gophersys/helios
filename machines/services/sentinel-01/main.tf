#
# sentinel-01 — prod tailnet bastion (OCI E2.1.Micro x86, always-free, HA pair).
#
# Init:
#   terraform init \
#     -backend-config=../../../providers/state-backend/backend.hcl \
#     -backend-config=key=machines/services/sentinel-01/terraform.tfstate
#
# Import:
#   terraform import \
#     'module.instance.oci_core_instance.destroyable[0]' \
#     'ocid1.instance.oc1.phx.anyhqljtslzce6ac3qgdneikdgj2mmntzptywfixkma2fi7ddxk3eshaw7hq'
#

terraform {
  required_version = ">= 1.10.0"
  required_providers {
    oci = {
      source  = "oracle/oci"
      version = ">= 6.0.0, < 8.0.0"
    }
  }
  backend "s3" {}
}

provider "oci" {}

variable "ssh_public_key" {
  type    = string
  default = ""
}

variable "tailnet_auth_key" {
  type      = string
  sensitive = true
  default   = ""
}

module "instance" {
  source = "../../../providers/oracle/modules/compute"

  name      = "sentinel-01"
  arch      = "amd64"
  cpu_count = 1
  memory_gb = 1
  disk_gb   = 47
  role      = "service"
  network   = "public"

  compartment_ocid    = "ocid1.tenancy.oc1..aaaaaaaa5iycmk4zpz3dzyht4o4z5nztiqi7zyrosmxjvw4rjymoxdvtbw7a"
  availability_domain = "FEQI:PHX-AD-2"
  subnet_ocid         = "ocid1.subnet.oc1.phx.aaaaaaaagtaww7cbqlo6qtgv3od4dxmcr375qh3uryc5ecfeh6dsdn5vtruq"
  shape               = "VM.Standard.E2.1.Micro"
  image_ocid          = "ocid1.image.oc1.phx.aaaaaaaarmcelmbnwximabxo7qvea5cv56bjfa3jnpmgvsfpkeq2e6w4w4ta"
  hostname_label      = "k3s-x86-2-660755"
  prevent_destroy     = false

  ssh_public_key   = var.ssh_public_key
  tailnet_auth_key = var.tailnet_auth_key

  tags = {
    role = "bastion"
  }
}

output "id" { value = module.instance.id }
output "private_ip" { value = module.instance.private_ip }
output "public_ip" { value = module.instance.public_ip }
output "tailnet_name" { value = module.instance.tailnet_name }
output "fqdn" { value = module.instance.fqdn }
