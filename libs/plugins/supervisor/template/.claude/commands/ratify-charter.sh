#!/usr/bin/env bash
#
# ratify-charter.sh — FSM transition `ratify-charter`: charter_drafted -> charter_ratified.
# The human's act of freezing the charter. Guard: a drafted charter exists in git. Writes the
# init/charter/.ratified marker (its git presence is every downstream guard's predicate),
# fingerprints the ratified charter, advances state, audits, prints the trailer. Does NOT commit.
#
# Usage: ratify-charter.sh '<ratification-json>'
#
# shellcheck shell=bash
# shellcheck source=_supervisor.sh
# shellcheck disable=SC1091
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_supervisor.sh"
sv_require_jq

PAYLOAD="${*:-}"
[[ -n "$PAYLOAD" ]] || sv_die "ratify-charter requires a JSON ratification payload (who/when)."

TRANSITION="ratify-charter"
ARTIFACT="init/charter/.ratified"

sv_assert_legal    "$TRANSITION"
sv_assert_guard    "$TRANSITION"
sv_validate_schema "ratification" "$PAYLOAD"

# Fingerprint the charter we are freezing, so a later silent edit is detectable.
root="$(sv_project_dir)"
charter="$root/init/charter/charter.md"
[[ -f "$charter" ]] || sv_die "init/charter/charter.md missing on disk despite the guard — re-run /propose-charter."
if command -v shasum >/dev/null 2>&1; then
  fp="$(shasum -a 256 "$charter" | awk '{print $1}')"
elif command -v sha256sum >/dev/null 2>&1; then
  fp="$(sha256sum "$charter" | awk '{print $1}')"
else
  fp=""
fi

enriched="$(printf '%s' "$PAYLOAD" | jq --arg fp "$fp" '. + (if $fp == "" then {} else {charter_fingerprint:$fp} end)')"
sv_write_json_marker "$ARTIFACT" "$enriched"

printf 'charter ratified by %s; marker written: %s\n' "$(printf '%s' "$PAYLOAD" | jq -r '.ratified_by')" "$ARTIFACT"
sv_finish_transition "$TRANSITION" "$ARTIFACT" "$(printf '%s' "$PAYLOAD" | jq -r '.ratified_by')" "fingerprint=$fp"
