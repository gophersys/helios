#!/usr/bin/env bash
set -Eeuo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

expected_projects=$'agents\nchange\ndevcontainer\ndocs\neden\nworkspace'
actual_projects="$(nx show projects | sort)"
[[ "$actual_projects" == "$expected_projects" ]] || {
  printf 'unexpected Nx projects:\n%s\n' "$actual_projects" >&2
  exit 1
}

while IFS= read -r project_file; do
  project_root="$(jq -r '.root // "."' "$project_file")"
  while IFS= read -r target; do
    command="$(jq -r --arg target "$target" '.targets[$target].command // .targets[$target].options.command // ""' "$project_file")"
    cwd="$(jq -r --arg target "$target" '.targets[$target].options.cwd // ""' "$project_file")"
    [[ "$command" == "./ctl.sh $target" && "$cwd" == "{projectRoot}" ]] || {
      printf '%s:%s must use command "./ctl.sh %s" with cwd "{projectRoot}"\n' "$project_root" "$target" "$target" >&2
      exit 1
    }
  done < <(jq -r '.targets | keys[]' "$project_file")
done < <(find "$root" -name project.json -not -path '*/node_modules/*' -not -path '*/.nx/*' | sort)

for path in "$root"/* "$root"/.[!.]*; do
  name="$(basename "$path")"
  case "$name" in
    .agents|.claude|.codex|.ctl|.devcontainer|.eden|.editorconfig|.gitattributes|.github|.githooks|.gitignore|.omp|.yarnrc.yml|AGENTS.md|CLAUDE.md|README.md|ctl.sh|docs|nx.json|package.json|project.json|yarn.lock) ;;
    .git|.nx|.yarn|node_modules) ;;
    *) echo "unexpected top-level path: $name" >&2; exit 1 ;;
  esac
done

echo "minimal Nx workspace: PASS"
