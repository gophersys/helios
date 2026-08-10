# getting-started

First-time operator setup for `infrastructure/`.

## 1. Prerequisites

Install these on the operator host (Linux, macOS or WSL):

- `git` 2.40+.
- `bash` 5.0+.
- `python3` 3.10+ (the scripts use it to parse YAML and JSON).
- `bw` (Bitwarden CLI) — install it from Bitwarden's official sources or with
  `npm install -g @bitwarden/cli`.
- `shellcheck` — for the pre-commit lint of bash.
- `shred` — part of coreutils; the secret-handling scripts use it.
- `tailscale` — for SSH through Tailscale and for host provisioning.
- `terraform` (optional) — for `plan` and `apply` on a cluster instance.
- `ansible` + `ansible-core` (optional) — for host convergence.

The parent monorepo (`brain`) also supplies Nx. This repo does not need Nx for
local authoring, because every verb works through `bash ./ctl.sh <verb>`.

## 2. Clone through the parent monorepo

```
git clone --recurse-submodules git@github.com:gophersys/brain.git
cd brain
```

The `shared/infrastructure/` submodule is this repo. Edit it in place. The
commits there are authored by `Mateo Segura <mateo.segura413@gmail.com>` and
signed with `commit.gpgsign=false`.

## 3. Unlock Bitwarden once per session

```
export BW_SESSION=$(bw unlock --raw)
```

Every script in `machines/scripts/` checks this first. If `BW_SESSION` is unset
or the vault is locked, the script exits with a message that says what to do.

## 4. First look

```
cd shared/infrastructure
bash ./ctl.sh status
bash ./ctl.sh validate
```

`status` prints the counts across all layers. `validate` lints every bash script
and every `project.json`.

## 5. Add a machine

```
bash machines/ctl.sh new-host linux-server-kubernetes my-new-host
$EDITOR machines/hosts/my-new-host/identity.yaml
bash ctl.sh generate-index
git add machines/hosts/my-new-host machines/README.md machines/ledger.md
git commit -m 'feat(machines): enroll my-new-host'
```

## 6. What is NOT implemented yet

- Cluster instances (`clusters/instances/*`) — there are no live clusters yet.
- Provider Terraform modules (`providers/*/modules/*`) — empty.
- Platform service releases (`platform/*/ctl.sh` + values) — READMEs only.
- Helm charts (`charts/*/templates/`) — READMEs only.

Each of these is populated when the first real consumer arrives. Do not scaffold
in advance.
