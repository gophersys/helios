# getting-started

First-time operator setup for `infrastructure/`.

## 1. Prerequisites

On the operator host (Linux, macOS, or WSL):

- `git` 2.40+.
- `bash` 5.0+.
- `python3` 3.10+ (used by scripts to parse YAML/JSON).
- `bw` (Bitwarden CLI) — install from Bitwarden's official sources or
  `npm install -g @bitwarden/cli`.
- `shellcheck` — for pre-commit linting of bash.
- `shred` — part of coreutils; used by secret-handling scripts.
- `tailscale` — for Tailscale-backed SSH and host provisioning.
- `terraform` (optional) — for `plan`/`apply` on cluster instances.
- `ansible` + `ansible-core` (optional) — for host convergence.

The parent monorepo (`brain`) additionally provides Nx. This repo does not
require Nx for local authoring — every verb works via `bash ./ctl.sh <verb>`.

## 2. Clone via the parent monorepo

```
git clone --recurse-submodules git@github.com:gophersys/brain.git
cd brain
```

The `shared/infrastructure/` submodule is this repo. Edit it in place;
commits there are authored by `Mateo Segura <mateo.segura413@gmail.com>`
and signed with `commit.gpgsign=false`.

## 3. Unlock Bitwarden once per session

```
export BW_SESSION=$(bw unlock --raw)
```

Every script in `machines/scripts/` preflights this. If `BW_SESSION` is
unset or the vault is locked, scripts exit with a helpful message.

## 4. First-look

```
cd shared/infrastructure
bash ./ctl.sh status
bash ./ctl.sh validate
```

`status` prints counts across all layers. `validate` lints every bash
script and every `project.json`.

## 5. Adding a machine

```
bash machines/ctl.sh new-host linux-server-kubernetes my-new-host
$EDITOR machines/hosts/my-new-host/identity.yaml
bash ctl.sh generate-index
git add machines/hosts/my-new-host machines/README.md machines/ledger.md
git commit -m 'feat(machines): enroll my-new-host'
```

## 6. What's NOT yet implemented

- Cluster instances (`clusters/instances/*`) — no live clusters yet.
- Provider Terraform modules (`providers/*/modules/*`) — empty.
- Platform service releases (`platform/*/ctl.sh` + values) — READMEs only.
- Helm charts (`charts/*/templates/`) — READMEs only.

These populate when the first real consumer arrives. No speculative
scaffolding.
