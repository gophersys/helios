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
  [[ "$actual" == *"$expected"* ]] ||
    echo "note: image has $command_name '$actual'; repository pin is $expected" >&2
done

# Workspace dependencies change with the checkout and therefore are installed at
# container creation rather than baked into the shared image.
yarn install --immutable
sudo ln -sfn /workspace/node_modules/.bin/nx /usr/local/bin/nx

grep -qs "alias c=" "$HOME/.zshrc" ||
  echo "alias c='claude --dangerously-skip-permissions'" >> "$HOME/.zshrc"
