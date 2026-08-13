#!/usr/bin/env bash
# Assert the arc-org runner pool actually receives the macOS buildx SSH key.
#
# The Mac mini is a native arm64 buildx node reached over `docker -H ssh://`. The
# key is DIAL-ONLY on the mini (`command="... docker system dial-stdio",restrict`),
# so a build gets a BuildKit dial and nothing else. None of that helps if the key
# never arrives in the pod, or arrives in a form ssh refuses.
#
# Three ways this silently does not work, all asserted below:
#
#   1. THE SECRET NEVER MATERIALISES. An ExternalSecret must name the vault item
#      and point at ClusterSecretStore/vaultwarden, in the namespace the pool runs
#      in. A missing or misdirected store leaves an empty Secret and the mount
#      succeeds with an empty file.
#   2. THE KEY IS AN ENV VAR. A private key in the environment is printed by every
#      `env` dump and every debug log. ssh also cannot consume it from there.
#   3. THE MODE IS WRONG. ssh REFUSES a private key that is group- or
#      world-readable ("UNPROTECTED PRIVATE KEY FILE"). The kubelet's default
#      projection is 0644, so a mount with no explicit mode is dead on arrival —
#      and it fails only at the first build, not at sync.
#
# This pins PROPERTIES, not paths. The file name of the ExternalSecret, the
# Secret's own name, the volume name and the mount path are the implementer's
# choice. What must hold is: one vault-backed Secret, mounted as a file, owner-only.
#
# Exit 0 = every property holds. Exit 1 = at least one does not.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REGISTRY="$ROOT/platform/services/gitops/registry"
VAULT_ITEM="shared/eden/macos-buildx-key"
POOL="arc-org"
STORE_KIND="ClusterSecretStore"
STORE_NAME="vaultwarden"

pass=0; fail=0
red() { printf '\033[0;31m%s\033[0m' "$1"; }
grn() { printf '\033[0;32m%s\033[0m' "$1"; }

ok()   { printf '  %s %s\n' "$(grn PASS)" "$1"; pass=$((pass + 1)); }
bad()  { printf '  %s %s\n' "$(red FAIL)" "$1"; echo "::error::$1"; fail=$((fail + 1)); }

if ! command -v yq >/dev/null 2>&1; then
  # A missing tool is a failure, never a skip: a skipped structural check is a
  # green line that asserted nothing.
  printf '  %s yq is required and is not installed\n' "$(red FAIL)"
  exit 127
fi

# Kubernetes parses a manifest as YAML 1.1 (sigs.k8s.io/yaml -> yaml.v2), where a
# leading zero means OCTAL: `defaultMode: 0400` really is 0400. `yq -o=json`
# follows YAML 1.2 and reports that same scalar as decimal 400, which is 0620 —
# group-writable, and ssh refuses it. So read the RAW scalar and resolve it the
# way the API server does, or this check blesses a mode the cluster never applies.
mode_value() {  # raw scalar -> decimal value, or empty when unparseable
  case "$1" in
    0o[0-7]*) printf '%d\n' "$((8#${1#0o}))" ;;
    0[0-7]*)  printf '%d\n' "$((8#${1#0}))" ;;
    [0-9]*)   printf '%d\n' "$(($1))" ;;
    *)        printf '\n' ;;
  esac
}

# ssh's own rule: no permission for group or other. Owner must still be able to
# read it, so mode 0 is not "safe", it is unusable.
mode_is_owner_only() {  # decimal mode -> 0 when acceptable
  local m="$1"
  [ -n "$m" ] || return 1
  [ $((m & 63)) -eq 0 ] || return 1   # 0077 -> group+other bits
  [ $((m & 256)) -ne 0 ] || return 1  # 0400 -> owner read
  return 0
}

echo "verifying the $POOL pool receives $VAULT_ITEM"

# ---- 1. an ExternalSecret names the vault item ------------------------------
es_file=""
while IFS= read -r f; do
  hit="$(yq eval-all '
    select(.kind == "ExternalSecret")
    | [.spec.data[]?.remoteRef.key, .spec.dataFrom[]?.extract.key]
    | .[] | select(. == "'"$VAULT_ITEM"'")' "$f" 2>/dev/null)"
  if [ -n "$hit" ]; then es_file="$f"; break; fi
done < <(grep -rl 'kind: ExternalSecret' --include='*.yaml' --include='*.yml' "$ROOT" 2>/dev/null | grep -v '/\.git/')

if [ -z "$es_file" ]; then
  bad "no ExternalSecret in this repo names the vault item $VAULT_ITEM"
  echo
  echo "  pass=$pass fail=$fail"
  exit 1
fi
ok "ExternalSecret names $VAULT_ITEM (${es_file#"$ROOT"/})"

es() { yq eval-all "select(.kind == \"ExternalSecret\") | $1" "$es_file" 2>/dev/null; }

# ---- 2. it resolves through the vaultwarden ClusterSecretStore --------------
got_kind="$(es '.spec.secretStoreRef.kind')"
got_name="$(es '.spec.secretStoreRef.name')"
if [ "$got_kind" = "$STORE_KIND" ] && [ "$got_name" = "$STORE_NAME" ]; then
  ok "secretStoreRef is $STORE_KIND/$STORE_NAME"
else
  bad "secretStoreRef is ${got_kind:-<none>}/${got_name:-<none>}, expected $STORE_KIND/$STORE_NAME"
fi

# ---- 3. it lands in the namespace the pool runs in --------------------------
es_ns="$(es '.metadata.namespace')"

# ---- 4. the Secret it produces ---------------------------------------------
# ESO defaults target.name to metadata.name when target.name is absent.
secret_name="$(es '.spec.target.name // .metadata.name')"
[ -n "$secret_name" ] && [ "$secret_name" != "null" ] || secret_name=""
if [ -n "$secret_name" ]; then
  ok "materialises Secret '$secret_name' in namespace '${es_ns:-<none>}'"
else
  bad "ExternalSecret declares no target Secret name"
fi

# ---- 5. locate the pool by its runs-on label, not by file name --------------
app_file=""
for f in "$REGISTRY"/*.yaml; do
  [ -e "$f" ] || continue
  vals="$(yq '.spec.source.helm.values // ""' "$f" 2>/dev/null)"
  [ -n "$vals" ] || continue
  if [ "$(printf '%s\n' "$vals" | yq '.runnerScaleSetName // ""' 2>/dev/null)" = "$POOL" ]; then
    app_file="$f"; break
  fi
done
if [ -z "$app_file" ]; then
  bad "no Argo Application in the registry declares runnerScaleSetName: $POOL"
  echo
  echo "  pass=$pass fail=$fail"
  exit 1
fi
ok "found the $POOL scale set (${app_file#"$ROOT"/})"

app_ns="$(yq '.spec.destination.namespace // ""' "$app_file" 2>/dev/null)"
if [ -n "$es_ns" ] && [ "$es_ns" = "$app_ns" ]; then
  ok "ExternalSecret namespace matches the pool's namespace ($app_ns)"
else
  bad "ExternalSecret namespace '${es_ns:-<none>}' does not match the $POOL namespace '${app_ns:-<none>}'"
fi

# The runner pod spec lives inside the Helm values, which are a YAML STRING
# inside the Application. It has to be parsed a second time.
spec="$(yq '.spec.source.helm.values' "$app_file" 2>/dev/null)"
podq() { printf '%s\n' "$spec" | yq "$1" 2>/dev/null; }

# ---- 6. the Secret is mounted as a FILE ------------------------------------
vol=""
if [ -n "$secret_name" ]; then
  vol="$(podq '.template.spec.volumes[]? | select(.secret.secretName == "'"$secret_name"'") | .name' | head -1)"
fi
if [ -n "$vol" ]; then
  ok "mounted from a secret volume '$vol'"
else
  bad "no volume in the $POOL pod spec projects Secret '${secret_name:-<none>}'"
fi

mounted_in=""
if [ -n "$vol" ]; then
  mounted_in="$(podq '[.template.spec.containers[]?, .template.spec.initContainers[]?]
    | .[] | select(.volumeMounts[]?.name == "'"$vol"'") | .name' | head -1)"
fi
if [ -n "$mounted_in" ]; then
  ok "volume '$vol' is mounted into container '$mounted_in'"
elif [ -n "$vol" ]; then
  bad "volume '$vol' exists but no container mounts it — the key never reaches a build"
fi

# ---- 7. owner-only mode ----------------------------------------------------
if [ -n "$vol" ]; then
  default_raw="$(podq '.template.spec.volumes[] | select(.name == "'"$vol"'") | .secret.defaultMode // ""')"
  item_raw="$(podq '.template.spec.volumes[] | select(.name == "'"$vol"'") | .secret.items[]?.mode // ""')"
  raws=""
  if [ -n "$item_raw" ]; then raws="$item_raw"; else raws="$default_raw"; fi

  if [ -z "$raws" ]; then
    bad "volume '$vol' sets no mode — the kubelet projects 0644 and ssh refuses a group-readable key"
  else
    bad_mode=0
    while IFS= read -r raw; do
      [ -n "$raw" ] || continue
      m="$(mode_value "$raw")"
      if ! mode_is_owner_only "$m"; then
        bad "volume '$vol' mode '$raw' is not owner-only (renders $(printf '0%o' "${m:-0}")) — ssh refuses it"
        bad_mode=1
      fi
    done <<EOF
$raws
EOF
    [ "$bad_mode" -eq 0 ] && ok "mode is owner-only ($raws)"
  fi
fi

# ---- 8. never an environment variable --------------------------------------
if [ -n "$secret_name" ]; then
  env_hit="$(podq '[.template.spec.containers[]?, .template.spec.initContainers[]?]
    | .[] | (.env[]?.valueFrom.secretKeyRef.name, .envFrom[]?.secretRef.name)
    | select(. == "'"$secret_name"'")' | head -1)"
  if [ -n "$env_hit" ]; then
    bad "Secret '$secret_name' is exposed as an environment variable — a private key must be a file only"
  else
    ok "not exposed as an environment variable"
  fi
fi

echo
echo "  pass=$pass fail=$fail"
[ "$fail" -eq 0 ] || exit 1
