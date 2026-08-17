# download-checksums

phase:    fix
repo:     gophersys/.devcontainer
branch:   ci/download-checksums
worktree: ~/code/.worktrees/.devcontainer-checksums
pr:       -
attempt:  1/2

## Goal
Every binary download in every image verifies a sha256 (43 rows, one arch
vocabulary _SHA256_AMD64/_NOARCH, one fetch-verified.sh helper, 9 stated
exemptions), and a download without its digest row cannot build. F2 PR2 of
ledger #100.

## Plan
Approved under standing-orders §4 delegation with ONE amendment. Full plan:
tasks/a827511a1ce33365a.output. Amendment (the plan's open question — where
the pre-merge all-6-image build runs): NOT 6 QEMU-hours on this mac. The
pre-merge proof is instead (a) the digest generator verifies every asset at
fetch time — 43/43 by construction; (b) a PROBE build exercising the
fetch-verified wiring once per pattern (base ARG-home, cloud versions.env
home, a _delta component, one sole-home Dockerfile); (c) the post-merge main
build as the full-wiring proof — acceptable because the publish order gates
smoke BEFORE push, so a broken digest reds main without shipping anything.
Key plan decisions: helper is ONE file _build/fetch-verified.sh (bash
shebang, executed not sourced); vocabulary migration X86_64->AMD64 value-
unchanged + the 4 arm rows deleted with their case arms (F3 restores both
deliberately); exemptions in _build/download-exemptions.txt with stated
classes; evidence comment per row (upstream-published vs computed-at-pin);
smoke classifies *_SHA256_* by shape.

## Proven
- RED (1ad546b): 16 files, 378 checks, 16 intended fails (56 unclassified
  fetch sites named; helper/exemptions absent; legacy vocab; missing
  evidence comments). Every ratchet proven can-fail by reverted mutation;
  2 self-caught test defects fixed before belief.
- GREEN (5 commits to c888dd2): 378/0; validate rc=0; 46 digest rows
  (32 upstream-published, 14 computed-at-pin) sourced by a generator reading
  URL templates out of the Dockerfile lines; probe builds: positive rc=0,
  wrong-digest rc=1 naming the pin, unset-pin rc=1 at the gate; hadolint/gh/
  k9s upstream checksum files agreed; legacy vocab migration value-identical.
- GAP 2 resolved by decision: AWS CLI removed from base on the terraform
  precedent (1f65b93); smoke listings re-proven coherent by execution.
- VERIFIER round 1 (2026-08-17): 9 assets independently re-fetched 9/9
  MATCH; 18/18 evidence URLs confirm; helper red-teamed (404/SIGTERM/
  mismatch all leave nothing, EXIT trap proven); routing swept independently
  55 = 46 verified + 9 exempt. NO-GO on 3 mechanical items -> this fix
  round: (1) COPY _build/ wiring unguarded by any static test -> test
  author; (2) THIS file was 3 phases stale -> fixed here, orchestrator's
  second such miss this program; (3) three false counts in comments ->
  implementer + test author. Non-blocking residue -> ledger #108.

## Next
Fix round: test author (COPY assertion + its 2 stale test comments),
implementer (2 count fixes + the Go evidence URL &include=all). Then PR with
the post-merge-proof list verbatim.

## Blocked
Landing waits behind the CVE-round rebuild (run 32004858893) + the nightly
green/close-#44 proof. Test authoring is not blocked.

## Next
dev-test-author: the 4 new/widened red suites (download-coverage both
directions + fixtures, same-home+evidence rule, dockerfile-args widening,
fetch-verified.test.sh over file:// fixtures) proven red for the right
reasons.
