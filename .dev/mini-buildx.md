# mini-buildx

phase:    verify
repo:     gophersys/infrastructure
branch:   feat/mini-buildx
worktree: ~/code/.worktrees/infra-buildx
pr:       -
attempt:  1/2

## Goal

Give CI a native arm64 builder. The Mac mini builds arm64 3.44x faster than the
amd64 runners can emulate it, so image workflows stop paying the QEMU tax and
D42 (arm64 dropped from the images) can be reversed.

## MEASURED — do not re-derive

Controlled, same machine, same Dockerfile, images pre-pulled, --no-cache, warmup
discarded:

```
linux/arm64  (native)     4.01s  4.02s  4.02s
linux/amd64  (emulated)  14.05s 13.65s 13.74s      -> 3.44x
```

Cross-check: D42's own basis measured the OPPOSITE direction (the CI case) at
2.9x warm / 9.6x cold. Two measurements, opposite directions, same order.

The remote node works and the transfer cost is not the feared problem:

```
build THROUGH the node   3.25s / 3.31s / 3.24s
context  10MB  ->  1.22s
context 100MB  ->  2.10s          ~100 MB/s, so ~1-2s for a realistic context
pod -> mini    nc -z 10.168.0.92 22 from arc-runners: succeeded
```

## The credential design, already built and proven

The key is DIAL-ONLY. `~/.ssh/macos-buildx` is installed on the mini as:

```
command="/Users/mateo/bin/docker system dial-stdio",restrict ssh-ed25519 ...
```

Proven, all four:

```
ssh ... whoami                 -> no shell; the forced command runs instead
docker -H ssh://macos-buildx   -> server 28.1.1 arch=arm64   rc=0
ssh ... cat ~/.ssh/id_ed25519  -> refused
ssh -L 9999:...                -> forwarding refused
```

This matters because image builds run on the GENERAL `arc-org` pool. An
unrestricted key there would give every build — including one from a pull
request — a shell on the mini. The forced command reduces that to a BuildKit
dial and nothing else.

The private key is in Vaultwarden as `shared/eden/macos-buildx-key`
(secureNote; the notes body IS the value, matching the provider's
`$.data.data[0].notes`). The admin key `~/.ssh/macos-ci-runner` stays
unrestricted for `verify-access` and is a DIFFERENT key.

## Plan

APPROVED (self, under delegated authority, 2026-08-13).

Follow the pattern already in `platform/services/ci/arc-runners/`, do not invent
one: an ExternalSecret against `ClusterSecretStore: vaultwarden`, the repo naming
the vault item and never the value.

1. `40-macos-buildx-key-externalsecret.yaml` — same shape as
   `20-ghcr-pull` and `30-claude-review-token`, including the doc comment
   explaining WHO can read it and WHY.
2. Mount it into the `arc-org` scale set as a file with mode 0400, and configure
   the buildx endpoint. The runner needs an ssh alias so `ssh://` finds the key.
3. Documentation, so the next reader knows how this works without reverse
   engineering it.

## The durable half — a check that stops the class

An ExternalSecret can name a vault item that does not exist, and NOTHING catches
it. That already happened tonight: the mini enrolment shipped
`shared/macos-ci-runner/account-credentials`, which never existed, and only a
manual vault query found it.

Worse, the provider resolves by SEARCH and takes `$.data.data[0]` — the FIRST
match. Two items whose names share a substring are silently ambiguous, and the
wrong secret is delivered with no error anywhere.

So: every `remoteRef.key` in the repo must resolve to EXACTLY ONE vault item.
Not zero (the secret never materialises), not two (the wrong one might).

## Deliberately NOT in this change

- Reversing D42 in the image workflows. That is a `.devcontainer` change and it
  should land only after this builder is proven in CI.
- Registering the Actions runner on the mini. A buildx node serves builds over
  SSH without ever being a runner; the two paths are independent.
- Per-label runner floors, and anything in the queue verb (#172).

## Proven

Everything under MEASURED and the credential design above. Nothing about the
manifests yet — phase 2 owes a RED test.

## Blocked

Nothing.

## Next

Test author: red tests for the mount and for the vault-item resolution check.


## Phase 2/3 — RED then GREEN, and one finding that would have broken the first build

```
verify-buildx-key   pass=9 fail=0   rc=0
verify-vault-refs   pass=11 fail=0  rc=0     (10 before, 11 now)
ctl.sh validate     rc=0            6 project.json, 21 scripts, shellcheck strict
kubeconform         122 resources / 93 files, Invalid 0, Errors 0
```

**THE VAULT ITEM'S LAST BYTE IS NOT A NEWLINE.** OpenSSH matches its end marker
WITH the newline, so a key without one is refused. Proven with a throwaway key:
`ssh-keygen -y` exits 255, `invalid format`. A plain passthrough would have
shipped a Secret that ssh rejects at the first build, and the failure would have
looked like a permissions or network problem. The ExternalSecret therefore
templates `{{ .privateKey | trim }}` plus exactly one newline — idempotent, and
it survives a re-paste of the vault item.

**kubeconform SKIPS the Argo `Application`**, so nothing in this repo had ever
validated the pod spec that lives inside its Helm values. Extracted and run
through `kubectl create --dry-run=client`: rc=0, and `defaultMode` resolves to
**256**, which is `0400`. `yq -o=json` reports the same scalar as `400`. The trap
the test author measured is real and it was avoided.

**The credential path is proven in the REAL runner image**, not inferred. Inside
`ghcr.io/gophersys/base-runner:e0c6bc5`, with the key installed exactly as the
kubelet projects it (`root:root 400`):

```
docker -H ssh://macos-buildx version  ->  28.1.1 arm64 linux   rc=0
```

A fresh-pod case was also proven: a client with no local buildx metadata reused
the existing remote buildkit container AND its cache (second build reported
`CACHED`), rc=0.

## BLOCKED — the runner image has no buildx

Measured against the pinned image, and confirmed independently by me:

```
docker run --rm ghcr.io/gophersys/base-runner:e0c6bc5 ...
  /usr/local/lib/docker/cli-plugins:  docker-compose      <- buildx ABSENT
  docker buildx version -> docker: unknown command
```

`base/Dockerfile` installs `docker-ce-cli` and then downloads ONLY the compose
plugin (lines 493-496). buildx ships as a separate `docker-buildx-plugin`
package. So the documented workflow step CANNOT RUN today.

The implementer deliberately did not work around it by downloading buildx inside
the job, citing `ci-substrate.md`'s own rule that software capability belongs in
the image, and the fact that `validate.yml` has no tool-install step for exactly
that reason. That was the right call and it is why this is a blocker rather than
a silent hack.

The fix is one line in a DIFFERENT repository, `gophersys/.devcontainer`.

## DECIDED — the volume stays REQUIRED, not `optional: true`

The implementer asked for a second opinion and picked the strict reading. I agree,
and I am recording why so it is not re-litigated:

- `optional: true` would let a runner pod start with NO key and fail at build
  time, which reads as a build problem rather than a broken vault link. That is
  the false-green shape this whole night has been about.
- required means the pod waits in `ContainerCreating` and the kubelet retries, so
  it SELF-HEALS within seconds once ESO syncs. The window is small and loud.
- it matches the `ghcr-pull` precedent, which is also required and has the same
  org-wide blast radius.

## Deliberately NOT in this change

- Reversing D42. No image workflow's platform list was touched.
- Registering an Actions runner on the mini.
- The 51 pre-existing kubeconform errors under `charts/`, `clusters/`,
  `machines/` and `contracts/` (missing `kind`, duplicate `env` keys in 5 chart
  values files). CI never scans those roots, so they are invisible today. Not
  caused by this change — but they are a real finding and they need their own task.

## Unverified

The ESO template rendering itself. `{{ .privateKey | trim }}` uses sprig, which
the `ghcr-pull` sibling already relies on, and `mergePolicy` defaults to Replace —
but there is no cluster run to prove it. Check the materialised Secret's size at
first sync.

## Next

Unblock the image: add buildx to `gophersys/.devcontainer` base/Dockerfile.
