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

# --- ADR-0020 advisory reminders (never block; still exit 0) -------------------------------
# (1) four-binding rule: a *_test.go inside a <lib>test conformance package should run the suite
#     over fake + docker + k3d + kind. If a binding looks missing, remind the agent.
# (2) TDD order: a NON-test body edit while the conformance suite is still RED is out of order.
reminders=""
case "$ABS" in
  */libs/go/*test/*_test.go)
    # In a conformance package: nudge the four-binding rule if any binding token is absent.
    have_all=1
    for token in docker k3d kind; do
      grep -qiE "\\b${token}\\b" "$ABS" 2>/dev/null || have_all=0
    done
    if [[ $have_all -eq 0 ]]; then
      reminders+="four-binding rule (ADR-0020 §d): the conformance suite runs over fake + REAL docker + k3d + kind — never mock the substrate. Ensure every binding is present (one may Skip on an absent local substrate, but never be silently omitted)."$'\n'
    fi
    ;;
  */libs/go/*.go)
    case "$ABS" in
      *_test.go) : ;;  # editing a test — TDD order is fine
      *)
        # A non-test body edit: if the owning lib's unit/conformance suite is currently RED,
        # warn that bodies are being written before green conformance (TDD order). Fast probe.
        lib_dir="$(printf '%s' "$ABS" | sed -E 's#^(.*/libs/go/[^/]+)/.*#\1#')"
        if [[ -d "$lib_dir" ]] && command -v go >/dev/null 2>&1; then
          if ! ( cd "$lib_dir" && go test ./... -count=1 >/dev/null 2>&1 ); then
            reminders+="TDD order (ADR-0020): you edited an implementation body while this lib's conformance suite is RED. Write the fake binding + conformance cases FIRST (red), then make them green. Run: bash ./ctl.sh phase-gate implementation."$'\n'
          fi
        fi
        ;;
    esac
    ;;
esac

if [[ -z "$findings" && -z "$reminders" ]]; then
  exit 0   # clean — stay silent
fi

msg=""
[[ -n "$findings" ]]  && msg+="project-go lint findings on ${FILE} — fix these before proceeding:"$'\n\n'"$findings"$'\n'
[[ -n "$reminders" ]] && msg+="project-go pipeline reminders on ${FILE}:"$'\n\n'"$reminders"
pg_emit_context "PostToolUse" "$msg"
exit 0
