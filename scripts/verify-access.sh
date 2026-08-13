#!/usr/bin/env bash
# Assert every machine in contracts/access.yaml is reachable by its declared method.
#
# Read-only: one SSH command per host that echoes its hostname. Changes nothing.
# Exit 0 = every machine reachable AND identifying as itself. Exit 1 = drift.
#
# This is the access twin of verify-exposure.sh. Docs describe; this asserts.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DECL="$ROOT/contracts/access.yaml"
ONLY="${1:-}"
pass=0; fail=0; skip=0
red() { printf '\033[0;31m%s\033[0m' "$1"; }
grn() { printf '\033[0;32m%s\033[0m' "$1"; }
ylw() { printf '\033[0;33m%s\033[0m' "$1"; }

# Flatten both YAML forms (inline {a: b} and indented block) to: name|key|value
parse() {
  awk '
    /^  [a-z0-9-]+: *\{/ {
      name=$1; sub(":","",name); body=$0; sub(/^[^{]*\{/,"",body); sub(/\}[[:space:]]*$/,"",body)
      n=split(body,parts,","); for(i=1;i<=n;i++){ split(parts[i],kv,":"); k=kv[1]; v=kv[2]
        gsub(/^[ \t]+|[ \t]+$/,"",k); gsub(/^[ \t]+|[ \t]+$/,"",v); gsub(/"/,"",v)
        if(k!="") print name"|"k"|"v }
      next }
    /^  [a-z0-9-]+: *$/ { name=$1; sub(":","",name); next }
    /^    [a-z_]+:/ && name!="" {
      k=$1; sub(":","",k); v=substr($0,index($0,":")+1)
      sub(/#.*$/,"",v); gsub(/^[ \t]+|[ \t]+$/,"",v); gsub(/"/,"",v)
      print name"|"k"|"v }
  ' "$DECL"
}

get() { parse | awk -F'|' -v n="$1" -v k="$2" '$1==n && $2==k {print $3; exit}'; }
names() { parse | awk -F'|' '{print $1}' | awk '!seen[$0]++'; }

# ssh does not expand a tilde inside -i; it looks for a directory named "~".
keypath() { case "$1" in \~/*) printf '%s\n' "$HOME/${1#\~/}" ;; *) printf '%s\n' "$1" ;; esac; }

probe() {  # user host [key] -> prints hostname or an error token
  # IdentitiesOnly keeps the agent and the default identities out, so a PASS
  # proves the DECLARED key works and not some other key that happens to be
  # loaded. The ${id[@]+...} form is for bash 3.2, where "${empty[@]}" is
  # unbound under set -u.
  id=(); [ -n "${3:-}" ] && id=(-i "$3" -o IdentitiesOnly=yes)
  ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=8 -o BatchMode=yes \
      ${id[@]+"${id[@]}"} "$1@$2" 'echo HN:$(hostname)' 2>&1 | grep -o 'HN:[^ ]*' | head -1
}

echo "verifying access against contracts/access.yaml"
for m in $(names); do
  [ -n "$ONLY" ] && [ "$ONLY" != "$m" ] && continue
  method="$(get "$m" method)"; user="$(get "$m" user)"; addr="$(get "$m" address)"
  case "$method" in
    local)
      hn="$(hostname)"
      printf '  %s %-13s %-14s %s\n' "$(grn PASS)" "$m" "$method" "$hn"; pass=$((pass+1)) ;;
    tailscale-ssh|ssh-key)
      # A declared key that cannot be used FAILS and names the file. It must
      # never fall back to ssh's default identity: this check read no `key:` at
      # all until 2026-08-13, and 8 hosts passed only because their declared key
      # IS the default identity. The first host with a dedicated key exposed it.
      key=""
      if [ "$method" = ssh-key ]; then
        key="$(get "$m" key)"
        if [ -z "$key" ]; then
          printf '  %s %-13s %-14s declares method ssh-key but no key:\n' "$(red FAIL)" "$m" "$method"; fail=$((fail+1)); continue
        fi
        key="$(keypath "$key")"
        if [ ! -f "$key" ]; then
          printf '  %s %-13s %-14s declared key not found: %s\n' "$(red FAIL)" "$m" "$method" "$key"; fail=$((fail+1)); continue
        fi
      fi
      out="$(probe "$user" "$addr" "$key")"
      if [ -z "$out" ]; then
        printf '  %s %-13s %-14s unreachable as %s@%s\n' "$(red FAIL)" "$m" "$method" "$user" "$addr"; fail=$((fail+1))
      else
        got="${out#HN:}"
        # hostname must contain the declared name — catches a machine answering
        # at an address that now belongs to something else
        case "$got" in
          *"$m"*) printf '  %s %-13s %-14s %s\n' "$(grn PASS)" "$m" "$method" "$got"; pass=$((pass+1)) ;;
          *)      printf '  %s %-13s %-14s answered as %s (expected %s)\n' "$(red FAIL)" "$m" "$method" "$got" "$m"; fail=$((fail+1)) ;;
        esac
      fi ;;
    password)
      printf '  %s %-13s %-14s needs vault secret %s (not probed non-interactively)\n' "$(ylw SKIP)" "$m" "$method" "$(get "$m" secret)"; skip=$((skip+1)) ;;
    *)
      printf '  %s %-13s unknown method %s\n' "$(red FAIL)" "$m" "$method"; fail=$((fail+1)) ;;
  esac
done

echo
echo "  pass=$pass fail=$fail skip=$skip"
[ "$fail" -eq 0 ] || exit 1
