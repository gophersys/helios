# secrets-guide

End-to-end walk-through of how secrets enter and leave an operator's
shell session.

## The rules (one-liner per)

1. Secrets live in Bitwarden. Nowhere else.
2. Secrets transit through `/dev/shm/brain-secrets-$$/` tmpfs.
3. Secrets scrub on shell exit via `trap on_exit EXIT`.
4. Scripts log secret *names*, never values.
5. Scripts never receive secrets on the command line.

## Flow: loading a set of secrets

```
export BW_SESSION=$(bw unlock --raw)

bash machines/scripts/secrets-load.sh bw-manifest-dev-cluster

# Env now has ORACLE_API_TOKEN_FILE=/dev/shm/brain-secrets-<pid>/ORACLE_API_TOKEN
# Consumer reads the file:
terraform apply -var="oracle_api_token=$(cat "$ORACLE_API_TOKEN_FILE")"

# When the shell exits, the trap fires and scrubs everything.
```

The manifest `bw-manifest-dev-cluster` is itself a Bitwarden item. Its
"notes" field contains one `ENV_VAR=bw-item-name` mapping per line.
Example notes:

```
ORACLE_API_TOKEN=cloud-oracle-oke-admin
AWS_SECRET_ACCESS_KEY=cloud-aws-brain-admin
GITHUB_TOKEN=github-brain-bot
```

The script fetches each referenced item's `password` field, writes it to
`/dev/shm/brain-secrets-$$/<env-var-name>` with mode 0600, and exports
`<env-var-name>_FILE` pointing at the tmpfs path.

## Flow: SSH into a machine

```
export BW_SESSION=$(bw unlock --raw)
bash machines/scripts/ssh-ephemeral.sh my-host
```

1. Script fetches `ssh-key-my-host` from BW (private key stored in
   "notes" field).
2. Writes to `/dev/shm/<random>/id` with mode 0600.
3. `ssh-add -t 300 /dev/shm/<random>/id` — agent remembers for 5 minutes.
4. Resolves target via `identity.yaml:tailscale_hostname` or falls back to
   machine name.
5. Invokes `ssh` with `IdentitiesOnly=yes` so only the freshly added key
   is offered.
6. On exit: `ssh-add -d`, shred the key, remove the tmpfs dir.

If the SSH session is interactive and the operator walks away, the agent
forgets the key after 5 minutes regardless of whether the trap ever fires.

## Flow: provisioning Tailscale on a host

```
export BW_SESSION=$(bw unlock --raw)
sudo -E bash machines/scripts/tailscale-provision.sh k8s-node --hostname node-01 --ssh
```

`sudo -E` preserves `BW_SESSION`. The script fetches
`tailscale-authkey-k8s-node` from BW and runs `tailscale up`.

Caveat: the current script passes the key inline via `--auth-key=` because
not every Tailscale version supports `--authkey-file`. This means the key
is in `/proc/<pid>/cmdline` for the lifetime of the `tailscale` invocation.
TODO: switch to `--authkey-file` once the minimum supported Tailscale
version across our platforms is >=1.60.

## Flow: purging without exiting the shell

```
bash machines/scripts/secrets-purge.sh            # this shell's tmpfs
bash machines/scripts/secrets-purge.sh --all      # every brain-secrets-* owned by $USER
```

Idempotent. Safe to run after a crash where a trap did not fire.

## Flow: rotation

Not implemented. Rotation is an approval-gated action per brain's
top-level rules. The hooks will land as a `secrets-rotate` verb once the
approval gate infrastructure exists.

## What NOT to do

- Do not source `machines/scripts/secrets-load.sh` — running it as a
  subshell is intentional. Sourcing would make the trap fire when the
  shell exits, scrubbing tmpfs after the consumer has already finished
  its work anyway but also attempting to unset exported vars. If you need
  secrets persistent for an interactive session, use the helper from
  `roles/secrets-bitwarden-client` which exposes a `bw-session` shell
  function.
- Do not copy a tmpfs file to disk. The whole point is ephemeral storage.
- Do not print `cat "$ORACLE_API_TOKEN_FILE"` in any script or chat
  window — pipe into the consumer, don't reveal.
