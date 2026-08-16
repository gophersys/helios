# bw-serve-auto-sync

phase:    verify
repo:     gophersys/infrastructure
branch:   feat/bw-serve-auto-sync
worktree: ~/code/.worktrees/infrastructure-bw-serve-auto-sync
pr:       -
attempt:  0/2

## Goal

The bw-serve bridge (ESO's Bitwarden read bridge) caches the vault at login and
never syncs again on its own. A new or rotated Vaultwarden item stays invisible
to ESO until the pod restarts. That broke the arc-netpol work for a day (build
ledger #89): the item existed, the cache was 4 days stale. When this is done, a
CronJob in the external-secrets namespace sends POST /sync to the bridge every
10 minutes, fail-loud, so the cache is at most 10 minutes old.

## Plan

plan: PRE-APPROVED — program authority Mateo 2026-08-17 "build everything on
the todo list" (build ledger #89), with the fix fully specified by the
directive. The one risk weighed: ingress to bw-serve is default-denied with
only ESO allowed (live-verified: netpols `bw-serve-default-deny`,
`bw-serve-allow-eso` in external-secrets), so the CronJob needs its own
ingress allow or it fails every 10 minutes forever. The manifest therefore
carries both the CronJob and a `bw-serve-allow-sync` NetworkPolicy.

Files:
- `platform/core/secrets-operator/manifests/bw-serve-sync.yaml` — NEW: CronJob
  (every 10 min, POST /sync, restartPolicy Never, backoffLimit 1, no || true)
  + NetworkPolicy allowing the job's pods to reach bw-serve:8087.
- `platform/core/secrets-operator/manifests/networkpolicy.yaml` — comment only:
  "ONLY the ESO controllers" is no longer the whole truth.
- `platform/core/secrets-operator/manifests/README.md` — Files list + the same
  "only ESO" sentence.

Image: `curlimages/curl:8.11.0`. Rule 50 §7 allowlists "the official
upstreams"; curl.se publishes curlimages/curl as the curl project's official
image, and the estate already runs this exact image and tag on main
(`apps/music/qbittorrent/20-deployment.yaml`, port-sync sidecar). Defensible
and precedented.

Argo ownership (live-verified): Application `secrets-bridge` (argocd ns) syncs
`platform/core/secrets-operator/manifests` with automated selfHeal — a new
file in that path deploys on merge with no registry change.

Not included, deliberately: no merge (directive says DO NOT MERGE); no rewrite
of the stale "Status and findings (2026-07-05)" section of the manifests
README (pre-existing staleness, named in the PR); no change to ESO
refreshInterval semantics (an ExternalSecret still refetches on its own
interval after the bridge syncs).

Process note: no test files exist for a raw-manifest change — the repo's gates
(kubeconform via scripts/lint-manifests.sh, which explicitly roots this path)
are the tests. Red = prove the gate fails on a broken version of the new file;
green = the real file passes. Single-file change, subagent file-class split
collapses; dev-verifier still runs adversarially before the PR.

## Proven

- RED — `bash scripts/lint-manifests.sh` with a deliberately broken
  bw-serve-sync.yaml (`schedules:` for `schedule:`): rc=1, output named the
  file — "CronJob bw-serve-sync is invalid: … missing property 'schedule' …
  additional properties 'schedules' not allowed". The gate can fail on this
  file class, for the right reason.
- GREEN — `bash scripts/lint-manifests.sh` with the real manifest: rc=0,
  "Summary: 128 resources found in 96 files - Valid: 90, Invalid: 0" (+2
  resources vs the red baseline's 88 valid: the CronJob and the NetworkPolicy).
- `bash ctl.sh validate`: rc=0 — "validate: OK" (28 shell scripts linted,
  6 project.json parsed).
- `bash ctl.sh verify-registry`: rc=0 — "checked=19 skipped=0 fail=0".
- `kubectl apply --dry-run=server -f platform/core/secrets-operator/manifests/bw-serve-sync.yaml`:
  rc=0 — "cronjob.batch/bw-serve-sync created (server dry run)",
  "networkpolicy.networking.k8s.io/bw-serve-allow-sync created (server dry
  run)". Live API server accepts both objects.
- Endpoint contract — one `curl -fsS --max-time 60 -X POST /sync` through
  `kubectl port-forward svc/bw-serve` (1 request, under the ~10 req/s vault
  rate limit): rc=0, body
  `{"success":true,"data":{...,"title":"Syncing complete."}}` — the job's
  `grep -q '"success":true'` matches the real response.
- Live prerequisites — `kubectl get app secrets-bridge -n argocd`: path
  `platform/core/secrets-operator/manifests`, automated selfHeal (a new file
  in the path deploys on merge). `kubectl get netpol -n external-secrets`:
  only `bw-serve-default-deny` + `bw-serve-allow-eso` existed, confirming the
  sync job needs its own allow.

## Blocked

- (nothing)

## Next

Adversarial verify (dev-verifier), then PR. DO NOT MERGE — directive.
