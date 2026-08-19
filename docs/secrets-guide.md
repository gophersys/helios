# secrets-guide

How a secret enters and leaves an operator's shell session, end to end.

## The rules

1. A secret lives in Vaultwarden (self-hosted, Bitwarden-compatible, so the `bw`
   tooling applies without change). Nowhere else.
2. A secret passes through the tmpfs directory `/dev/shm/brain-secrets-$$/`.
3. A secret is scrubbed when the shell exits, through `trap on_exit EXIT`.
4. A script logs the *name* of a secret, never the value.
5. A script never receives a secret on the command line.

## Flow: load a set of secrets

```
export BW_SESSION=$(bw unlock --raw)

bash machines/scripts/secrets-load.sh bw-manifest-dev-cluster

# Env now has ORACLE_API_TOKEN_FILE=/dev/shm/brain-secrets-<pid>/ORACLE_API_TOKEN
# Consumer reads the file:
terraform apply -var="oracle_api_token=$(cat "$ORACLE_API_TOKEN_FILE")"

# When the shell exits, the trap fires and scrubs everything.
```

The manifest `bw-manifest-dev-cluster` is itself a Bitwarden item. Its "notes"
field holds one `ENV_VAR=bw-item-name` mapping per line. Example notes:

```
ORACLE_API_TOKEN=cloud-oracle-oke-admin
AWS_SECRET_ACCESS_KEY=cloud-aws-brain-admin
GITHUB_TOKEN=github-brain-bot
```

The script fetches the `password` field of each referenced item, writes it to
`/dev/shm/brain-secrets-$$/<env-var-name>` with mode 0600, and exports
`<env-var-name>_FILE` with the tmpfs path.

## Flow: SSH into a machine

```
export BW_SESSION=$(bw unlock --raw)
bash machines/scripts/ssh-ephemeral.sh my-host
```

1. The script fetches `ssh-key-my-host` from Bitwarden. The private key is in the
   "notes" field.
2. It writes the key to `/dev/shm/<random>/id` with mode 0600.
3. It runs `ssh-add -t 300 /dev/shm/<random>/id`, so the agent holds the key for
   5 minutes.
4. It connects to the machine's Tailscale hostname, which is the machine name
   verbatim. There is no per-host override.
5. It calls `ssh` with `IdentitiesOnly=yes`, so only the new key is offered.
6. On exit it runs `ssh-add -d`, shreds the key, and removes the tmpfs directory.

If the SSH session is interactive and the operator walks away, the agent forgets
the key after 5 minutes, whether or not the trap fires.

## Flow: provision Tailscale on a host

```
export BW_SESSION=$(bw unlock --raw)
sudo -E bash machines/scripts/tailscale-provision.sh k8s-node --hostname node-01 --ssh
```

`sudo -E` keeps `BW_SESSION`. The script fetches `tailscale-authkey-k8s-node`
from Bitwarden and runs `tailscale up`.

Caveat: the current script passes the key inline with `--auth-key=`, because not
every Tailscale version supports `--authkey-file`. The key is therefore in
`/proc/<pid>/cmdline` while the `tailscale` command runs. TODO: change to
`--authkey-file` when the minimum supported Tailscale version on all our
platforms is 1.60 or higher.

## Flow: purge without exiting the shell

```
bash machines/scripts/secrets-purge.sh            # this shell's tmpfs
bash machines/scripts/secrets-purge.sh --all      # every brain-secrets-* owned by $USER
```

The script is idempotent. It is safe to run after a crash in which the trap did
not fire.

## Flow: rotation

Not implemented. Rotation is an action that needs approval, per brain's top-level
rules. The hooks **will** arrive as a `secrets-rotate` verb once the approval gate
infrastructure exists.

## What NOT to do

- Do not source `machines/scripts/secrets-load.sh`. It must run as a subshell. If
  you source it, the trap fires when the shell exits. That scrubs the tmpfs after
  the consumer has already finished its work, and it also tries to unset the
  exported variables. If you need the secrets to persist for an interactive
  session, use the helper from `roles/secrets-bitwarden-client`, which exposes a
  `bw-session` shell function.
- Do not copy a tmpfs file to disk. The storage must stay temporary.
- Do not print `cat "$ORACLE_API_TOKEN_FILE"` in a script or a chat window. Pipe
  the value into the consumer instead.
