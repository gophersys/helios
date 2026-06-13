#!/usr/bin/env bash
#
# post-edit-lint.sh — PostToolUse hook on Edit/Write/MultiEdit (ADR-0018 Layer 2).
#
# The inner-loop enforcement that would have caught `cfgtest` the instant it was written:
# when the agent edits a *.go file, lint that file's module (golangci-lint, fast path) and
# run hnslint on its libs/go/<lib>, and feed any findings straight back to the agent so it
# self-corrects BEFORE proceeding — via hookSpecificOutput.additionalContext (PostToolUse
# is a member of CC's hookSpecificOutput union, so this is the correct delivery channel).
#
# Always exits 0: this hook reports, it does not hard-block (the git gate is the block).
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_lib.sh
# shellcheck disable=SC1091
source "$SCRIPT_DIR/_lib.sh"

pg_read_input

FILE="$(pg_json '.tool_input.file_path')"
[[ -z "$FILE" ]] && FILE="$(pg_json '.tool_input.path')"

# Only care about Go source. Skip anything else (incl. *_test.go is fine — lint it too).
case "$FILE" in
  *.go) ;;
  *) exit 0 ;;
esac
[[ -f "$FILE" ]] || exit 0

ABS="$FILE"
[[ "$ABS" = /* ]] || ABS="$(pg_project_dir)/$FILE"

findings=""

# --- gofumpt (formatting) ---
if gofumpt_bin="$(pg_have gofumpt)"; then
  fmtout="$("$gofumpt_bin" -l "$ABS" 2>/dev/null || true)"
  [[ -n "$fmtout" ]] && findings+="gofumpt: not formatted — run gofumpt -w on this file."$'\n'
fi

# --- golangci-lint (fast path) on the single file; v2 lints the enclosing package and
#     filters output to this file. Picks up the shared libs/.golangci.yml by discovery. ---
if gcl_bin="$(pg_have golangci-lint)"; then
  module_dir="$(pg_module_dir "$ABS")"
  if [[ -n "$module_dir" ]]; then
    rel="${ABS#"$module_dir"/}"
    lintout="$( ( cd "$module_dir" && "$gcl_bin" run --fast-only --timeout=90s --output.text.print-issued-lines=false "$rel" ) 2>&1 || true )"
    if [[ -n "$lintout" ]] && ! printf '%s' "$lintout" | grep -qiE '^0 issues\.?$'; then
      # Strip the noisy "0 issues." tail if present; keep real findings.
      cleaned="$(printf '%s\n' "$lintout" | grep -vE '^0 issues\.?$' || true)"
      [[ -n "$cleaned" ]] && findings+="golangci-lint:"$'\n'"$cleaned"$'\n'
    fi
  fi
fi

# --- hnslint (structural HNS-1) when the file is inside libs/go/<lib> ---
case "$ABS" in
  */libs/go/*)
    lib_dir="$(printf '%s' "$ABS" | sed -E 's#^(.*/libs/go/[^/]+)/.*#\1#')"
    if hns_bin="$(pg_have hnslint)" && [[ -d "$lib_dir" ]]; then
      hnsout="$("$hns_bin" "$lib_dir" 2>&1 || true)"
      [[ -n "$hnsout" ]] && findings+="hnslint (HNS-1):"$'\n'"$hnsout"$'\n'
    fi
    ;;
esac

if [[ -z "$findings" ]]; then
  exit 0   # clean — stay silent
fi

msg="project-go lint findings on ${FILE} — fix these before proceeding:"$'\n\n'"$findings"
pg_emit_context "PostToolUse" "$msg"
exit 0
