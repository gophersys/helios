#!/usr/bin/env bash
#
# scripts/mktemp-template_test.sh — repository rule: an mktemp invocation passes at most 1 template,
# and that template carries >= 3 trailing X's.
#
# A mac-only form (GNU exits 1 where BSD accepts) reaches CI green on a laptop and dies in the lane.
#
# SCOPE — read this before you read a green run as a repository-wide guarantee.
#   COVERED: the shell files of THIS repository, tracked AND untracked — a .sh or .bash name, or a
#     shell shebang on the first line. Untracked is deliberate: a brand-new script is exactly where
#     a fresh violation enters the tree, and `git ls-files` alone cannot see one.
#   NOT COVERED: the 3 submodules — libs/, infrastructure/ and .devcontainer/. Their content is a
#     gitlink here, not a file, and each submodule repository carries its own gate; libs/go/_ctl/
#     lib.sh alone holds 4 mktemp calls that this scan never reads. Also not covered: a non-shell
#     file, the `run:` block of a CI yaml, a Dockerfile, a Makefile. A violation in any of those
#     passes this test.
#   LIMIT: the leader set of mktemp_command_position is ENUMERATED, not a shell parser. It holds
#     the shell keywords, the wrappers sudo/exec/command/eval/env/time/timeout/nohup and the
#     command string of trap. A wrapper outside that list — `runner mktemp -t bad` — is read as
#     prose and passes. This test judges literal text only, so a template built at run time
#     (`mktemp "$TEMPLATE"`) carries no X's to read and falls on the strict side: bad. The fixture
#     table pins both limits with a row.
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

# Part C plants this file to prove the scan reaches an untracked path. A leftover from an
# interrupted run would be scanned by part B and reported as a violation, so it goes first.
probe_relative='scripts/testdata/untracked-scan-probe.tmp.sh'
probe_path="${repository_root}/${probe_relative}"
rm -f "$probe_path"

fails=0
invocations_examined=0

# The word mktemp also opens a variable name (mktemp_version=...) and closes nothing, so the text
# on the right of the occurrence is judged too. `;`, `&` and `|` end the command right there.
mktemp_follower_pattern='^([[:space:]]|[);&|]|$)'
# A command string that a keyword runs: trap 'cmd' EXIT, trap "cmd" EXIT.
mktemp_quoted_command_pattern='(^|[[:space:];&|(`])trap$'
mktemp_command_quote=''

# mktemp_command_position <the text on the line before this occurrence> -> 0 when the occurrence
# stands in command position. It sets mktemp_command_quote to the quote that opened the command
# string, or to the empty string when no quote opened it.
mktemp_command_position() {
  local prefix="$1" last
  mktemp_command_quote=''

  # A quote directly before the word opens a word, not a command — printf 'mktemp %s\n' is prose.
  # It opens a command only after a keyword that runs a command string.
  case "$prefix" in
    *[\"\'])
      mktemp_command_quote="${prefix: -1}"
      prefix="${prefix%?}"
      while [[ $prefix == *[[:space:]] ]]; do prefix="${prefix%?}"; done
      [[ $prefix =~ $mktemp_quoted_command_pattern ]] && return 0
      mktemp_command_quote=''
      return 1
      ;;
  esac

  while [[ $prefix == *[[:space:]] ]]; do prefix="${prefix%?}"; done

  # The line starts here, or a metacharacter ended the command before it.
  [[ -z "$prefix" ]] && return 0
  case "$prefix" in
    *[\;\&\|\(\`\!\{]) return 0 ;;
  esac

  # The word before it opens a command: a shell keyword whose body is a command list, or a wrapper
  # that runs its arguments. `if true; then mktemp -t bad; fi` and `sudo mktemp -t bad` are both
  # real invocations that a metacharacter-only reading misses entirely. A wrapper may carry its own
  # options and operands first — `timeout 5 mktemp`, `env FOO=bar mktemp` — so the walk steps back
  # over an option, a number and an assignment, 4 words at most, and judges what opens them. The
  # set is enumerated: a wrapper outside it reads as prose. See LIMIT in the file header.
  local steps=0
  while [[ $steps -lt 4 ]]; do
    last="${prefix##*[[:space:]]}"
    case "$last" in
      if | elif | then | else | while | until | do) return 0 ;;
      sudo | exec | command | eval | env | time | timeout | nohup) return 0 ;;
    esac
    case "$last" in
      -* | [0-9]* | *=*) ;;
      *) return 1 ;;
    esac
    [[ $prefix == *[[:space:]]* ]] || return 1
    prefix="${prefix%[[:space:]]*}"
    while [[ $prefix == *[[:space:]] ]]; do prefix="${prefix%?}"; done
    steps=$((steps + 1))
  done
  return 1
}

# mktemp_template_verdict <source line> -> echoes none | ok | bad
mktemp_template_verdict() {
  local line="$1"
  local remainder consumed='' before after prefix leading
  local -a invocations=() quotes=()

  # A whole-line comment is prose. It is never executed, so it can hold any broken form.
  leading="${line%%[![:space:]]*}"
  if [[ "${line#"$leading"}" == '#'* ]]; then
    printf 'none\n'
    return 0
  fi

  remainder="$line"
  while [[ $remainder == *mktemp* ]]; do
    before="${remainder%%mktemp*}"
    after="${remainder#*mktemp}"
    prefix="${consumed}${before}"
    if mktemp_command_position "$prefix" && [[ $after =~ $mktemp_follower_pattern ]]; then
      invocations+=("$after")
      quotes+=("$mktemp_command_quote")
    fi
    consumed="${prefix}mktemp"
    remainder="$after"
  done
  if [[ ${#invocations[@]} -eq 0 ]]; then
    printf 'none\n'
    return 0
  fi

  local index
  for index in "${!invocations[@]}"; do
    if [[ "$(mktemp_arguments_verdict "${invocations[index]}" "${quotes[index]}")" == 'bad' ]]; then
      printf 'bad\n'
      return 0
    fi
  done
  printf 'ok\n'
}

# mktemp_arguments_verdict <everything after one mktemp in command position> [opening quote] -> ok | bad
mktemp_arguments_verdict() {
  local arguments="$1" quote="${2:-}"
  # A command string ends at the quote that closes it: in `trap "mktemp -d -t x.XXXXXX" EXIT` the
  # word EXIT belongs to trap, not to mktemp.
  if [[ -n "$quote" ]]; then
    arguments="${arguments%%"$quote"*}"
  fi
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
        # GNU takes the next word for these two: -p DIR and --suffix SUFF are required arguments.
        -p | --suffix) expects_value=1 ;;
        # The argument of --tmpdir is OPTIONAL, so getopt_long attaches it only as --tmpdir=DIR.
        # Bare --tmpdir leaves the next word an operand: `mktemp --tmpdir bad` exits 1 with "too
        # few X's in template", and `mktemp --tmpdir /var/tmp x.XXXXXX` exits 1 with "too many
        # templates" (both read from GNU coreutils 9.4 in ghcr.io/gophersys/base).
        --tmpdir) ;;
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
  # GNU mktemp accepts 1 template operand at most; a second one is "too many templates", exit 1.
  if [[ ${#templates[@]} -gt 1 ]]; then
    printf 'bad\n'
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

# --- part B — no shell file of this repository breaks the rule ------------------------------------
# The scan set is every shell file git knows about, tracked or untracked: a .sh or .bash name, or a
# shell shebang. A document that quotes the broken form on purpose is therefore not scanned, and
# neither is the fixture table. A submodule is a gitlink here, so its files are out of scope.
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
  done < <(
    git -C "$repository_root" ls-files
    git -C "$repository_root" ls-files --others --exclude-standard
  )
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
  printf '  FAIL  repository scan — an mktemp invocation passes 1 template at most, and it needs >= 3 trailing X'"'"'s (GNU rejects both):\n' >&2
  printf '%s' "$violations" | sed 's/^/          /' >&2
  fails=$((fails + 1))
else
  printf '  ok    repository scan — %d shell file(s) tracked+untracked, %d mktemp invocation(s), 0 violation(s)\n' \
    "$scanned" "$invocations_examined"
fi

# --- part C — the scan set really reaches an untracked file ---------------------------------------
# `git ls-files` lists tracked paths only, so before this the scan was blind to a NEW script — the
# exact moment a fresh violation enters the tree — and returned 0 with a planted violation present.
# The probe plants that case, asks the scan set for it, and removes it again.
remove_probe() { rm -f "$probe_path"; }
trap remove_probe EXIT
# The word is passed as an operand, never written in command position, so the scan of part B does
# not read this line as a violation of the very file that asserts the rule.
printf '#!/usr/bin/env bash\n%s -t untracked-scan-probe\n' 'mktemp' >"$probe_path"
probe_state="$(git -C "$repository_root" status --porcelain -- "$probe_relative")"
probe_seen="$(scan_files | grep -c -F -x -e "$probe_relative")" || probe_seen=0
remove_probe
trap - EXIT

if [[ "$probe_state" != '?? '* ]]; then
  printf 'mktemp-template_test: FAILED — the probe %s is not untracked (git says: %s).\n' \
    "$probe_relative" "$probe_state" >&2
  exit 1
fi
if [[ "$probe_seen" -ne 1 ]]; then
  printf '  FAIL  untracked probe — the scan set holds the planted untracked script %d time(s), want 1\n' \
    "$probe_seen" >&2
  printf '          an untracked shell file is invisible to plain git ls-files; the scan set must\n' >&2
  printf '          also read: git ls-files --others --exclude-standard\n' >&2
  fails=$((fails + 1))
elif [[ "$(mktemp_template_verdict 'mktemp -t untracked-scan-probe')" != 'bad' ]]; then
  printf '  FAIL  untracked probe — the planted line is in the scan set but judged not-bad\n' >&2
  fails=$((fails + 1))
else
  printf '  ok    untracked probe — a planted untracked script enters the scan set and is judged bad\n'
fi

if [[ $fails -ne 0 ]]; then
  printf '\nmktemp-template_test: %d failure(s)\n' "$fails" >&2
  exit 1
fi
printf '\nmktemp-template_test: all assertions passed (%d fixture rows, %d shell files)\n' \
  "$fixture_rows" "$scanned"
