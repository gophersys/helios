# machines — conventions

## Host taxonomy

Machines split into two categories at the directory level:

| Category        | Path prefix                 | Contains                                                       |
|-----------------|-----------------------------|----------------------------------------------------------------|
| `development`   | `machines/development/`     | Developer workstations: laptops, desktops, WSL, macOS builders |
| `services`      | `machines/services/`        | Service hosts: cluster nodes, bastions, ARM builders, etc.     |

Templates mirror the split at `machines/templates/<category>/<template>/`.

## The self-documenting principle

Every machine is its own source of truth. `machines/<category>/<name>/` is
a small bundle of data files that together describe the machine completely:

```
machines/<category>/<name>/
├── identity.yaml          # required — who/what/where/why
├── ansible/
│   ├── host_vars.yaml     # machine-specific Ansible variables
│   └── playbook.yaml      # (optional) machine-specific playbook
├── scripts/               # (optional) host-local scripts (e.g. arm-builder CLI)
├── peripherals.yaml       # (optional) attached devices: phones, MCUs
└── notes.md               # (optional) human notes
```

Host-local `scripts/` are for logic that's only meaningful for this
specific machine (example: `services/arm-builder/scripts/arm-builder.sh`
which manages that exact EC2 instance). Fleet-wide scripts — anything
that operates across many machines — live in `machines/scripts/` instead.
Rule of thumb: if the script name includes the machine's name or only
makes sense for one host, it goes local; otherwise fleet-wide.

`identity.yaml` MUST contain at least:

```yaml
name: <host-name>                    # same as directory name
os: <linux-debian|linux-fedora|windows-server|windows-client|wsl-debian|macos>
purpose: <short free-text>           # e.g. "k3s server for brain dev cluster"
tailscale_hostname: <string>         # the name used by tailscale up --hostname
status: <active|planned|retired>
location: <free-text>                # e.g. "home-office", "oracle-phoenix"
owner: <email>
roles:                               # Ansible roles to apply, in order
  - common
  - platform-linux-debian
  - networking-tailscale
  - secrets-bitwarden-client
```

Anything not in identity.yaml is an implementation detail of the machine's
own subtree. Adding a new machine never requires touching any other path.

## Track-keeping

`machines/README.md` and `machines/ledger.md` are both generated artifacts.
Never edit them by hand — every edit is overwritten by
`machines/scripts/generate-machine-index.sh`.

The ledger splits machines by lifecycle state AND by category:

- `planned` — file exists, machine doesn't yet.
- `active` — reachable on the tailnet and under Ansible management.
- `retired` — decommissioned; file kept as historical record.

Retirement is a soft delete: change `status: retired` in identity.yaml. The
directory stays for audit. Hard-delete is a brain-approved operation.

## Creating a new machine

1. Pick a category (`development` or `services`) and a template:
   ```
   ls machines/templates/development/
   ls machines/templates/services/
   ```
2. Scaffold:
   ```
   bash machines/ctl.sh new-host services linux-server-kubernetes agent-03
   ```
3. Edit `machines/services/agent-03/identity.yaml`. Fill in every field.
4. Regenerate index:
   ```
   bash machines/ctl.sh generate-index
   ```
5. Commit:
   ```
   git add machines/services/agent-03 machines/README.md machines/ledger.md
   git commit -m 'feat(machines): enroll services/agent-03'
   ```

## Ansible roles

Roles live at `machines/roles/<role-name>/`. They follow the standard Ansible
role layout:

```
roles/<role>/
├── tasks/main.yml
├── defaults/main.yml        # (optional)
├── handlers/main.yml        # (optional)
└── templates/               # (optional)
```

A role is generic: it targets a platform (`platform-linux-debian`) or a
capability (`developer-kubernetes-operator`). It never hard-codes a specific
machine.

Platform roles own package install, systemd units, and OS config. Capability
roles assume a platform role already ran.

## Groups

`machines/groups/by-purpose/` and `machines/groups/by-location/` are
Ansible inventory fragments grouping hosts by dimension. They are NOT source
of truth — identity.yaml is. Groups are regenerated from identity.yaml when
the index generator is extended to emit inventory (not yet implemented).

TODO: extend `generate-machine-index.sh` to also emit
`machines/groups/by-purpose/<purpose>.yml` and by-location equivalents.
