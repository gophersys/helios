# security-nightly

phase:    fix
repo:     gophersys/.devcontainer
branch:   ci/security-nightly
worktree: ~/code/.worktrees/.devcontainer-security-nightly
pr:       -
attempt:  1/2

## Goal
Nightly trivy scan of the 6 published images (CRITICAL fails, fixed or unfixed;
waivers carry id+reason+expiry), failure lands as ONE auto-filed issue that a
green run closes, and the base OS moves from a floating ubuntu:24.04 tag to a
digest pin (UBUNTU_BASE_REF in both pin homes) whose drift the nightly reports.

## Plan
Approved under standing-orders §4 delegation. Full plan:
tasks/a6f8076b3e0cc64e3.output. Decisions: digest pin + bump PR; CRITICAL-only
day 1; ONE issue notifier; provider cmp widened to every provider file;
checksums = PR2; weekly bumps = PR3; Renovate rejected (5 reasons).

## Proven
- RED (9681c0b): 12 files, 221 checks, 24 intended fails (workflow absent,
  notifier absent, waivers absent, floating FROM, empty pin homes, undeclared
  lib functions); every green ratchet proven by reverted mutation; waiver
  schema verified against trivy docs (loads only when named -> extra clause).
- GREEN (1894b75, 985e4c9, 6d3bc07): 236 checks 0 failed; validate rc=0;
  cmp both provider pairs rc=0; INDEX digest 561618e2... proven by manifest
  inspect (6 platforms) + pull + 2 probe builds printing Ubuntu 24.04.4;
  base-currency verb rc=0 live; notifier fail-loud drills incl. real 401.
- ORCHESTRATOR NOTE: this Proven section was backfilled AFTER the verifier
  found it empty (its finding 4) — the phase updates lagged the commits.
  Process defect owned by the orchestrator, corrected here.

## Verifier round 1 (2026-08-16) — 4 blocking
1. BOTH workflow copies are INVALID YAML (line 139 col 52: unquoted run:
   scalar with ": ") — the workflow would never run; survived because nothing
   parses workflow YAML (finding 5). -> implementer.
2. The notify job's always()+verdict-reduction shape is held by NO test —
   deleting the verdict step makes a red night CLOSE the issue, suite green.
   -> test author.
3. The scan matrix is a 5th hand-written image-set declaration; narrowing it
   to [base] drops 5 images from the security gate, suite green. -> test
   author (tie to BUILD_ORDER, the one declaration).
4. State file stale — owned + fixed above.
Non-blocking -> this fix round: 5 (validate parses no YAML -> yq parse loop,
implementer + hermetic test), 7 (duplicate issue never closed: drop --limit 1,
close every match), 8 (cancelled run files a red issue — one comment line),
9 (3 contradictory clock comments). 6 (anonymous Docker Hub rate limit on
base-currency) = accept + name in PR body as first-run-measured.
Could-not-refute: 6 break-drills red correctly; index digest live-verified;
trivy 0.74.0 empty-ignorefile accepted (verified by SOURCE, not execution);
action pinning matches convention; no masked exit codes.

## Blocked
Landing order: fix/first-run-smoke-defects (red main) lands FIRST, then this
branch rebases if needed. #104 resolved: 4/6 bodies passed; flutter+devbox
failures are that fix lane's subject.

## Next
Fix round: test author reds for findings 2+3+5, then implementer greens
1+5+7+8+9, then re-verify (bounded), then PR.
