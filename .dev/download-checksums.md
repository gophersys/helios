# download-checksums

phase:    red
repo:     gophersys/.devcontainer
branch:   ci/download-checksums
worktree: ~/code/.worktrees/.devcontainer-checksums
pr:       -
attempt:  0/2

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
(nothing yet)

## Blocked
Landing waits behind the CVE-round rebuild (run 32004858893) + the nightly
green/close-#44 proof. Test authoring is not blocked.

## Next
dev-test-author: the 4 new/widened red suites (download-coverage both
directions + fixtures, same-home+evidence rule, dockerfile-args widening,
fetch-verified.test.sh over file:// fixtures) proven red for the right
reasons.
