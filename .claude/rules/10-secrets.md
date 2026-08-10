# infrastructure — secrets handling

Rules for secret material that are specific to infrastructure. They add to the
global secrets discipline in brain. If the 2 sets of rules conflict, the brain
rule wins.

## Vaultwarden is the only source

Every secret that infrastructure consumes — an SSH key, a Tailscale auth key, a
cloud API token, a container registry credential, a certificate key — lives in
the self-hosted Vaultwarden at secrets.mateosegura.com. It is
Bitwarden-compatible, so the `bw` CLI and the Bitwarden naming below apply
without change. A secret does not live in this repo. It does not live in a
consuming project. It does not live on a developer machine outside tmpfs.

## Naming conventions in the vault

An item in the vault uses one of these name prefixes, so that a script can
resolve it mechanically:

- `ssh-key-<host>` — the SSH private key for a machine.
  `machines/scripts/ssh-ephemeral.sh` uses it.
- `tailscale-authkey-<tag>` — a Tailscale pre-auth key scoped to a tag.
  `machines/scripts/tailscale-provision.sh` uses it.
- `bw-manifest-<context>` — a bundle of secrets that
  `machines/scripts/secrets-load.sh` loads. The "notes" field of the item holds a
  list of `<env-var-name>=<bw-item-name>` mappings, one per line.
- `cloud-<provider>-<purpose>` — API credentials for a cloud provider, for
  example `cloud-aws-brain-admin` and `cloud-oracle-oke-admin`.

## Script contract

Every script in `machines/scripts/` that touches a secret must do all of the
following:

1. Check `bw status` first, and exit with a helpful error if the vault is locked.
2. Write only to `/dev/shm/brain-secrets-$$/...` with mode 0600.
3. Register a `trap on_exit EXIT` handler that shreds the files, unsets the
   variables and removes the tmpfs directory.
4. Log names only, never values.
5. Never pass a secret on the command line.

## Forbidden

- Do not commit any file that looks like a secret (`.pem`, `.key`, `.env`,
  `id_rsa*`, `*.pfx`, `*.p12`). `.gitignore` enforces this.
- Do not read a secret value into an interactive shell transcript. A script pipes
  a secret into its consumer, and its stdout never contains a secret value.
- Do not store a secret in an Ansible vault, in a Terraform state file, or in a
  Kubernetes Secret manifest committed to git. Use external-secrets with the
  vault (Vaultwarden, which is Bitwarden-compatible) as the provider. See
  `platform/core/secrets-operator/` and `docs/runtime-secrets.md`.

## Rotation

Rotation needs approval. The `secrets-rotate` verb is not implemented on any
project yet, and to add it you must use the approval flow at brain level.
