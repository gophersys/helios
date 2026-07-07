# infrastructure — secrets handling

Infrastructure-specific rules for secret material. Layers on top of brain's
global secrets discipline; in case of conflict, brain's rule wins.

## Vaultwarden is the only source

Every secret consumed by infrastructure — SSH keys, Tailscale auth keys,
cloud API tokens, container registry credentials, certificate keys — lives
in the self-hosted Vaultwarden (secrets.mateosegura.com; Bitwarden-compatible,
so the `bw` CLI and the Bitwarden naming below apply unchanged). Not in this
repo. Not in any consuming project. Not on any developer machine outside tmpfs.

## Naming conventions in the vault

Items in the vault follow these name prefixes so scripts can resolve them
mechanically:

- `ssh-key-<host>` — SSH private key for a machine. Used by
  `machines/scripts/ssh-ephemeral.sh`.
- `tailscale-authkey-<tag>` — Tailscale pre-auth key scoped to a tag.
  Used by `machines/scripts/tailscale-provision.sh`.
- `bw-manifest-<context>` — arbitrary secret bundle loaded by
  `machines/scripts/secrets-load.sh`. The item's "notes" field holds a
  newline-separated list of `<env-var-name>=<bw-item-name>` mappings.
- `cloud-<provider>-<purpose>` — cloud provider API credentials
  (e.g., `cloud-aws-brain-admin`, `cloud-oracle-oke-admin`).

## Script contract

Every script in `machines/scripts/` that touches secrets:

1. Pre-flights with `bw status`; exits with a helpful error if locked.
2. Writes only to `/dev/shm/brain-secrets-$$/...` with mode 0600.
3. Registers a `trap on_exit EXIT` handler that shreds files, unsets
   variables, and removes the tmpfs directory.
4. Logs names only, never values.
5. Never passes secrets on the command line.

## Forbidden

- Committing any file that looks like a secret (`.pem`, `.key`, `.env`,
  `id_rsa*`, `*.pfx`, `*.p12`). Enforced by `.gitignore`.
- Reading a secret value into any interactive shell transcript. Scripts
  pipe secrets into consumers; their stdout never contains secret values.
- Storing secrets in Ansible vaults, Terraform state files, or Kubernetes
  Secret manifests committed to git. Use external-secrets with Bitwarden
  as the provider (see `platform/secrets-external-operator/`).

## Rotation

Rotation is an approval-gated action. The `secrets-rotate` verb is not
implemented on any project yet; adding it requires the brain-level
approval flow.
