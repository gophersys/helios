# machines/roles

Ansible roles applied to machines under IaC management. Each role is a
directory with at minimum `tasks/main.yml`.

## Categories

- `common` — portable tasks that apply to any OS (shell setup, git
  identity, basic packages). First role applied on every host.
- `platform-*` — OS-family-specific setup (packages, systemd units,
  networking). Apply exactly one per host.
- `networking-*` — cross-cutting network capabilities (Tailscale, VPNs).
- `secrets-*` — secret-management capabilities (Bitwarden CLI).
- `developer-*` — developer capabilities layered on top of a platform
  (kubectl + helm, Flutter SDK, embedded toolchains).

## Order of application

Per host's `identity.yaml`, roles run in the declared order. Conventional
order is:

```
common
platform-<os>
networking-*
secrets-*
developer-*
```

## Stubs

Roles with `TODO:` markers are not yet implemented. Using a stub role
does not fail a playbook run — it just does nothing visible. Implement
the real tasks when the first host needs them.
