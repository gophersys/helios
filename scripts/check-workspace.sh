#!/usr/bin/env bash
set -Eeuo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

expected_projects=$'devcontainer\nworkspace'
actual_projects="$(nx show projects | sort)"
[[ "$actual_projects" == "$expected_projects" ]] || {
  printf 'unexpected Nx projects:\n%s\n' "$actual_projects" >&2
  exit 1
}

for path in "$root"/* "$root"/.[!.]*; do
  name="$(basename "$path")"
  case "$name" in
    .agents|.claude|.devcontainer|.editorconfig|.gitattributes|.gitignore|.yarnrc.yml|AGENTS.md|CLAUDE.md|README.md|docs|harnesses|nx.json|package.json|project.json|scripts|yarn.lock) ;;
    .git|.nx|.yarn|node_modules) ;;
    *) echo "unexpected top-level path: $name" >&2; exit 1 ;;
  esac
done

echo "minimal Nx workspace: PASS"
