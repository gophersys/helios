# bw-serve-auto-sync

phase:    wait
repo:     gophersys/infrastructure
branch:   feat/bw-serve-auto-sync
worktree: ~/code/.worktrees/infrastructure-bw-serve-auto-sync
pr:       183
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

PLAN AMENDED after the adversarial verify (recorded, with why): the verifier
refuted 4 claims, so the change grew by exactly their remedies —
- F1 (HIGH): "fail-loud" overstated. No observability stack exists in this
  cluster; a Failed Job alerts nobody (D16 already records the unobserved-
  CronJob gap). Remedy: comment + README state the honest limit; the CronJob
  is registered inside D16.
- F2 (HIGH): no standing gate covered the wiring. The verifier proved a
  netpol-selector typo, a wrong port, AND a `|| true` in the job script pass
  kubeconform + server dry-run + ctl.sh validate. Remedy:
  scripts/verify-bw-sync-wiring.sh (11 property assertions), ctl.sh
  `verify-bw-sync`, and a validate.yml step — precedent
  scripts/verify-buildx-key.sh.
- F3 (MED): a third "only ESO reaches the bridge" claim survived in the
  security paragraph of the manifests README. Corrected.
- F4 (MED): no dedicated ServiceAccount (rule 50 §7). Added, with
  automountServiceAccountToken: false on both the SA and the pod.
- F6 (LOW): docs/cluster-topology.md external-secrets section gains the
  CronJob. F7 (INFO): the success grep is now spacing-tolerant.
Process defect, recorded: the first break-test restore (`git checkout --`)
discarded the then-uncommitted F1/F4/F7 manifest edits — the exact trap the
skill names. Re-applied, then committed BEFORE the remaining break-tests.

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
- Adversarial verify (dev-verifier, read-only + reversible breaks): fail-loud
  shell chain survived a 9-case matrix run byte-exact in
  `curlimages/curl:8.11.0` (200+success rc=0; success:false rc=1; 500/401
  rc=22; hang rc=28; DNS fail rc=6; truncated rc=18; empty rc=1); image uid
  100/gid 101 verified by running the image; AppProject `platform` allows
  `group:*, kind:*` in external-secrets, so CronJob is admitted.
- verify-bw-sync-wiring break-tests, each restored after: selector typo
  `bw-serve-synk` → rc=1 "the Job pod labels do not carry: app=bw-serve-synk";
  netpol port 9999 → rc=1 "port mismatch: NetworkPolicy=9999 container=8087
  Service=8087"; `|| true` appended to the job's grep → rc=1 "the job script
  contains '|| true'". Clean run: rc=0, "pass=11 fail=0". The same three
  sabotages had passed kubeconform + server dry-run + validate (the F2
  refutation), so this check demonstrably closes a real hole.
- Full CI parity after the fixes, every script from validate.yml run locally:
  lint-manifests rc=0, test-lint-manifests rc=0, verify-registry-paths rc=0,
  verify-structure rc=0, verify-buildx-key rc=0, test-verify-runner-queue
  rc=0, lint-shell rc=0, test-lint-shell rc=0, verify-bw-sync-wiring rc=0,
  kustomize x3 rc=0, qbt config-enforce + drift rc=0, verify-exposure rc=0
  ("checked=11 fail=0"). `bash ctl.sh validate` rc=0; `bash ctl.sh
  verify-bw-sync` rc=0. shellcheck first caught SC2015 in the new script
  (lint-shell rc=1) — fixed to if/else, re-run rc=0.
- `kubectl apply --dry-run=server -f bw-serve-sync.yaml` re-run after fixes:
  rc=0 — serviceaccount, cronjob, networkpolicy all "created (server dry
  run)".
- Hardened grep vs the recorded live body:
  `grep -Eq '"success"[[:space:]]*:[[:space:]]*true'` rc=0.

## Blocked

- (nothing)

## Next

Open the PR, wait for checks + the pr-review verdict, address findings.
DO NOT MERGE — directive. Mateo merges.
