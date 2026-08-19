# machines — conventions

## Host taxonomy

At directory level, the machines split into 2 categories:

| Category        | Path prefix                 | Contains                                                       |
|-----------------|-----------------------------|----------------------------------------------------------------|
| `development`   | `machines/development/`     | Developer workstations: laptops, desktops, WSL, macOS builders |
| `services`      | `machines/services/`        | Service hosts: cluster nodes, bastions, ARM builders, etc.     |

The templates use the same split, at `machines/templates/<category>/<template>/`.

## Every machine documents itself

Every machine is its own source of truth. `machines/<category>/<name>/` is a
small bundle of data files, and together they describe the machine completely:

```
machines/<category>/<name>/
├── identity.yaml          # required — who/what/where/why
├── ansible/
│   ├── host_vars.yaml     # machine-specific Ansible variables
│   └── playbook.yaml      # (optional) machine-specific playbook
├── scripts/               # (optional) host-local scripts
├── peripherals.yaml       # (optional) attached devices: phones, MCUs
└── notes.md               # (optional) human notes
```

The local `scripts/` directory holds logic that applies to this machine only. An
example is a start-and-stop script for one cloud instance, which manages that
instance and nothing else. A script that operates across many machines goes in
`machines/scripts/` instead. The test: if the script name includes the name of
the machine, or if it makes sense for 1 host only, put it in the local directory.
Otherwise put it in `machines/scripts/`.

`identity.yaml` MUST contain at least these fields:

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

Anything that is not in identity.yaml is an implementation detail of the
machine's own subtree. To add a new machine you never touch another path.

## Record keeping

`machines/README.md` and `machines/ledger.md` are both generated artifacts. Never
edit them by hand, because `machines/scripts/generate-machine-index.sh`
overwrites every edit.

The ledger splits the machines by lifecycle state AND by category:

- `planned` — the file exists, but the machine does not exist yet.
- `active` — the machine is reachable on the tailnet and under Ansible
  management.
- `retired` — the machine is decommissioned, and the file stays as a historical
  record.

Retirement is a soft delete: set `status: retired` in identity.yaml. The
directory stays, for the audit trail. A hard delete needs approval at brain
level.

## Create a new machine

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
4. Regenerate the index:
   ```
   bash machines/ctl.sh generate-index
   ```
5. Commit:
   ```
   git add machines/services/agent-03 machines/README.md machines/ledger.md
   git commit -m 'feat(machines): enroll services/agent-03'
   ```

## Ansible roles

A role lives at `machines/roles/<role-name>/`. It follows the standard Ansible
role layout:

```
roles/<role>/
├── tasks/main.yml
├── defaults/main.yml        # (optional)
├── handlers/main.yml        # (optional)
└── templates/               # (optional)
```

A role is generic. It targets a platform (`platform-linux-debian`) or a
capability (`developer-kubernetes-operator`). It never hard-codes one specific
machine.

A platform role owns the package install, the systemd units and the OS
configuration. A capability role assumes that a platform role already ran.

## Groups

`machines/groups/by-purpose/` and `machines/groups/by-location/` will be Ansible
inventory fragments that group the hosts by 1 dimension each. **Neither
directory exists today**: the extension that emits them does not exist either,
and the empty placeholders that stood in for them were removed on 2026-08-19.
They are NOT the source of truth; identity.yaml is. The groups are generated
from identity.yaml once the index generator is extended to emit an inventory.

TODO: extend `generate-machine-index.sh` so that it also emits
`machines/groups/by-purpose/<purpose>.yml` and the equivalent by-location files.
