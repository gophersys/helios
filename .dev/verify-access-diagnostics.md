# verify-access-diagnostics

phase:    green
repo:     gophersys/infrastructure
branch:   fix/verify-access-diagnostics
worktree: ~/code/.worktrees/infra-verify-access
pr:       -
attempt:  0/2

## REMINDER: remove .dev BEFORE the PR (infra reviewer flags it); prove gone with git cat-file -e.

## Goal
`scripts/verify-access.sh` (the manual `bash ctl.sh verify-access` diagnostic) has two real defects and
NO tests. Fix both + give it its first test harness: (1) #58 — the flow-form `{...}` parser drops
neither an inline `# comment` nor the `}` before it, corrupting the last field; (2) #56 — probe()
reports "unreachable" for EVERY ssh failure (auth, DNS, refused, timeout), discarding the real cause.
When done: a `{...}` line with a trailing comment parses correctly, and a failed probe names WHY.

## Proven (vs origin/main ea6446d)
- #58: parse() flow branch does `sub(/\}[[:space:]]*$/,"",body)` (strips `}` only at EOL, NO comment
  strip); the block branch does `sub(/#.*$/,"",v)`. So `host: { a: b, method: tailscale-ssh } # note`
  → last value = `tailscale-ssh } # note` → the `case $method` falls to `*) unknown method`. Fails LOUD
  (not a false-green), no current access.yaml triggers it, tool not in CI — hence LOW value but real.
- #56: `probe()` = `ssh … 'echo HN:$(hostname)' 2>&1 | grep -o 'HN:[^ ]*' | head -1`. On failure the ssh
  error (Permission denied / Could not resolve / Connection refused / timed out) is captured by 2>&1 but
  grep finds no HN: → empty → caller prints `unreachable as u@h` for ALL causes. The cause is lost.

## Fix (dev-implementer, scripts/verify-access.sh only)
- #58: change the flow branch `sub(/\}[[:space:]]*$/,"",body)` → `sub(/\}[[:space:]]*(#.*)?$/,"",body)`
  (strip `}` + an optional trailing comment). One line. (A `#` inside a quoted flow value is out of
  scope — the block branch has the same naive strip; keep them consistent.)
- #56: capture probe's full output; on no `HN:`, CLASSIFY the ssh error and return/print the cause so
  the caller can show it. Map at least: `Permission denied`/`publickey` → auth; `Could not resolve`/
  `Name or service not known` → dns; `Connection refused` → refused; `timed out`/`Connection timed out`
  → timeout; `No route to host` → no-route; else → the last stderr line. The caller's `unreachable as
  u@h` line becomes `unreachable (<cause>) as u@h`. Keep bash 3.2-safe, shellcheck-clean, keep the
  IdentitiesOnly/BatchMode/ConnectTimeout flags + the hostname-match check unchanged.

## Test (dev-test-author, NEW scripts/test-verify-access.sh — the tool's FIRST test)
Mirror test-lint-shell.sh's idiom. Run the REAL verify-access.sh end-to-end against a mktemp fixture
`access.yaml` (DECL) + a FAKE `ssh` on a temp PATH (verify-access calls `ssh` directly, so a fake
intercepts it). Fixtures under mktemp ONLY. Cases:
1. `flow_form_inline_comment_parses` (#58) — fixture has a machine declared in `{...}` flow form WITH a
   trailing `# comment`; fake ssh succeeds (`echo HN:<name>`). Assert the line is `PASS` (NOT `unknown
   method` — proving the method parsed cleanly, comment+`}` stripped). RED now: current parse → the
   method carries `} # comment` → `unknown method`.
2. `probe_failure_names_the_cause` (#56) — fixture machine, fake ssh emits `Permission denied
   (publickey).` to stderr and exits non-zero. Assert the FAIL line contains the CAUSE (e.g. `auth`),
   NOT a bare `unreachable as`. RED now: current → `unreachable as u@h` with no cause.
3. (optional) `dns_vs_auth_distinguished` — a second fake-ssh error (`Could not resolve hostname`) →
   the FAIL line names `dns`, proving distinct causes are distinguished, not collapsed.
The fake ssh: a `#!/usr/bin/env bash` script that prints a chosen message and exits a chosen code, put
at `$tmp/bin/ssh`, with `PATH="$tmp/bin:$PATH"`. test-verify-access.sh must be shellcheck-clean.

## Gate
`bash ctl.sh validate` (the shellcheck floor lints the new test + the edited script). No kubeconform/
actionlint dependency. Tool: bash + ssh-fake (self-contained). The new test is NOT wired into a CI job
here (verify-access is not a CI gate) — it runs via `bash scripts/test-verify-access.sh` locally; note
whether to add a validate.yml step (probably yes — mirror the lint-shell fixture-test step) so CI runs it.

## Conflict
scripts/verify-access.sh + a new test file. DISJOINT from #175 (validate.yml/ctl.sh verify_* — ctl.sh
only DISPATCHES to verify-access, not touched here) and #174. No overlap.

## Blocked
Nothing. Non-Mateo, isolated, low-value-but-real.

## Next
dev-test-author: write scripts/test-verify-access.sh (fake-ssh + fixture, the 2-3 cases above), prove
RED (current parse corrupts + probe hides the cause). Owners: test-verify-access.sh → dev-test-author;
verify-access.sh → dev-implementer.
