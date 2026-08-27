# troubleshooting

The first diagnostics to run for common problems.

## `BW_SESSION is not set`

```
export BW_SESSION=$(bw unlock --raw)
```

If `bw unlock` itself fails, make sure that `bw login` has run at least once on
this host. The login is separate from the unlock of each session.

## `bitwarden vault is 'locked'`

The session token expired. Run `bw unlock --raw` again and export the result. A
session expires without a message. That is the normal behaviour of the CLI.

## `bw status` does not return

The CLI is trying to sync against the upstream vault. Usual causes:
- The host is offline, or a captive portal blocks it. Connect and try again.
- A rate limit on the server. Wait 1 minute.
- A stale local configuration at `~/.config/Bitwarden CLI/data.json`. As the last
  option, run `bw logout` and then `bw login` again.

## `ssh-add refused the key`

The private key was fetched correctly, but `ssh-add` rejected it. Usual causes:
- The key has a passphrase. Our keys should not have one.
- The key format is DSA or RSA-1, which modern OpenSSH does not support.
  Generate an ed25519 key instead.
- `SSH_AUTH_SOCK` is unset. Run `eval "$(ssh-agent -s)"` first.

## `tailscale up` fails with "auth key already used"

By default a pre-auth key works only once. Create a new key in the Tailscale
admin console, update `tailscale-authkey-<tag>` in Bitwarden, and try again.

## `generate-machine-index.sh` produces empty output

Check that each `machines/<category>/<name>/identity.yaml` exists, under
`machines/development/` or `machines/services/`. The script indexes only the
directories that contain one.

## `bash machines/ctl.sh new-host ...` says that the template is not found

List the templates:

```
ls machines/templates/
```

Make sure that the template name matches exactly: kebab-case, no slashes.

## Shellcheck reports errors after you edit a script

Run it directly to see the output line by line:

```
shellcheck machines/scripts/<script>.sh
```

The validator reports failures at error severity only. To clean up the
warning-level output, run `shellcheck` without `-S error`.

## The Ansible run of a host fails on platform-windows

Confirm the WinRM prerequisites:

```
Test-WSMan -ComputerName <host> -Port 5986 -UseSSL
```

The comment at the top of
`machines/roles/platform-windows/tasks/main.yml` describes the one-time setup on
the Windows side, which is outside the scope of Ansible.

## Anything else

File an issue in the parent monorepo. For a problem specific to infrastructure,
tag it `scope:infrastructure`.
