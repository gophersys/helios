# weekly-bumps

phase:    fix
repo:     gophersys/.devcontainer
branch:   ci/weekly-bumps
worktree: ~/code/.worktrees/.devcontainer-weekly-bumps
pr:       -
attempt:  1/2

## Goal
A weekly workflow resolves every pin's upstream (one table _build/upstreams.txt,
one resolver _build/resolve-upstream.sh with one function per datasource, 11+
no-autobump=12) and opens ONE gated bump PR where anything moved — version and
sha256 from the SAME fetch, re-proven by fetch-verified.sh before writing, so a
stale digest is impossible by construction. Failures file a ci-weekly-red issue
via the parameterized notifier. The last piece of ledger #100.

## Plan
Approved under standing-orders §4 delegation, 2026-08-17, WITH the fallback as
day-1 state for the one open credential: the 3 harness pins (claude/omp/codex)
take no-autobump ("eden harness-upgrade-check is the one decision point; the
cross-repo read needs EDEN_MANIFEST_READ, a fine-grained PAT only Mateo can
mint — NEEDS-MATEO item 16"); the eden-manifest datasource ships ready and
FAILS NAMING THE SECRET if selected while it is absent. Full plan:
tasks/a692df0b23121fdae.output. Planner's premise corrections accepted: PR#48
shipped no generator (the resolver is the FIRST digest-computing home);
dual-home version equality needs a NEW static rule (only UBUNTU_BASE_REF held
today). 12 datasources incl. no-autobump (9 pins); readers fetch_urls/
evidence_of/homes_of MOVE from download-coverage.test.sh into _ctl/lib.sh
(move, not copy); notifier ISSUE_LABEL parameterized (weekly=ci-weekly-red,
a green weekly must not close nightly issues).

## Proven
- RED (9109d07): 19 files, 475 checks, 54 intended fails; every detector
  watched firing AND staying quiet; in-container byte-identical verdicts.
  Spec 7 proved LIVE that the hardcoded notifier label closes the NIGHTLY
  issue when run as the weekly.
- GREEN (5 commits): 484 checks, 1 failed = the DESIGNED free ratchet
  (EXPECTED_PROVIDER_FILES lacks weekly-bumps.yml — test-file, next round).
  pin-mirroring 26/0, resolve-upstream 43/0, upstream-coverage 19/0,
  download-coverage untouched 62/0. validate rc=0; shellcheck rc=0; yq both
  copies rc=0; cmp pair rc=0. Hermetic --dry-run: 12 movers, porcelain
  empty; --apply wrote the 5 fixture digests into both rows.
- ADVERSARIAL EXTRA: all 43 resolvable REAL rows driven through the real
  resolver with stub upstream -> 43/0; caught + fixed a real defect
  (CODE_SERVER ${ARCH} from dpkg --print-architecture, not a case arm).
- Implementer findings: no-autobump truth is 13 (JAVA_VERSION joins — the
  JDK major inside a package name); the weekly's bump PR starts NO checks
  under GITHUB_TOKEN (GitHub suppresses token-caused events) — human
  close/reopen documented in-workflow + docs; durable fix = a PAT/App,
  NEEDS-MATEO item 17.

## Blocked
Nothing. The PR#48 wiring-proof build was 5/6 green at intake (devbox
finishing); landing order unaffected.

## Verifier round 1 (2026-08-17) — NO-GO, 2 blocking
B1: no inherit_errexit — fail_pin's exit 1 dies inside $( ) and the
aggregate --dry-run/--apply path SWALLOWS failures (rc=0 with an empty-
version bump line; --apply leaves a partial write) — the exact defect the
file header claims impossible; the suite is structurally blind (every
failure spec is single-pin). B2: 3 dead coordinates proven on the REAL
network: BW (bitwarden multi-product stream — releases/latest = web vault;
cli asset 404), CICTL + HNSLINT (our own repos: tags, ZERO GitHub
Releases — releases/latest 404 forever, while cictl sits 4 releases
behind). N1 Android cmdline index EXISTS (repository2-3.xml, newest
15859902) — the no-autobump reason is false; N2 oci-index never asserts
index media type; N3 job timeout files no issue (single-job failure()
shape) + assets fetched twice (~3.1GB flutter alone) vs "a handful"
comment; N4 three doc untruths incl. OpenJDK 17-vs-21; N5 this file was
stale again (fixed here). 24 attack lines REFUTED incl. 4 clean drills.

## Next
Fix round (attempt 1): test author RED spec — aggregate --dry-run with one
failing row must exit non-zero naming the pin, no bump line with an empty
version (red against current code = proves B1). Then implementer:
inherit_errexit (+ substitution status checks), the 3 rows corrected with
true classes, N1-N4. Then bounded re-verify, then PR.
