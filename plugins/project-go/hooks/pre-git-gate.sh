#!/usr/bin/env bash
#
# pre-git-gate.sh — PreToolUse hook on Bash (ADR-0018 Layer 2).
#
# When the agent is about to run `git commit` or `git push`, run the same deterministic
# Layer-1 gate the .githooks enforce, and block the tool call on failure so the agent
# fixes the code instead of committing a violation. This is belt-and-suspenders with the
# client git hooks: the hooks catch a human/agent who runs git directly; this catches the
# agent inside the harness and gives it the findings inline.
#
# PreToolUse decision is returned via hookSpecificOutput.permissionDecision:
#   "deny"  -> block the git command, feed `permissionDecisionReason` back to the agent
#   (absent / exit 0) -> allow
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_lib.sh
# shellcheck disable=SC1091
source "$SCRIPT_DIR/_lib.sh"

pg_read_input

CMD="$(pg_json '.tool_input.command')"

# Is this a git commit or git push? (Match the verb robustly; ignore `git log`, etc.)
is_git_gate=0
case "$CMD" in
  *git*commit*|*git*push*) is_git_gate=1 ;;
esac
[[ $is_git_gate -eq 0 ]] && exit 0   # not a gated command — allow silently

# --no-verify in the command means the human explicitly chose to bypass the client hooks;
# we honour that here too (CI remains the non-bypassable gate) but say so.
case "$CMD" in
  *--no-verify*) exit 0 ;;
esac

PROJECT_DIR="$(pg_project_dir)"
cd "$PROJECT_DIR" 2>/dev/null || exit 0

# Decide which gate: commit -> staged tree; push -> commits ahead of upstream.
GATE="commit"
case "$CMD" in *git*push*) GATE="push" ;; esac

# Collect the Go files in scope, identically to the .githooks. CRITICAL: the library code lives in
# the `libs/` git SUBMODULE — a `git commit`/`git push` for library work runs INSIDE the submodule,
# whose staged Go files do NOT appear in the superproject's `git diff --cached`. So we gate BOTH the
# superproject tree (paths `libs/go/<lib>/…`) AND the libs submodule tree (paths `go/<lib>/…`,
# re-prefixed to `libs/go/<lib>/…` so the per-lib resolution below is uniform). Without this the
# gate is blind to exactly the commits it most needs to catch.
_scope_go_files() {                  # _scope_go_files <repo-dir> <path-prefix>
  local repo="$1" prefix="$2"
  [[ -d "$repo/.git" || -f "$repo/.git" ]] || return 0
  local files
  if [[ "$GATE" == "commit" ]]; then
    files="$(git -C "$repo" diff --cached --name-only --diff-filter=ACM -- '*.go' 2>/dev/null || true)"
  else
    local up
    up="$(git -C "$repo" rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2>/dev/null || true)"
    [[ -n "$up" ]] && files="$(git -C "$repo" diff --name-only --diff-filter=ACM "${up}..HEAD" -- '*.go' 2>/dev/null || true)"
  fi
  printf '%s\n' "$files" | while IFS= read -r f; do
    [[ -n "$f" ]] || continue
    printf '%s%s\n' "$prefix" "$f"
  done
}

go_files="$(
  {
    _scope_go_files "$PROJECT_DIR" ''                  # superproject: paths already libs/go/<lib>/…
    _scope_go_files "$PROJECT_DIR/libs" 'libs/'        # submodule: go/<lib>/… → libs/go/<lib>/…
  } | sort -u | sed '/^$/d'
)"

[[ -z "$go_files" ]] && exit 0   # no Go in scope — nothing to gate

findings=""

# Unique owning modules + touched libs/go/<lib>.
modules="$(printf '%s\n' "$go_files" | while IFS= read -r f; do
  [[ -n "$f" ]] || continue
  d="$(dirname "$PROJECT_DIR/$f")"
  while [[ -n "$d" && "$d" != "/" ]]; do
    [[ -f "$d/go.mod" ]] && { printf '%s\n' "$d"; break; }
    d="$(dirname "$d")"
  done
done | sort -u)"

# gofumpt
if gofumpt_bin="$(pg_have gofumpt)"; then
  abs_files="$(printf '%s\n' "$go_files" | while IFS= read -r f; do [[ -n "$f" ]] && printf '%s\n' "$PROJECT_DIR/$f"; done)"
  # shellcheck disable=SC2086
  fmtout="$(printf '%s\n' "$abs_files" | tr '\n' '\0' | xargs -0 "$gofumpt_bin" -l 2>/dev/null || true)"
  [[ -n "$fmtout" ]] && findings+="gofumpt — not formatted:"$'\n'"$fmtout"$'\n'
fi

# golangci-lint per module
if gcl_bin="$(pg_have golangci-lint)"; then
  while IFS= read -r md; do
    [[ -n "$md" ]] || continue
    lintout="$( ( cd "$md" && "$gcl_bin" run --timeout=180s ./... ) 2>&1 || true )"
    if [[ -n "$lintout" ]] && ! printf '%s' "$lintout" | grep -qiE '^0 issues\.?$'; then
      cleaned="$(printf '%s\n' "$lintout" | grep -vE '^0 issues\.?$' || true)"
      [[ -n "$cleaned" ]] && findings+="golangci-lint (${md#"$PROJECT_DIR"/}):"$'\n'"$cleaned"$'\n'
    fi
  done <<< "$modules"
fi

# hnslint per touched lib
touched_libs="$(printf '%s\n' "$go_files" | sed -nE 's#^(libs/go/[^/]+)/.*#\1#p' | sort -u)"
if hns_bin="$(pg_have hnslint)"; then
  while IFS= read -r lib; do
    [[ -n "$lib" ]] || continue
    hnsout="$("$hns_bin" "$PROJECT_DIR/$lib" 2>&1 || true)"
    [[ -n "$hnsout" ]] && findings+="hnslint (HNS-1, $lib):"$'\n'"$hnsout"$'\n'
  done <<< "$touched_libs"
fi

# --- ADR-0020 taxonomy gate: leak + vuln + secretscan + cover-floor + apidiff per touched lib ---
# The git gate enforces the FULL taxonomy for the touched libs, so a commit/push the agent
# attempts is denied unless every dimension passes — the agent gets the per-dimension findings
# inline and self-corrects. Heavy host-bound lanes (integration/load/bench) stay OUT (CI + the
# phase-gate verb own them). Each delegates to the per-lib ctl.sh so the ONE definition is reused.
while IFS= read -r lib; do
  [[ -n "$lib" ]] || continue
  lib_dir="$PROJECT_DIR/$lib"
  [[ -f "$lib_dir/ctl.sh" ]] || continue
  # govulncheck
  if pg_have govulncheck >/dev/null; then
    vout="$( ( cd "$lib_dir" && bash ./ctl.sh vuln ) 2>&1 || true )"
    printf '%s' "$vout" | grep -qiE 'No vulnerabilities found|vuln: OK' || findings+="vuln ($lib):"$'\n'"$vout"$'\n'
  fi
  # leak
  lout="$( ( cd "$lib_dir" && bash ./ctl.sh leak ) 2>&1 || true )"
  printf '%s' "$lout" | grep -qiE 'leak: OK' || findings+="leak ($lib):"$'\n'"$(printf '%s' "$lout" | tail -8)"$'\n'
  # secretscan
  if pg_have gitleaks >/dev/null; then
    sout="$( ( cd "$lib_dir" && bash ./ctl.sh secretscan ) 2>&1 || true )"
    printf '%s' "$sout" | grep -qiE 'secretscan: OK' || findings+="secretscan ($lib):"$'\n'"$(printf '%s' "$sout" | tail -6)"$'\n'
  fi
  # cover-floor
  cout="$( ( cd "$lib_dir" && bash ./ctl.sh cover-floor ) 2>&1 || true )"
  printf '%s' "$cout" | grep -qiE 'cover-floor: every production package|cover-floor: .* >= ' || findings+="cover-floor ($lib):"$'\n'"$(printf '%s' "$cout" | grep -E '< floor|FAIL|error' | tail -6)"$'\n'
  # apidiff (no break) — only if a baseline exists
  if [[ -f "$lib_dir/.apibaseline" ]]; then
    aout="$( ( cd "$lib_dir" && bash ./ctl.sh apidiff ) 2>&1 || true )"
    printf '%s' "$aout" | grep -qiE 'apidiff: (exported surface matches|no break)' || findings+="apidiff BREAK ($lib) — the cardinal sin (10 §9):"$'\n'"$(printf '%s' "$aout" | grep -E '^\s+-|BREAK' | tail -8)"$'\n'
  fi
done <<< "$touched_libs"

if [[ -z "$findings" ]]; then
  exit 0   # gate clean — allow the git command
fi

reason="Eden Go gate failed — this ${GATE} is blocked. Fix the violations below and retry (or, if you must, the human can bypass with --no-verify; CI re-runs the same gate regardless):"$'\n\n'"$findings"

if command -v jq >/dev/null 2>&1; then
  jq -n --arg r "$reason" \
    '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "deny", permissionDecisionReason: $r}}'
else
  esc="$(printf '%s' "$reason" | sed 's/\\/\\\\/g; s/"/\\"/g' | awk '{printf "%s\\n", $0}')"
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"%s"}}' "$esc"
fi
exit 0
