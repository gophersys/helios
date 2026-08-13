# mini-buildx

phase:    plan
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
