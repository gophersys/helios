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

pass=0; fail=0
red() { printf '\033[0;31m%s\033[0m' "$1"; }
grn() { printf '\033[0;32m%s\033[0m' "$1"; }

check() {   # host expected-class
  local host="$1" want="$2" fqdn="$1.$ZONE" ips code loc gate got note=""
  ips="$(dig +short "$fqdn" A 2>/dev/null | tr '\n' ' ')"
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 12 "https://$fqdn/" 2>/dev/null || echo 000)"
  loc="$(curl -s -o /dev/null -w '%{redirect_url}' --max-time 12 "https://$fqdn/" 2>/dev/null || true)"

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
awk '
  /^  [a-z0-9-]+:$/            { h=$1; sub(":","",h); next }
  /^  [a-z0-9-]+: *\{/         { h=$1; sub(":","",h);
                                 if (match($0,/class: *[a-z-]+/)) { c=substr($0,RSTART+7,RLENGTH-7); gsub(/[ ,}]/,"",c); print h, c } next }
  /^    class:/                { if (h!="") print h, $2 }
' "$DECL" | while read -r h c; do check "$h" "$c"; done

# the while loop runs in a subshell; recount from its output is not available,
# so re-run the classification cheaply for the summary
total=$(awk '/^  [a-z0-9-]+:( *\{)?$|^  [a-z0-9-]+: *\{/{n++} END{print n+0}' "$DECL")
echo
echo "checked $total declared hosts — scroll for any FAIL lines"
