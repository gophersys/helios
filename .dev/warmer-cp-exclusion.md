# warmer-cp-exclusion

phase:    red
repo:     gophersys/infrastructure
branch:   fix/warmer-cp-exclusion
worktree: ~/code/.worktrees/infrastructure-warmer-cp-exclusion
pr:       -
attempt:  0/2

## Goal
The arc-runners ci-image-warmer DaemonSet pins ~3.86GB of unGCable images (its
initContainers run `true`, holding the images "in use" forever) on all schedulable
nodes INCLUDING the three 38GB etcd control planes. Its comment claims no-tolerations
keeps it off tainted control planes — but zero taints exist cluster-wide (verified
live), so the premise is false. k3s-cp-0 hit 93% used / 2.7GB free at 22:31Z while
running etcd; kubelet image GC could not free enough. When this is done: the warmer
never schedules on k3s-cp-0/1/2, the comment tells the truth, and the fix is proven
IN EFFECT — warmer pods gone from the CPs after Argo syncs, image GC reclaims the
cloud images there, df on all three CPs below the 85% GC high-threshold, with numbers.

## Plan
plan: SELF-APPROVED (--auto), FULL scope (pool files included — the minimal version
trades the pin for 2.2GB cold-pulls onto etcd nodes, the planner's named risk).
Risk weighed: runner-eligible nodes drop 7->4 for arc-org/arc-review at maxRunners 4
— inside the measured contention envelope, stated at merge.
- 42-image-warmer-daemonset.yaml + 43-image-warmer-refresh.yaml + app-arc-runners-
  org.yaml:105 + app-arc-runners-review.yaml:68: NotIn gains k3s-cp-0/1/2 (hostnames,
  NOT role labels — cluster_role devops includes w-0, a runner worker; node-role label
  unobserved and unprecedented in-repo). False comments rewritten (42:35-37, 43:12).
- verify-warmer-pins.sh property 3: DERIVE the server set from clusters/instances/
  homelab/nodes/*/identity.yaml (kubernetes.role: server) and assert every derived
  hostname in the NotIn of all 4 files (yq guarded exit-127 for identities; TEXT read
  for the helm values: | blocks); accumulate via fail(), never exit mid-loop (-e absent).
- scripts/test-verify-warmer-pins.sh: NEW fixture suite, 5 cases (CP-EXCLUDED,
  DERIVED-NOT-HARDCODED, ZERO-SERVERS-IS-NOT-A-PASS, REFRESH-COVERED, POOLS-COVERED),
  real script via symlinked ROOT per test-verify-buildx-key.sh convention.
- validate.yml: run the suite in `manifests`, no continue-on-error.
- docs/debt-register.md D45 🟠: declared devops labels/taints exist in git, zero
  applied live, cluster-node-labels Ansible role pending; affinity governs instead.
- VERDICT KEPT: imagePullPolicy Always stays (IfNotPresent freezes :latest; the daily
  refresh exists solely to re-resolve it; superseded digests are GC-able post-change).
- In-effect proof (post-merge): DS desiredNumberScheduled 7->4; zero warmer pods on
  k3s-cp*; crictl shows cloud images with NO holding container (reclaimable); one-time
  `crictl rmi --prune` per CP (NOT during an Argo sync), df before/after recorded —
  GC alone will NOT fire at 57% usage; done-condition = reclaimable + reclaimed once.
  Sync confirmed from DS generation + pod set, never from Application status (D44).
- Out of scope: CP taints (D45 records), LimitRange, Longhorn, journald, base-runner
  layer removal, Ansible label role, arc-build (already pinned In workers).

## Proven
- Diagnosis (agent, 2026-08-18 22:38Z, read-only, raw captures in session scratchpad
  out/*.txt): cp-0 93%→57% after kubelet GC self-rescue at 22:31Z; warmer initContainers
  pin ghcr.io/gophersys/cloud@sha256:9a15... 2.06GB + :latest 1.65GB + dind 0.15GB on
  7/8 nodes; zero taints cluster-wide (kubectl get nodes jsonpath); containerd is
  84-90% of used disk on every node; log rotation healthy; crictl understates real
  image disk ~3.7x.

## Blocked
-

## Next
Phase 1: dev-planner.
