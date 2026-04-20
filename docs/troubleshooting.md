# troubleshooting

First-stop diagnostics for common issues.

## `BW_SESSION is not set`

```
export BW_SESSION=$(bw unlock --raw)
```

If `bw unlock` itself fails, make sure `bw login` has been run at least
once on this host. The login is separate from the per-session unlock.

## `bitwarden vault is 'locked'`

The session token expired. Re-run `bw unlock --raw` and export. Sessions
expire silently — this is expected behavior from the CLI.

## `bw status` hangs

The CLI is trying to sync against the upstream vault. Usual causes:
- Offline / captive portal — connect and retry.
- Server-side rate limit — wait a minute.
- A stale local config at `~/.config/Bitwarden CLI/data.json` — as a last
  resort, `bw logout` and `bw login` again.

## `ssh-add refused the key`

The private key was fetched correctly but `ssh-add` rejected it. Usual
causes:
- Key is encrypted with a passphrase (our keys should not be).
- Key format is DSA/RSA-1 (unsupported by modern OpenSSH). Re-generate
  as ed25519.
- `SSH_AUTH_SOCK` is unset — run `eval "$(ssh-agent -s)"` first.

## `tailscale up` fails with "auth key already used"

Pre-auth keys are one-shot by default. Create a fresh key in the
Tailscale admin console, update `tailscale-authkey-<tag>` in Bitwarden,
retry.

## `generate-machine-index.sh` produces empty output

Check that each `machines/hosts/<name>/identity.yaml` actually exists —
the script only indexes directories that contain one. A directory with
just a `.gitkeep` is ignored.

## `bash machines/ctl.sh new-host ...` says template not found

List templates:

```
ls machines/templates/
```

Make sure the template name matches exactly (kebab-case, no slashes).

## Shellcheck errors after editing a script

Run directly to see line-by-line output:

```
shellcheck machines/scripts/<script>.sh
```

The validator only reports failures at error severity. For warning-level
cleanup, run `shellcheck` without `-S error`.

## A host's Ansible run fails on platform-windows

Confirm WinRM prerequisites:

```
Test-WSMan -ComputerName <host> -Port 5986 -UseSSL
```

See the comment at the top of `machines/roles/platform-windows/tasks/main.yml`
for the one-time Windows-side setup that's outside Ansible's scope.

## Anything else

File an issue in the parent monorepo. For infra-specific issues, tag
`scope:infrastructure`.
