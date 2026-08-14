#!/usr/bin/env bash
# Spec for scripts/verify-access.sh — the manual `verify-access` diagnostic.
#
# TWO DEFECTS THESE CASES PIN (both live in scripts/verify-access.sh today)
# #58  parse() flow branch. A machine declared in `{...}` flow form with a
#      trailing `# comment` is mis-parsed: the awk strips the `}` only when it
#      sits at end-of-line (`sub(/\}[[:space:]]*$/,...)`), and strips no comment
#      at all, while the block branch does strip `#.*`. So
#          host: { ..., method: tailscale-ssh } # note
#      yields method = `tailscale-ssh } # note`, which falls through `case
#      "$method"` to `*) unknown method`. The block branch is correct; only the
#      flow branch drops the comment.
# #56  probe(). `ssh ... 2>&1 | grep -o 'HN:[^ ]*' | head -1` keeps only an HN:
#      match, so on ANY failure (auth, DNS, refused, timeout) the ssh error is
#      discarded and the caller prints a bare `unreachable as u@h` — the same
#      four words for four different causes. The cause is lost.
#
# HOW THESE CASES REACH THE REAL SCRIPT
# verify-access.sh derives DECL from its own location
# (ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd); DECL=$ROOT/contracts/
# access.yaml) and calls `ssh` directly. There is no -f/env override today, so we
# point it at a fixture WITHOUT editing it: a SYMLINK at <tmp>/scripts/verify-
# access.sh -> the real script makes BASH_SOURCE the symlink path, so ROOT
# resolves to <tmp> and DECL to <tmp>/contracts/access.yaml. The symlink runs the
# REAL script live, so the implementer's fix is exercised, not a stale copy. A
# FAKE `ssh` at <tmp>/bin/ssh on PATH intercepts the probe and emits a chosen
# message + exit code. Everything lives under mktemp; nothing is written into the
# repo tree.
#
# THE CONTRACT THESE CASES PIN
#   C1  a `{...}` flow-form machine WITH a trailing `# comment` parses to a clean
#       method: its line is PASS and carries no `unknown method`. Proves #58's
#       comment+`}` strip. RED now: method = `tailscale-ssh } # note` -> `unknown
#       method`.
#   C2  a probe that fails with `Permission denied (publickey).` prints a FAIL
#       line that NAMES the cause `auth`, not a bare `unreachable as`. RED now:
#       `unreachable as tester@homelab.example`, no cause.
#   C3  two probes failing with DIFFERENT ssh errors (Permission denied vs
#       Could not resolve hostname) are DISTINGUISHED: one line names `auth`, the
#       other `dns`. Proves the cause is classified, not collapsed. RED now: both
#       print `unreachable as ...`.
#
# Run: bash scripts/test-verify-access.sh            # every case
#      bash scripts/test-verify-access.sh <name>...  # one case, by name
#      bash scripts/test-verify-access.sh --list     # the case names
#
# FIXTURES + FAKE ssh LIVE UNDER mktemp ONLY, never in the repo tree: the real
# diagnostic reads the real contracts/access.yaml and calls the real ssh, so a
# committed fixture or fake would be either dead weight or a live hazard.
set -Eeuo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/.." && pwd)"
SUT="$REPO_ROOT/scripts/verify-access.sh"
ESC="$(printf '\033')"

CASES="
flow_form_inline_comment_parses
probe_failure_names_the_cause
dns_and_auth_are_distinguished
"

# mktemp dirs to shred on exit. The guard form ${arr[@]+"${arr[@]}"} is for
# bash 3.2 (the macOS system bash) under set -u, where "${empty[@]}" aborts.
TMPDIRS=()
cleanup() {
  local d
  for d in ${TMPDIRS[@]+"${TMPDIRS[@]}"}; do
    [ -n "$d" ] && rm -rf "$d"
  done
}
trap cleanup EXIT

failures=0
case_failures=0
out=""
rc=0
ENV_DIR=""

note() { echo "    $*"; }

bad() {
  note "FAIL: $*"
  failures=$((failures + 1))
  case_failures=$((case_failures + 1))
}

# A fresh sandbox: a symlink to the REAL verify-access.sh so BASH_SOURCE places
# ROOT/DECL under the temp dir, plus empty contracts/ and bin/ for the fixture
# yaml and the fake ssh. The case fills those two in.
new_env() {
  ENV_DIR="$(mktemp -d)"; TMPDIRS+=("$ENV_DIR")
  mkdir -p "$ENV_DIR/scripts" "$ENV_DIR/contracts" "$ENV_DIR/bin"
  ln -s "$SUT" "$ENV_DIR/scripts/verify-access.sh"
}

# Drive the REAL script via the symlink, fake ssh first on PATH. set +e wraps the
# call so a non-zero exit does not abort the run, and rc=$? sits on the line right
# after the substitution so nothing runs between them. A pipeline would report its
# last stage instead — a misreading that has produced false findings here.
run_verify() {
  set +e
  out="$(PATH="$ENV_DIR/bin:$PATH" bash "$ENV_DIR/scripts/verify-access.sh" 2>&1)"
  rc=$?
  out="$(printf '%s\n' "$out" | sed "s/${ESC}\[[0-9;]*m//g")"
  set -e
}

expect_rc() { # <want> <why>
  if [ "$rc" -eq "$1" ]; then
    return 0
  fi
  bad "exit $rc, want $1 — $2"
  printf '%s\n' "$out" | tail -6 | sed 's/^/      | /'
}

expect_line() { # <extended-regex> <why>
  if printf '%s\n' "$out" | grep -qE "$1"; then
    return 0
  fi
  bad "no line matched /$1/ — $2"
  printf '%s\n' "$out" | tail -6 | sed 's/^/      | /'
}

refute_line() { # <extended-regex> <why>
  if printf '%s\n' "$out" | grep -qE "$1"; then
    bad "a line matched /$1/ but must not — $2"
    printf '%s\n' "$out" | tail -6 | sed 's/^/      | /'
  fi
}

# -------- the cases --------

# 1. #58 — FLOW FORM WITH A TRAILING COMMENT. `homelab` is declared in `{...}`
# form with a trailing `# note`. The fake ssh succeeds and echoes HN:homelab, so
# the ONLY thing that can keep this off PASS is a corrupted method. With the bug
# the last field parses to `tailscale-ssh } # note` and the line reads `unknown
# method tailscale-ssh } # note`. Green when the flow branch strips the `}` and
# the comment.
test_flow_form_inline_comment_parses() {
  new_env
  cat >"$ENV_DIR/contracts/access.yaml" <<'EOYAML'
machines:
  homelab: { user: tester, address: homelab.example, method: tailscale-ssh } # note
EOYAML
  cat >"$ENV_DIR/bin/ssh" <<'EOSH'
#!/usr/bin/env bash
echo "HN:homelab"
exit 0
EOSH
  chmod +x "$ENV_DIR/bin/ssh"
  run_verify
  expect_rc 0 "a reachable machine parsed cleanly must make the run pass (C1)"
  expect_line 'PASS[[:space:]]+homelab' "the flow-form machine must reach PASS (C1)"
  refute_line 'unknown method' "the trailing comment must not leak into method (C1)"
}

# 2. #56 — A FAILED PROBE MUST NAME ITS CAUSE. The fake ssh fails with a
# publickey rejection. The machine is genuinely unreachable, so the run stays
# non-zero either way; what must change is the FAIL line — it must carry the
# cause `auth`, not the causeless `unreachable as`. Green when probe classifies
# `Permission denied`/`publickey` as `auth` and the caller prints it.
test_probe_failure_names_the_cause() {
  new_env
  cat >"$ENV_DIR/contracts/access.yaml" <<'EOYAML'
machines:
  homelab:
    user: tester
    address: homelab.example
    method: tailscale-ssh
EOYAML
  cat >"$ENV_DIR/bin/ssh" <<'EOSH'
#!/usr/bin/env bash
echo "Permission denied (publickey)." >&2
exit 255
EOSH
  chmod +x "$ENV_DIR/bin/ssh"
  run_verify
  expect_line 'FAIL[[:space:]]+homelab' "an unreachable machine must report FAIL (C2)"
  expect_line 'homelab.*auth' "the FAIL line must name the auth cause, not a bare unreachable (C2)"
}

# 3. #56 — DISTINCT CAUSES ARE DISTINGUISHED, NOT COLLAPSED. Two machines fail
# with different ssh errors: `homelab` a publickey rejection (auth), `builder` a
# name-resolution failure (dns). The two FAIL lines must name two different
# causes. Green when probe maps Permission-denied->auth and Could-not-resolve->
# dns. RED now: both print `unreachable as ...`, indistinguishable.
test_dns_and_auth_are_distinguished() {
  new_env
  cat >"$ENV_DIR/contracts/access.yaml" <<'EOYAML'
machines:
  homelab:
    user: tester
    address: homelab.example
    method: tailscale-ssh
  builder:
    user: tester
    address: builder.example
    method: tailscale-ssh
EOYAML
  cat >"$ENV_DIR/bin/ssh" <<'EOSH'
#!/usr/bin/env bash
target=""
for a in "$@"; do
  case "$a" in *@*) target="$a" ;; esac
done
case "$target" in
  *homelab*) echo "Permission denied (publickey)." >&2; exit 255 ;;
  *builder*) echo "ssh: Could not resolve hostname builder.example: nodename nor servname provided" >&2; exit 255 ;;
  *)         echo "unexpected target: $target" >&2; exit 2 ;;
esac
EOSH
  chmod +x "$ENV_DIR/bin/ssh"
  run_verify
  expect_line 'homelab.*auth' "the publickey failure must be named auth (C3)"
  expect_line 'builder.*dns' "the resolve failure must be named dns, distinct from auth (C3)"
}

# -------- runner --------

run_case() {
  local name="$1"
  case_failures=0
  echo "== $name"
  "test_$name"
  if [ "$case_failures" -eq 0 ]; then
    note "ok"
  fi
}

main() {
  local selected="" name known found
  if [ "$#" -eq 0 ]; then
    selected="$CASES"
  elif [ "$1" = "--list" ]; then
    printf '%s' "$CASES" | sed '/^$/d'
    return 0
  else
    for name in "$@"; do
      found=0
      for known in $CASES; do
        [ "$name" = "$known" ] && found=1
      done
      if [ "$found" -eq 0 ]; then
        echo "test-verify-access: no such case: $name" >&2
        echo "  known: $(printf '%s' "$CASES" | tr '\n' ' ')" >&2
        exit 2
      fi
      selected="$selected$name
"
    done
  fi

  local total=0
  for name in $selected; do
    run_case "$name"
    total=$((total + 1))
  done

  echo
  echo "cases=$total assertion-failures=$failures"
  [ "$failures" -eq 0 ] || exit 1
}

main "$@"
