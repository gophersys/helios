#
# server-00 — prod cluster server (OCI A1.Flex ARM, irreplaceable).
#
# Init:
#   terraform init \
#     -backend-config=../../../../../providers/state-backend/backend.hcl \
#     -backend-config=key=clusters/prod/nodes/server-00/terraform.tfstate
#
# Import (live instance already exists):
#   terraform import \
#     'module.instance.oci_core_instance.protected[0]' \
#     'ocid1.instance.oc1.phx.anyhqljrslzce6ac2h7h5npmdwa3rdxf5b5zhkldocnwi3vsjr5polrdadfa'
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

provider "oci" {
  # Credentials + tenancy + region sourced from ~/.oci/config (built in
  # tmpfs by the calling ctl.sh / shell from OCI_* env vars).
}

variable "ssh_public_key" {
  type        = string
  description = "Public key — ignored on imports (module ignores metadata)."
  default     = ""
}

variable "tailnet_auth_key" {
  type        = string
  sensitive   = true
  description = "Tailnet pre-auth key — ignored on imports (module ignores metadata)."
  default     = ""
}

module "instance" {
  source = "../../../../../providers/oracle/modules/compute"

  name      = "server-00"
  arch      = "arm64"
  cpu_count = 2
  memory_gb = 12
  disk_gb   = 47
  role      = "cluster"
  network   = "tailnet"

  compartment_ocid    = "ocid1.tenancy.oc1..aaaaaaaa5iycmk4zpz3dzyht4o4z5nztiqi7zyrosmxjvw4rjymoxdvtbw7a"
  availability_domain = "FEQI:PHX-AD-1"
  subnet_ocid         = "ocid1.subnet.oc1.phx.aaaaaaaagtaww7cbqlo6qtgv3od4dxmcr375qh3uryc5ecfeh6dsdn5vtruq"
  shape               = "VM.Standard.A1.Flex"
  image_ocid          = "ocid1.image.oc1.phx.aaaaaaaagxa7pjvb4k55w7tkgr6kocxae7ajegb2x3fjbuwtywxeounv4htq"
  hostname_label      = "code-kit-server"
  prevent_destroy     = true

  ssh_public_key   = var.ssh_public_key
  tailnet_auth_key = var.tailnet_auth_key

  tags = {
    cluster = "prod"
    k3s     = "server"
  }
}

output "id" { value = module.instance.id }
output "private_ip" { value = module.instance.private_ip }
output "public_ip" { value = module.instance.public_ip }
output "tailnet_name" { value = module.instance.tailnet_name }
output "fqdn" { value = module.instance.fqdn }
