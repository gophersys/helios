#!/usr/bin/env bash
#
# scripts/mktemp-template_test.sh — repository rule: an mktemp template carries >= 3 trailing X's.
#
# GNU mktemp (the devcontainer and every CI image) rejects a template with fewer than 3 trailing
# X's — "too few X's in template" — while BSD mktemp on a mac accepts the same line. A form that
# only a mac accepts therefore reaches CI green on a laptop and exits 1 in the lane, which is how
# scripts/assert-no-skipped-tests.sh:22 stopped the harness-conformance job for 8 days. This test
# holds the whole repository to the portable form.
#
# It reads text only. It never runs mktemp, so its verdict is the same on a mac and in the
# container and it needs no GNU-mktemp guard. Run it directly:
#   bash scripts/mktemp-template_test.sh
# It exits non-zero on the first violation or on a fixture mismatch. shellcheck-clean at -S style.
set -Eeuo pipefail
IFS=$'\n\t'

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repository_root="$(git -C "$here" rev-parse --show-toplevel)"
fixtures="${here}/testdata/mktemp-template-fixtures.txt"

fails=0
invocations_examined=0

# mktemp counts only in command position. The word inside a comment, a message or a document is
# prose, and a rule that reads prose as code cannot be trusted to name a real violation. The word
# also opens a variable name (mktemp_version=...), so both sides of the occurrence are judged.
mktemp_leader_pattern='(^|[;&|(`!{])[[:space:]]*$'
mktemp_follower_pattern='^([[:space:]]|\)|$)'

# mktemp_template_verdict <source line> -> echoes none | ok | bad
mktemp_template_verdict() {
  local line="$1"
  local remainder="$line" consumed='' before after prefix
  local -a invocations=()
  while [[ $remainder == *mktemp* ]]; do
    before="${remainder%%mktemp*}"
    after="${remainder#*mktemp}"
    prefix="${consumed}${before}"
    if [[ $prefix =~ $mktemp_leader_pattern ]] && [[ $after =~ $mktemp_follower_pattern ]]; then
      invocations+=("$after")
    fi
    consumed="${prefix}mktemp"
    remainder="$after"
  done
  if [[ ${#invocations[@]} -eq 0 ]]; then
    printf 'none\n'
    return 0
  fi

  local arguments
  for arguments in "${invocations[@]}"; do
    if [[ "$(mktemp_arguments_verdict "$arguments")" == 'bad' ]]; then
      printf 'bad\n'
      return 0
    fi
  done
  printf 'ok\n'
}

# mktemp_arguments_verdict <everything after one mktemp in command position> -> ok | bad
mktemp_arguments_verdict() {
  local arguments="$1"
  # Drop the redirections first, so 2>&1 and >/dev/null are never read as a template operand.
  arguments="$(printf '%s' "$arguments" |
    sed -E 's/[0-9]*>>?[[:space:]]*(&[0-9-]+|[^[:space:];|)&]+)//g; s/[0-9]*<[[:space:]]*[^[:space:];|)&]+//g')"
  # Then stop at the end of this simple command.
  arguments="${arguments%%)*}"
  arguments="${arguments%%;*}"
  arguments="${arguments%%|*}"
  arguments="${arguments%%&*}"
  arguments="${arguments%%\`*}"

  local -a tokens=()
  local IFS=$' \t\n'
  read -r -a tokens <<<"$arguments"

  local -a templates=()
  local token
  local expects_value=0
  if [[ ${#tokens[@]} -gt 0 ]]; then
    for token in "${tokens[@]}"; do
      token="${token//\"/}"
      token="${token//\'/}"
      [[ -n "$token" ]] || continue
      if [[ $expects_value -eq 1 ]]; then
        expects_value=0
        continue
      fi
      case "$token" in
        # These flags take a directory or a suffix, never a template.
        -p | --tmpdir | --suffix) expects_value=1 ;;
        # -t is a flag under GNU and takes the next word under BSD. Either reading puts the
        # template in the next word, so -t is skipped here and the next word is judged.
        -*) ;;
        *) templates+=("$token") ;;
      esac
    done
  fi

  if [[ ${#templates[@]} -eq 0 ]]; then
    printf 'ok\n'
    return 0
  fi
  local template
  for template in "${templates[@]}"; do
    if [[ ! $template =~ XXX+$ ]]; then
      printf 'bad\n'
      return 0
    fi
  done
  printf 'ok\n'
}

# --- part A — the matcher is precise on the fixture table ---------------------------------------
if [[ ! -f "$fixtures" ]]; then
  printf 'mktemp-template_test: FAILED — the fixture table is missing: %s\n' "$fixtures" >&2
  exit 1
fi

fixture_rows=0
while IFS=$'\t' read -r want line; do
  [[ -n "$want" ]] || continue
  [[ "${want:0:1}" != '#' ]] || continue
  fixture_rows=$((fixture_rows + 1))
  got="$(mktemp_template_verdict "$line")"
  if [[ "$got" != "$want" ]]; then
    printf '  FAIL  fixture got=%-4s want=%-4s %s\n' "$got" "$want" "$line" >&2
    fails=$((fails + 1))
  else
    printf '  ok    fixture %-4s %s\n' "$got" "$line"
  fi
done <"$fixtures"

# A table that read no row is a green that proved nothing.
if [[ $fixture_rows -lt 15 ]]; then
  printf 'mktemp-template_test: FAILED — the fixture table read %d rows; it must hold >= 15.\n' \
    "$fixture_rows" >&2
  exit 1
fi

# --- part B — no tracked shell file breaks the rule ----------------------------------------------
# The scan set is the tracked shell files: a .sh or .bash name, or a shell shebang. A document that
# quotes the broken form on purpose is therefore not scanned, and neither is the fixture table.
scan_files() {
  local file first_line
  while IFS= read -r file; do
    case "$file" in
      *.sh | *.bash)
        printf '%s\n' "$file"
        continue
        ;;
    esac
    # A submodule entry is a gitlink, not a file, and its repository has its own gate.
    [[ -f "${repository_root}/${file}" ]] || continue
    IFS= read -r first_line <"${repository_root}/${file}" || first_line=''
    if [[ $first_line =~ ^#!.*[/[:space:]](bash|sh|dash|zsh)([[:space:]]|$) ]]; then
      printf '%s\n' "$file"
    fi
  done < <(git -C "$repository_root" ls-files)
}

scanned=0
scanned_files=''
violations=''
while IFS= read -r file; do
  scanned=$((scanned + 1))
  scanned_files+="${file}"$'\n'
  path="${repository_root}/${file}"
  matches="$(grep -n -I -F -e mktemp -- "$path")" && grep_status=0 || grep_status=$?
  if [[ $grep_status -gt 1 ]]; then
    printf 'mktemp-template_test: FAILED — grep exited %d on %s\n' "$grep_status" "$file" >&2
    exit 1
  fi
  [[ $grep_status -eq 0 ]] || continue
  while IFS= read -r numbered; do
    [[ -n "$numbered" ]] || continue
    number="${numbered%%:*}"
    content="${numbered#*:}"
    verdict="$(mktemp_template_verdict "$content")"
    [[ "$verdict" == 'none' ]] || invocations_examined=$((invocations_examined + 1))
    if [[ "$verdict" == 'bad' ]]; then
      violations+="${file}:${number}: ${content}"$'\n'
    fi
  done <<<"$matches"
done < <(scan_files)

# Three guards against a scan that silently examined nothing — the failure this rule exists to
# prevent must not be able to hide inside the rule itself.
if [[ $scanned -lt 20 ]]; then
  printf 'mktemp-template_test: FAILED — the scan set holds %d files; the tree holds far more.\n' \
    "$scanned" >&2
  exit 1
fi
for required in 'scripts/assert-no-skipped-tests.sh' 'apps/agent-runtime/ctl.sh' '.githooks/pre-commit'; do
  if [[ $'\n'"$scanned_files" != *$'\n'"$required"$'\n'* ]]; then
    printf 'mktemp-template_test: FAILED — the scan set does not hold %s\n' "$required" >&2
    exit 1
  fi
done
if [[ $invocations_examined -lt 4 ]]; then
  printf 'mktemp-template_test: FAILED — the scan judged %d mktemp invocations; the tree holds >= 4.\n' \
    "$invocations_examined" >&2
  exit 1
fi

if [[ -n "$violations" ]]; then
  printf '  FAIL  repository scan — an mktemp template needs >= 3 trailing X'"'"'s (GNU rejects fewer):\n' >&2
  printf '%s' "$violations" | sed 's/^/          /' >&2
  fails=$((fails + 1))
else
  printf '  ok    repository scan — %d shell file(s), %d mktemp invocation(s), 0 violation(s)\n' \
    "$scanned" "$invocations_examined"
fi

if [[ $fails -ne 0 ]]; then
  printf '\nmktemp-template_test: %d failure(s)\n' "$fails" >&2
  exit 1
fi
printf '\nmktemp-template_test: all assertions passed (%d fixture rows, %d shell files)\n' \
  "$fixture_rows" "$scanned"
