# security-nightly

phase:    red
repo:     gophersys/.devcontainer
branch:   ci/security-nightly
worktree: ~/code/.worktrees/.devcontainer-security-nightly
pr:       -
attempt:  0/2

## Goal
Nightly trivy scan of the 6 published images (CRITICAL fails, fixed or unfixed;
waivers carry id+reason+expiry), failure lands as ONE auto-filed issue that a
green run closes, and the base OS moves from a floating ubuntu:24.04 tag to a
digest pin (UBUNTU_BASE_REF in both pin homes) whose drift the nightly reports.
:latest stays gated by the F1 publish order. Mateo: "nightly weekly updates on
images", "i need correctness".

## Plan
Approved by the orchestrator under standing-orders §4 delegation (Mateo away),
2026-08-16. Full plan: tasks/a6f8076b3e0cc64e3.output. Key decisions: digest
pin + bump PR (never a nightly republish — the commit decides the image);
CRITICAL-only gate day 1 (HIGH needs a measured count first, via
workflow_dispatch); notify-failure.sh = ONE issue opened/updated on red,
closed on green; provider copy cmp widened to EVERY .ci/providers/github file;
checksums = PR 2; weekly bumps + eden-manifest coupling = PR 3; Renovate
REJECTED (5 reasons recorded in the plan). First nightly run is probably red —
that red IS the CVE measurement.

## Proven
(nothing yet)

## Blocked
Landing waits for the #104 watch run (main build of abf4d39) to finish green.
Development is not blocked.

## Next
dev-test-author writes the 6 red tests from the plan (notification ratchet,
provider cmp widening, trivy-gate flags, waiver expiry+reason, digest-pin FROM
lines, base_image_digest drift through the docker stub) and proves each fails
for the right reason. version-coverage red on UBUNTU_BASE_REF comes free.
