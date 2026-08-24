#!/usr/bin/env bash
# Assert every vault item this repo names resolves to EXACTLY ONE item.
#
# THE DEFECT CLASS
# The repo links to a secret by NAME and never by value (.claude/rules/10-secrets.md).
# Nothing checked that the name on the left of that link exists. On 2026-08-13 the
# Mac mini enrolment shipped `secret: shared/macos-ci-runner/account-credentials`,
# an item that had never existed. It was found by a hand query, not by any gate.
#
# WHY TWO MATCHES ARE AS BAD AS ZERO
# The ClusterSecretStore is a webhook provider
# (platform/core/secrets-operator/manifests/clustersecretstore.yaml):
#
#     url:      .../list/object/items?search={{ .remoteRef.key }}
#     jsonPath: $.data.data[0].notes
#
# Resolution is a SEARCH and the value taken is the FIRST match. The search is a
# substring match, so `shared/ssh/pve` matches 3 items today. Zero matches means
# the Secret never materialises and the workload fails at start. TWO matches
# means a secret IS delivered, silently, and it may be the wrong one. Both are
# failures here.
#
# WHY THIS IS LOCAL-ONLY, LIKE verify-access
# It has to ask the real vault. A CI runner has no route to Vaultwarden and no
# unlocked session, and a recorded copy of the item list would be vault state
# stored in git: it would keep reporting green after the real item was deleted.
# So there is no fixture and no offline mode. Run it by hand from a machine with
# an unlocked vault, after any change to a secret reference.
#
# FAIL, NEVER SKIP
# A missing `bw`, a locked vault or an absent session is a FAILURE that names
# what is missing. A credential check that skips itself reads as a pass.
#
# Values never leave the vault: this reads item NAMES and counts only.
#
# Exit 0 = every reference resolves to exactly one item. Exit 1 = it does not.
# Exit 127 = a required tool is missing.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ACCESS="$ROOT/contracts/access.yaml"
ONLY="${1:-}"

pass=0; fail=0
red() { printf '\033[0;31m%s\033[0m' "$1"; }
grn() { printf '\033[0;32m%s\033[0m' "$1"; }

missing=()
for t in bw jq yq; do
  command -v "$t" >/dev/null 2>&1 || missing+=("$t")
done
if [ "${#missing[@]}" -gt 0 ]; then
  printf '  %s missing required tool(s): %s\n' "$(red FAIL)" "${missing[*]}"
  printf '        install the Bitwarden CLI with: brew install bitwarden-cli\n'
  exit 127
fi

# An unset session is the common case and it must fail loudly, not silently
# resolve nothing. `bw status` prints JSON with no secret in it.
status="$(bw status 2>&1 | jq -r '.status' 2>/dev/null)"
if [ "$status" != "unlocked" ]; then
  printf '  %s vault is not unlocked (status: %s)\n' "$(red FAIL)" "${status:-unreadable}"
  # shellcheck disable=SC2016  # this is the literal command to copy, not an expansion
  printf '        export BW_SESSION="$(bw unlock --raw)" and run this again\n'
  exit 1
fi

# `bw list` reads the LOCAL encrypted cache. Without this sync an item deleted in
# the vault still answers here, which is a false PASS on exactly the question
# being asked.
if ! bw sync >/dev/null; then
  printf '  %s bw sync failed — the local cache may be stale, so a PASS would not be trustworthy\n' "$(red FAIL)"
  exit 1
fi

# ---- collect every vault reference in the repo -------------------------------
# Emitted as "<where>|<vault item name>". A reference with an EMPTY name is an
# ExternalSecret whose shape this extractor did not recognise. It is reported as
# a failure and never dropped: a check that silently stops covering a manifest is
# the same defect class it exists to catch.
refs() {
  local f
  while IFS= read -r f; do
    # A Helm chart TEMPLATE (e.g. platform/services/observability/chart/
    # templates/) is Go template source, so yq cannot parse it — and until
    # 2026-08-24 the 2>/dev/null below dropped its references SILENTLY, leaving
    # a vault item named only there covered by no gate: the exact defect class
    # this header names. For a file yq cannot read, extract every
    # `remoteRef:`+`key:` pair textually. If the file names an ExternalSecret
    # and no key can be extracted, the empty-ref line below makes it FAIL as
    # unrecognised — extend the extractor then, never let the file vanish.
    if ! yq eval-all -N 'true' "$f" >/dev/null 2>&1; then
      local id keys k
      id="${f#"$ROOT"/} (helm template)"
      keys="$(awk '$1 == "remoteRef:" {want=1; next} want && $1 == "key:" {print $2; want=0}' "$f")"
      if [ -z "$keys" ]; then
        printf '%s|\n' "$id"
      else
        while IFS= read -r k; do printf '%s|%s\n' "$id" "$k"; done <<< "$keys"
      fi
      continue
    fi
    yq eval-all -o=json 'select(.kind == "ExternalSecret")' "$f" 2>/dev/null \
      | jq -r --arg f "${f#"$ROOT"/}" '
          ($f + " " + (.metadata.namespace // "-") + "/" + (.metadata.name // "-")) as $id
          | ([.spec.data[]?.remoteRef.key] + [.spec.dataFrom[]?.extract.key]
             | map(select(type == "string" and length > 0))) as $k
          | if ($k | length) == 0 then "\($id)|" else $k[] | "\($id)|\(.)" end'
  done < <(grep -rl 'kind: ExternalSecret' --include='*.yaml' --include='*.yml' "$ROOT" 2>/dev/null | grep -v '/\.git/')

  # contracts/access.yaml names a vault item per machine. This is where the
  # 2026-08-13 defect was, so a check that skipped it would miss its own reason
  # for existing.
  if [ -f "$ACCESS" ]; then
    yq -o=json '.machines' "$ACCESS" 2>/dev/null \
      | jq -r 'to_entries[] | select(.value.secret) | "contracts/access.yaml \(.key)|\(.value.secret)"'
  fi
}

echo "verifying every vault reference resolves to exactly one item"

seen=""
while IFS='|' read -r where ref; do
  [ -n "$where" ] || continue
  if [ -z "$ref" ]; then
    printf '  %s %-52s no vault reference found — unrecognised ExternalSecret shape\n' "$(red FAIL)" "$where"
    echo "::error::$where declares no recognisable vault reference"
    fail=$((fail + 1))
    continue
  fi
  [ -n "$ONLY" ] && [ "$ONLY" != "$ref" ] && continue

  # One query per distinct name, not per reference site.
  case "$seen" in *"[$ref]"*) continue ;; esac
  seen="${seen}[$ref]"

  # One query. jq emits "<count><TAB><names>", so the count comes from the array
  # length and never from counting separators in a name. Only names and a count
  # are read: the notes body IS the secret and it never enters a variable here.
  answer="$(bw list items --search "$ref" | jq -r '"\(length)\t\([.[].name] | join(", "))"')"
  rc=$?
  if [ "$rc" -ne 0 ]; then
    printf '  %s %-52s vault query failed (rc=%s)\n' "$(red FAIL)" "$ref" "$rc"
    fail=$((fail + 1)); continue
  fi
  n="${answer%%	*}"
  names="${answer#*	}"

  case "$n" in
    1) printf '  %s %-52s 1 match\n' "$(grn PASS)" "$ref"; pass=$((pass + 1)) ;;
    0) printf '  %s %-52s NO match — the Secret will never materialise (%s)\n' "$(red FAIL)" "$ref" "$where"
       echo "::error::vault item not found: $ref (named by $where)"
       fail=$((fail + 1)) ;;
    *) printf '  %s %-52s %s matches — the provider takes the first, silently: %s (%s)\n' "$(red FAIL)" "$ref" "$n" "$names" "$where"
       echo "::error::vault reference is ambiguous: $ref matches $n items (named by $where)"
       fail=$((fail + 1)) ;;
  esac
done < <(refs)

if [ "$pass" -eq 0 ] && [ "$fail" -eq 0 ]; then
  # An empty run is not a pass. If the extractor finds nothing, it is broken or
  # the repo lost every ExternalSecret; both deserve red.
  printf '  %s no vault reference found anywhere in the repo — the extractor is broken\n' "$(red FAIL)"
  exit 1
fi

echo
echo "  pass=$pass fail=$fail"
[ "$fail" -eq 0 ] || exit 1
