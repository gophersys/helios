# machines/groups

Host groupings used for Ansible inventory filtering and playbook targeting.

- `by-purpose/` — groupings like `dev-workstations.yml`, `k8s-nodes.yml`,
  `mobile-builders.yml`. One file per purpose.
- `by-location/` — groupings like `home-office.yml`, `oracle-frankfurt.yml`.
  One file per physical/cloud location.

Both are generated artifacts. The source of truth is each machine's
`identity.yaml` (`purpose:` and `location:` fields). The index generator
in `machines/scripts/generate-machine-index.sh` is scheduled to emit these
group files — not yet implemented (see the TODO in
`machines/CONVENTIONS.md`).
