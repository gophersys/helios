# warmer-cp-exclusion

phase:    intake
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
(pending phase 1. Known constraints for the planner: the manifest ALREADY has a
scheduling affinity — "mirrors the runner pools exactly (NotIn k3s-w-4)" — so the fix
extends the existing NotIn list, not adds a mechanism; scripts/verify-warmer-pins.sh
couples 4 files to one pin value; 43-image-warmer-refresh.yaml rollout-restarts daily
at 03:30 UTC, which makes imagePullPolicy Always on warm-cloud-latest LOAD-BEARING
for :latest freshness — the original brief's "drop Always" half is likely WRONG and
the planner must weigh it (strand cost is GC-able once CPs are excluded); repo rules
00/20/50 apply; live cluster verification allowed read-only + watching Argo.)

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
