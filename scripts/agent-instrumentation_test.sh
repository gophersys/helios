#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

function fail() {
  printf 'agent-instrumentation: %s\n' "$*" >&2
  exit 1
}

for required in \
  AGENTS.md \
  CLAUDE.md \
  docs/engineering/README.md \
  docs/engineering/system.json \
  docs/engineering/system.schema.json \
  docs/tools/validate-engineering-system.mjs; do
  [[ -f "$repository_root/$required" ]] || fail "missing $required"
done

for entrypoint in AGENTS.md CLAUDE.md; do
  lines="$(wc -l < "$repository_root/$entrypoint" | tr -d ' ')"
  (( lines <= 80 )) || fail "$entrypoint is $lines lines; always-loaded guidance must stay at or below 80"
  rg -q 'docs/engineering/README\.md' "$repository_root/$entrypoint" || fail "$entrypoint does not route to docs/engineering/README.md"
  rg -q 'docs/engineering/system\.json' "$repository_root/$entrypoint" || fail "$entrypoint does not cite the machine-readable system contract"
done

node "$repository_root/docs/tools/validate-engineering-system.mjs"
printf 'agent-instrumentation: OK\n'
