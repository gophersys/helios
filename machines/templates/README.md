# machines/templates

Blueprints used by `bash machines/ctl.sh new-host <category> <template> <name>`
to scaffold a new host directory under `machines/<category>/<name>/`, where
`<category>` is `development` or `services`.

A template is a directory tree; `new-host` copies it verbatim, then replaces
the literal token `__HOST_NAME__` in `identity.yaml` with the provided host
name. Every other field the operator fills in manually.

## Available templates

| Template                           | For                                         | Priority |
|------------------------------------|---------------------------------------------|----------|
| `linux-server-kubernetes`          | Bare/cloud Linux server running k3s or k8s  | high     |
| `linux-developer-workstation`      | Linux desktop/laptop used for dev           | high     |
| `windows-developer-workstation`    | Windows 11 host used for dev + WSL parent   | high     |
| `wsl-developer-workstation`        | A WSL2 distro inside a Windows host         | high     |
| `macos-mobile-development`         | macOS machine for iOS/Flutter builds        | low/stub |

## Adding a new template

1. Create `machines/templates/<template-name>/`.
2. Drop an `identity.yaml` with `name: __HOST_NAME__` and sensible defaults
   for every other field. Use placeholder `TODO` strings for values the
   operator must supply.
3. Optionally add subfolders (`ansible/`, etc.) mirroring the host layout.
4. Run `bash machines/ctl.sh validate` to confirm the template passes the
   lint.

Templates themselves are NOT hosts — they are never included in the index.
