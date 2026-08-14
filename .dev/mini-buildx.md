# mini-buildx

phase:    BLOCKED — do not merge
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


## DO NOT MERGE — two blocking findings, both mine

A 10-agent consolidation audit found two defects in decisions I made and stated as
proven. Both are recorded here so the branch cannot be picked up and landed by
someone reading only the green checks.

### BLOCKER 1 (SECURITY) — the "dial-only" key grants root on the mini's Docker VM

I reported the key "grants a BuildKit dial and nothing else", proven four ways.
The four tests were correct and IRRELEVANT to the real surface. Confirmed by
direct measurement:

```
ssh exec / scp / sftp / -L / -R          blocked      <- the four I tested
docker run --privileged --pid=host       "I am root"  rc=0
docker run -v /:/host:ro  ls /host/etc/shadow         CAN read the VM root filesystem
```

The forced command hands the caller the **Docker Engine API**, which is
root-equivalent by design. Docker has no meaningful authorization model — you
either reach the socket or you do not. And this branch mounts that key into the
GENERAL `arc-org` pool, which every repository shares, including pull-request
builds. The "dial-only" framing is exactly what made that feel acceptable.

**The fix is architectural.** Run standalone `buildkitd` on the mini and connect
buildx over TCP with mTLS (`--driver remote`), exposing the BUILD API and never
the Engine API. That is the honest version of what I claimed to have built, and it
also removes the Docker Desktop GUI dependency that forced the auto-login +
LaunchAgent stack.

Filed as task #66. No live exposure: `kubectl get secret macos-buildx-key -n
arc-runners` -> NotFound, and the vault item is consumed by nothing.

### BLOCKER 2 (AVAILABILITY) — the required volume can stop ALL CI, with no ordering to prevent it

I decided the volume stays REQUIRED rather than `optional: true`, reasoning that a
missing secret should block the pod and that it "self-heals within seconds once
ESO syncs". **That assumed the ExternalSecret exists by then. Nothing guarantees
it does.**

The ExternalSecret is applied by a DIFFERENT Argo Application
(`app-arc-netpol.yaml`, path `platform/services/ci/arc-runners`) from the pool
Application, and:

```
grep -rn 'sync-wave' platform/services/gitops/registry/   -> nothing
```

There is no ordering anywhere in the registry. If the pool syncs first, every
runner pod in the org fails to start, ALL CI stops, and the tool you would use to
diagnose and fix it is CI. No branch states a rollback.

It compounds: the ESO template has never executed against the live vault. The
newline fix is proven only by an offline sprig render plus a source read of ESO
v1.3.2 from the module proxy, and nobody confirmed which ESO version the cluster
actually runs.

**Before this lands, in order:**
1. Prove the render OUT OF BAND — one throwaway ExternalSecret in a scratch
   namespace against the same vault item, then check the materialised secret's
   LENGTH (`| base64 -d | wc -c`), never echoing the value.
2. Either mark the volume `optional: true`, or put an explicit sync-wave on the
   ExternalSecret Application ahead of the pool Application — and prove the
   ordering, not assume it.
3. State the rollback.

### Also from the audit, not blocking but true

`docs/ci-substrate.md` presents pod runtime behaviour as measured fact ("the key
as the kubelet projects it | root:root 0400 — ssh accepted it"). No kubelet has
ever projected that key. The check was a `docker run` simulating the projection,
which is reasonable evidence and MUST be described as what it is.

## Next

Do not resume this branch until the credential design is settled. That decision is
Mateo's — it is a security posture question, not an implementation detail.


## REBUILT 2026-08-14 — buildkitd over mTLS, and the root hole is CLOSED (Mateo: "rebuild it")

The SSH-key design was found to grant root on the mini's Docker VM (task #66) and
was rebuilt as a standalone `buildkitd` exposing the BUILD API only. Built and
PROVEN live on the mini:

```
arm64 build through the remote builder   rc=0, 9.3s
no client cert                            rc=1 refused (mTLS enforced)
docker -H tcp://10.168.0.92:1234 version   error — NO Engine API on the port
docker -H tcp://... run --privileged --pid=host   error, NOT "pwned" — the old escape is DEAD
docker buildx build --allow security.insecure    rc=1, "entitlement security.insecure is not allowed"
```

The client cert can submit only SANDBOXED builds. No Engine API, no privileged
steps, no host access.

### THE RUNBOOK — reproduce the mini's buildkitd from scratch (cite this in the doc)

```sh
# 1. certs (on any machine with openssl)
openssl genrsa -out ca-key.pem 4096
openssl req -new -x509 -days 3650 -key ca-key.pem -sha256 -out ca.pem -subj "/CN=eden-buildkit-ca"
openssl genrsa -out daemon-key.pem 4096
openssl req -new -key daemon-key.pem -out daemon.csr -subj "/CN=macos-ci-runner"
# server SAN MUST carry the mini's IP — buildx verifies the cert against tcp://10.168.0.92
printf 'subjectAltName=IP:10.168.0.92,IP:127.0.0.1,DNS:macos-ci-runner
extendedKeyUsage=serverAuth
' > d.cnf
openssl x509 -req -days 3650 -in daemon.csr -CA ca.pem -CAkey ca-key.pem -CAcreateserial -out daemon.pem -sha256 -extfile d.cnf
openssl genrsa -out client-key.pem 4096
openssl req -new -key client-key.pem -out client.csr -subj "/CN=eden-ci-buildx-client"
printf 'extendedKeyUsage=clientAuth
' > c.cnf
openssl x509 -req -days 3650 -in client.csr -CA ca.pem -CAkey ca-key.pem -CAcreateserial -out client.pem -sha256 -extfile c.cnf

# 2. on the mini — the cred helper must be on PATH, and Docker Desktop file-sharing
#    rejects a bind mount of a home path, so seed a VOLUME via docker cp:
export PATH="/Applications/Docker.app/Contents/Resources/bin:$HOME/bin:$PATH"
docker volume create eden-bk-certs
docker create --name bkseed --entrypoint /bin/sh -v eden-bk-certs:/certs moby/buildkit:latest
docker cp ca.pem bkseed:/certs/ ; docker cp daemon.pem bkseed:/certs/ ; docker cp daemon-key.pem bkseed:/certs/
docker rm bkseed
docker run -d --name eden-buildkitd --restart unless-stopped --privileged -p 1234:1234   -v eden-bk-certs:/certs:ro moby/buildkit:latest --addr tcp://0.0.0.0:1234   --tlscacert /certs/ca.pem --tlscert /certs/daemon.pem --tlskey /certs/daemon-key.pem

# 3. client (CI, or any host with the 3 client-side certs)
docker buildx create --name eden-mini --driver remote   --driver-opt cacert=ca.pem,cert=client.pem,key=client-key.pem tcp://10.168.0.92:1234
```

Survives reboot via `--restart unless-stopped` + the Docker-autostart chain
(LaunchAgent `com.gophersys.docker-autostart` + auto-login). Confirmed running
policy=unless-stopped.

### Secrets

Vault: `shared/eden/buildkit-client-{ca,cert,key}` created, one match each. Old
root-granting `shared/eden/macos-buildx-key` DELETED, SSH dial key revoked from the
mini's authorized_keys. Admin key `shared/ssh/macos-ci-runner` kept.

### The `verify-buildx-key` suite will go RED — correctly

It asserts the OLD SSH-mount design. After the implementer's rework it fails
because the design changed; a test author rewrites it for the cert design. That
red is expected evidence, not a defect.


## Branch rework COMPLETE (`6ba6918`) — cert design wired, docs rewritten

Red first (honest): `verify-vault-refs` rc=1, the branch still named the DELETED
`shared/eden/macos-buildx-key`. Green after: rc=0, the three `buildkit-client-*`
items each resolve to one item.

- NEW `40-buildkit-client-certs-externalsecret.yaml` — 3 items -> one Secret with
  ca.pem/cert.pem/key.pem. DELETED the old macos-buildx-key ExternalSecret.
- arc-org mounts the cert Secret read-only at `/etc/buildkit-certs`, mode 0400
  (dry-run confirms 256 = 0o400).
- ALL docs rewritten: ci-substrate.md (security-model table + the 4 proofs + the
  --driver remote step + autostart dependency), the machine README, identity.yaml,
  and a NEW buildkitd-runbook.md.

`validate` rc=0, kubeconform rc=0 on CI roots, no secret material in the diff.

### ARC-ORG PLACEMENT — implementer's position, which I endorse

**Keep it on arc-org.** The client cert reaches only the BUILD API over mTLS —
no Engine API, no privileged, no insecure, all proven on the mini. That is a
different risk class from the old Engine-API key, and the pool is already closed
to public repos so a fork PR cannot reach the mini. Stated in the manifest comment
and docs, not silent. FINAL CALL IS MATEO'S because every repo on the pool then
shares one builder.

### TWO BLOCKERS before this can be switched on (both Mateo's rollout call)

1. **verify-buildx-key is RED** — it asserts the old SSH-mount design and makes the
   CI `manifests` job red. Being rewritten now for the cert design (test author).
   That red is expected evidence the design changed, not a defect.
2. **The runner image needs buildx AND arc-org must pin a buildx-carrying image.**
   `.devcontainer` #33 published base-runner WITH buildx (c69ffee), but arc-org is
   pinned to the pre-buildx e0c6bc5. The `--driver remote` step needs buildx on the
   runner, so arc-org's pin must be bumped. That is the pin-bump/rollout piece,
   which is D42 territory and Mateo's decision.

## Next

Test author: rewrite verify-buildx-key for the cert design (make the branch green).
Then the branch is READY, and its merge is Mateo's — pool placement + the arc-org
pin bump + D42.
