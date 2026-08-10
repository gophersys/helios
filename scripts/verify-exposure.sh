#!/usr/bin/env bash
# Assert that every hostname is exposed the way contracts/exposure.yaml declares.
#
# This exists because grafana.mateosegura.com silently moved from tailnet to
# public and no document noticed. Documentation describes; this asserts.
#
# Read-only: resolves DNS and issues HTTP HEADs. Changes nothing.
# Exit 0 = reality matches the declaration. Exit 1 = drift.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DECL="$ROOT/contracts/exposure.yaml"
ZONE="$(awk '/^zone:/{print $2}' "$DECL")"
VIP="$(awk '/homelab_vip:/{print $2}' "$DECL")"
PUB="$(awk '/prod_public:/{print $2}' "$DECL")"

# Resolvers are tried in order until one actually yields an answer. Order alone
# is not enough: the ARC runner has no `dig` at all, and a `dig` that exists but
# fails would otherwise make every host look like it has no DNS record — turning
# a tooling gap into a false "drift detected".
resolve() {
  local out
  if command -v dig >/dev/null 2>&1; then
    out="$(dig +short "$1" A 2>/dev/null | tr '\n' ' ')"
    [ -n "${out// /}" ] && { printf '%s' "$out"; return 0; }
  fi
  if command -v getent >/dev/null 2>&1; then
    out="$(getent ahostsv4 "$1" 2>/dev/null | awk '{print $1}' | sort -u | tr '\n' ' ')"
    [ -n "${out// /}" ] && { printf '%s' "$out"; return 0; }
  fi
  if command -v python3 >/dev/null 2>&1; then
    out="$(python3 -c "import socket,sys
try: print(' '.join(sorted({i[4][0] for i in socket.getaddrinfo(sys.argv[1],None,socket.AF_INET)})))
except Exception: pass" "$1" 2>/dev/null)"
    [ -n "${out// /}" ] && { printf '%s' "$out"; return 0; }
  fi
  return 1
}
command -v curl >/dev/null 2>&1 || { echo "verify-exposure: curl is required" >&2; exit 127; }
resolve mateosegura.com >/dev/null 2>&1 || {
  echo "verify-exposure: no working resolver (tried dig, getent, python3)" >&2; exit 127; }

pass=0; fail=0
red() { printf '\033[0;31m%s\033[0m' "$1"; }
grn() { printf '\033[0;32m%s\033[0m' "$1"; }

check() {   # host expected-class
  local host="$1" want="$2" fqdn="$1.$ZONE" ips code loc gate got note=""
  ips="$(resolve "$fqdn")"
  # one request, both fields — two calls double-count failures as "000000"
  local probe; probe="$(curl -s -o /dev/null -w '%{http_code} %{redirect_url}' --max-time 12 "https://$fqdn/" 2>/dev/null || echo "000 ")"
  code="${probe%% *}"; loc="${probe#* }"

  # classify what we actually observe
  case "$ips" in
    *"$VIP"*)                       got=tailnet ;;
    *104.21.*|*172.67.*)            got=public ;;
    *"$PUB"*)                       got=direct ;;
    "")                             got=no-record ;;
    *)                              got=unknown ;;
  esac
  case "$loc" in
    *cloudflareaccess*) gate="CF-Access" ;;
    *oauth2*)           gate="oauth2-proxy" ;;
    *)                  gate="none/app" ;;
  esac

  local ok=1
  case "$want" in
    tailnet)
      # must NOT be publicly resolvable to anything routable
      [ "$got" = "tailnet" ] || { ok=0; note="publicly reachable ($got)"; }
      ;;
    public-access)
      [ "$got" = "public" ] || { ok=0; note="not on the tunnel ($got)"; }
      [ "$gate" = "CF-Access" ] || { ok=0; note="${note:+$note; }NOT Access-gated (saw $gate)"; }
      ;;
    public-open)
      [ "$got" = "public" ] || { ok=0; note="not on the tunnel ($got)"; }
      ;;
    direct-auth)
      [ "$got" = "direct" ] || { ok=0; note="not on the prod public IP ($got)"; }
      [ "$gate" = "oauth2-proxy" ] || { ok=0; note="${note:+$note; }no oauth2-proxy gate (saw $gate, HTTP $code)"; }
      ;;
  esac

  if [ "$ok" = 1 ]; then
    printf '  %s %-11s %-14s http=%-4s gate=%s\n' "$(grn PASS)" "$host" "$want" "$code" "$gate"; pass=$((pass+1))
  else
    printf '  %s %-11s %-14s %s\n' "$(red FAIL)" "$host" "$want" "$note"; fail=$((fail+1))
  fi
}

echo "verifying exposure against contracts/exposure.yaml"
# parse "  <host>:" blocks with a class:, plus inline {class: x} form
total=0
while read -r h c; do
  total=$((total + 1))
  check "$h" "$c"
done < <(awk '
  /^  [a-z0-9-]+:$/            { h=$1; sub(":","",h); next }
  /^  [a-z0-9-]+: *\{/         { h=$1; sub(":","",h);
                                 if (match($0,/class: *[a-z-]+/)) { c=substr($0,RSTART+7,RLENGTH-7); gsub(/[ ,}]/,"",c); print h, c } next }
  /^    class:/                { if (h!="") print h, $2 }
' "$DECL")

# Process substitution, NOT a pipe. A pipe runs the loop in a subshell, so every
# increment of `fail` is discarded when it exits, and the script's last statement
# was an echo — which always succeeds. The result: this verifier printed FAIL
# lines and exited 0. Proven by forcing every host into drift: 13 FAIL lines,
# exit code 0. The CI job that exists BECAUSE grafana.mateosegura.com silently
# went public could therefore never fail. Its 2 sibling verifiers,
# verify-access.sh and verify-registry-paths.sh, both already end on the count.
echo
echo "  checked=$total fail=$fail"
[ "$fail" -eq 0 ] || exit 1
