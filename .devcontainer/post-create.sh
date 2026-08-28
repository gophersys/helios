#!/usr/bin/env bash
set -Eeuo pipefail

versions=/workspace/harnesses/versions.env
# shellcheck disable=SC1090
source "$versions"

for specification in \
  "claude:${CLAUDE_CODE_VERSION}" \
  "omp:${OMP_VERSION}" \
  "codex:${CODEX_VERSION}"; do
  command_name="${specification%%:*}"
  expected="${specification#*:}"
  actual="$($command_name --version 2>&1)"
  [[ "$actual" == *"$expected"* ]] || {
    echo "$command_name reports '$actual'; expected $expected" >&2
    exit 1
  }
done

grep -qs "alias c=" "$HOME/.zshrc" ||
  echo "alias c='claude --dangerously-skip-permissions'" >> "$HOME/.zshrc"
