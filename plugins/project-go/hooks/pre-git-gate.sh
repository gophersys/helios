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

# Collect the Go files in scope, identically to the .githooks.
go_files=""
if [[ "$GATE" == "commit" ]]; then
  go_files="$(git diff --cached --name-only --diff-filter=ACM -- '*.go' 2>/dev/null || true)"
else
  upstream="$(git rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2>/dev/null || true)"
  if [[ -n "$upstream" ]]; then
    go_files="$(git diff --name-only --diff-filter=ACM "${upstream}..HEAD" -- '*.go' 2>/dev/null || true)"
  fi
fi

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
if hns_bin="$(pg_have hnslint)"; then
  libs="$(printf '%s\n' "$go_files" | sed -nE 's#^(libs/go/[^/]+)/.*#\1#p' | sort -u)"
  while IFS= read -r lib; do
    [[ -n "$lib" ]] || continue
    hnsout="$("$hns_bin" "$PROJECT_DIR/$lib" 2>&1 || true)"
    [[ -n "$hnsout" ]] && findings+="hnslint (HNS-1, $lib):"$'\n'"$hnsout"$'\n'
  done <<< "$libs"
fi

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
