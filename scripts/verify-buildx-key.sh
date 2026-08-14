#!/usr/bin/env bash
# Assert the arc-org runner pool actually receives the buildkit CLIENT CERTS.
#
# The Mac mini (machines/services/macos-ci-runner) runs a standalone `buildkitd`
# that listens on tcp://10.168.0.92:1234 and exposes the BUILD API only, over
# mutual TLS. A build reaches it with buildx `--driver remote`, so the runner pod
# needs THREE PEM files on disk — the CA, the client certificate and the client
# key. This replaced an SSH key that reached the Docker Engine API (root on the
# mini's VM, task #66); that key and its vault item are deleted.
#
# Four ways this silently does not work, all asserted below:
#
#   1. THE SECRET NEVER MATERIALISES, OR IS INCOMPLETE. One ExternalSecret must
#      name the THREE vault items and point at ClusterSecretStore/vaultwarden in
#      the pool's namespace. It must produce EXACTLY the three data keys the mount
#      and the `--driver-opt` step read — a floor of "at least one" is not
#      completeness (task #71): two of three certs missing still passes a floor,
#      and mTLS then fails with no hint why.
#   2. THE CERTS ARE ENV VARS. A private key in the environment is printed by
#      every `env` dump and every debug log, and buildx cannot read a file path
#      from there.
#   3. THE MODE IS WRONG. The mount carries the client's private key. A
#      group- or world-readable key.pem is refused by tls, and the kubelet's
#      default projection is 0644 — dead on arrival, and only at the first build.
#   4. THE CERTS LAND WHERE NOTHING READS THEM. docs/ci-substrate.md's
#      `--driver remote` step reads cacert/cert/key from fixed paths. A cert
#      mounted at any other path is delivered to a path nothing reads — the
#      CONFIG-DEAD-STATE class.
#
# This pins PROPERTIES, not paths. The ExternalSecret's file name, the Secret's
# own name and the volume name are the implementer's choice. What must hold is:
# one vault-backed Secret carrying exactly the three certs, mounted read-only as a
# directory, owner-only, at the path the documented buildx step reads.
#
# Exit 0 = every property holds. Exit 1 = at least one does not. Exit 127 = yq
# is missing.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REGISTRY="$ROOT/platform/services/gitops/registry"
DOC="$ROOT/docs/ci-substrate.md"

VAULT_PREFIX="shared/eden/buildkit-client"
EXPECTED_ITEMS=(
  shared/eden/buildkit-client-ca
  shared/eden/buildkit-client-cert
  shared/eden/buildkit-client-key
)
EXPECTED_KEYS=(ca.pem cert.pem key.pem)   # the file names the mount must project
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

# setnorm: a newline list -> sorted, unique, blank-free, space-joined. So every
# set comparison below is order-independent and a duplicate cannot inflate it.
setnorm() { printf '%s\n' "$1" | awk 'NF' | sort -u | tr '\n' ' '; }

# Kubernetes parses a manifest as YAML 1.1 (sigs.k8s.io/yaml -> yaml.v2), where a
# leading zero means OCTAL: `defaultMode: 0400` really is 0400. `yq -o=json`
# follows YAML 1.2 and reports that same scalar as decimal 400, which is 0620 —
# group-writable. So read the RAW scalar and resolve it the way the API server
# does, or this check blesses a mode the cluster never applies. This is the
# finding that mattered most under the SSH design, and it matters more here
# because it now guards a private KEY that lives beside two certs.
mode_value() {  # raw scalar -> decimal value, or empty when unparseable
  case "$1" in
    0o[0-7]*) printf '%d\n' "$((8#${1#0o}))" ;;
    0[0-7]*)  printf '%d\n' "$((8#${1#0}))" ;;
    [0-9]*)   printf '%d\n' "$(($1))" ;;
    *)        printf '\n' ;;
  esac
}

# No permission for group or other. Owner must still be able to read it, so mode 0
# is not "safe", it is unusable.
mode_is_owner_only() {  # decimal mode -> 0 when acceptable
  local m="$1"
  [ -n "$m" ] || return 1
  [ $((m & 63)) -eq 0 ] || return 1   # 0077 -> group+other bits
  [ $((m & 256)) -ne 0 ] || return 1  # 0400 -> owner read
  return 0
}

want_items="$(setnorm "$(printf '%s\n' "${EXPECTED_ITEMS[@]}")")"
want_keys="$(setnorm "$(printf '%s\n' "${EXPECTED_KEYS[@]}")")"

echo "verifying the $POOL pool receives the buildkit client certs ($want_keys)"

# ---- 1. locate the ExternalSecret by the vault items it names ---------------
es_file=""
while IFS= read -r f; do
  keys="$(yq eval-all '
    select(.kind == "ExternalSecret") | .spec.data[]?.remoteRef.key' "$f" 2>/dev/null)"
  case "$keys" in *"$VAULT_PREFIX"*) es_file="$f"; break ;; esac
done < <(grep -rl 'kind: ExternalSecret' --include='*.yaml' --include='*.yml' "$ROOT" 2>/dev/null | grep -v '/\.git/')

if [ -z "$es_file" ]; then
  bad "no ExternalSecret in this repo names a $VAULT_PREFIX-* vault item"
  echo
  echo "  pass=$pass fail=$fail"
  exit 1
fi
ok "ExternalSecret names the buildkit client certs (${es_file#"$ROOT"/})"

es() { yq eval-all "select(.kind == \"ExternalSecret\") | $1" "$es_file" 2>/dev/null; }

# ---- 2. it names EXACTLY the three vault items — completeness, not a floor ---
got_items="$(setnorm "$(es '.spec.data[].remoteRef.key')")"
if [ "$got_items" = "$want_items" ]; then
  ok "names exactly the three vault items ($got_items)"
else
  bad "vault items are {$got_items}, expected exactly {$want_items}"
fi

# ---- 3. it produces EXACTLY the three data keys the mount needs --------------
got_keys="$(setnorm "$(es '.spec.data[].secretKey')")"
if [ "$got_keys" = "$want_keys" ]; then
  ok "produces exactly the three data keys ($got_keys)"
else
  bad "data keys are {$got_keys}, expected exactly {$want_keys} — the mount and --driver-opt need all three"
fi

# ---- 4. it resolves through the vaultwarden ClusterSecretStore --------------
got_kind="$(es '.spec.secretStoreRef.kind')"
got_name="$(es '.spec.secretStoreRef.name')"
if [ "$got_kind" = "$STORE_KIND" ] && [ "$got_name" = "$STORE_NAME" ]; then
  ok "secretStoreRef is $STORE_KIND/$STORE_NAME"
else
  bad "secretStoreRef is ${got_kind:-<none>}/${got_name:-<none>}, expected $STORE_KIND/$STORE_NAME"
fi

# ---- 5. it lands in a namespace and produces a named Secret -----------------
es_ns="$(es '.metadata.namespace')"
# ESO defaults target.name to metadata.name when target.name is absent.
secret_name="$(es '.spec.target.name // .metadata.name')"
[ -n "$secret_name" ] && [ "$secret_name" != "null" ] || secret_name=""
if [ -n "$secret_name" ]; then
  ok "materialises Secret '$secret_name' in namespace '${es_ns:-<none>}'"
else
  bad "ExternalSecret declares no target Secret name"
fi

# ---- 6. locate the pool by its runs-on label, not by file name --------------
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

# ---- 7. a volume projects the Secret ----------------------------------------
vol=""
if [ -n "$secret_name" ]; then
  vol="$(podq '.template.spec.volumes[]? | select(.secret.secretName == "'"$secret_name"'") | .name' | head -1)"
fi
if [ -n "$vol" ]; then
  ok "mounted from a secret volume '$vol'"
else
  bad "no volume in the $POOL pod spec projects Secret '${secret_name:-<none>}'"
fi

# ---- 8. it is mounted into a container, read-only, as a directory -----------
mount_path=""; read_only=""; sub_path=""; mounted_in=""
if [ -n "$vol" ]; then
  mount_path="$(podq '[.template.spec.containers[]?, .template.spec.initContainers[]?]
    | .[].volumeMounts[]? | select(.name == "'"$vol"'") | .mountPath' | head -1)"
  read_only="$(podq '[.template.spec.containers[]?, .template.spec.initContainers[]?]
    | .[].volumeMounts[]? | select(.name == "'"$vol"'") | .readOnly // false' | head -1)"
  sub_path="$(podq '[.template.spec.containers[]?, .template.spec.initContainers[]?]
    | .[].volumeMounts[]? | select(.name == "'"$vol"'") | .subPath // ""' | head -1)"
  mounted_in="$(podq '[.template.spec.containers[]?, .template.spec.initContainers[]?]
    | .[] | select(.volumeMounts[]?.name == "'"$vol"'") | .name' | head -1)"
fi

if [ -n "$mounted_in" ]; then
  ok "volume '$vol' is mounted into container '$mounted_in' at '$mount_path'"
elif [ -n "$vol" ]; then
  bad "volume '$vol' exists but no container mounts it — the certs never reach a build"
fi

if [ -n "$vol" ]; then
  if [ "$read_only" = "true" ]; then
    ok "the cert mount is readOnly"
  else
    bad "the cert mount is not readOnly (readOnly=${read_only:-<unset>}) — a build must not rewrite its own client key"
  fi
fi

# A subPath projects ONE file, not the directory the three certs need. The
# --driver-opt line reads three paths under one directory, so a subPath silently
# drops two of them.
if [ -n "$vol" ]; then
  if [ -z "$sub_path" ]; then
    ok "the mount is a directory (no subPath)"
  else
    bad "the cert mount uses subPath '$sub_path' — that projects a single file, not the three-cert directory"
  fi
fi

# ---- 9. exactly the three certs land at the mount ---------------------------
# With no items filter every data key lands as a file; with an items filter only
# the listed keys land. Either way the set that lands must be exactly the three.
if [ -n "$vol" ]; then
  items_keys="$(podq '.template.spec.volumes[] | select(.name == "'"$vol"'") | .secret.items[]?.key')"
  if [ -n "$items_keys" ]; then landed="$(setnorm "$items_keys")"; else landed="$got_keys"; fi
  if [ "$landed" = "$want_keys" ]; then
    ok "exactly the three certs land at the mount ($landed)"
  else
    bad "the files that land are {$landed}, expected exactly {$want_keys}"
  fi
fi

# ---- 10. owner-only mode — the mode trap, now over a private key ------------
if [ -n "$vol" ]; then
  default_raw="$(podq '.template.spec.volumes[] | select(.name == "'"$vol"'") | .secret.defaultMode // ""')"
  item_raw="$(podq '.template.spec.volumes[] | select(.name == "'"$vol"'") | .secret.items[]?.mode // ""')"
  raws=""
  if [ -n "$item_raw" ]; then raws="$item_raw"; else raws="$default_raw"; fi

  if [ -z "$raws" ]; then
    bad "volume '$vol' sets no mode — the kubelet projects 0644 and the client key becomes group-readable"
  else
    bad_mode=0
    while IFS= read -r raw; do
      [ -n "$raw" ] || continue
      m="$(mode_value "$raw")"
      if ! mode_is_owner_only "$m"; then
        bad "volume '$vol' mode '$raw' is not owner-only (renders $(printf '0%o' "${m:-0}")) — a group-readable key.pem is refused"
        bad_mode=1
      fi
    done <<EOF
$raws
EOF
    [ "$bad_mode" -eq 0 ] && ok "mode is owner-only ($raws)"
  fi
fi

# ---- 11. the mount path matches where --driver-opt reads the certs ----------
# CONFIG-DEAD-STATE guard: docs/ci-substrate.md's `--driver remote` step reads
# cacert/cert/key from fixed paths. A cert mounted anywhere else is delivered to
# a path nothing reads, and the build fails at mTLS with no hint why.
if [ -n "$mount_path" ]; then
  if [ ! -f "$DOC" ]; then
    bad "docs/ci-substrate.md is missing — cannot cross-check the --driver-opt cert paths"
  else
    doc_paths="$(grep -oE '(cacert|cert|key)=[^, ]+\.pem' "$DOC" | sed 's/^[^=]*=//' | sort -u)"
    if [ -z "$doc_paths" ]; then
      bad "docs/ci-substrate.md declares no --driver-opt cacert=/cert=/key= paths — the documented usage is gone"
    else
      base="${mount_path%/}"
      miss=""
      # every mounted cert must be read by the doc at <mount>/<key>
      for k in "${EXPECTED_KEYS[@]}"; do
        case "$doc_paths" in *"$base/$k"*) : ;; *) miss="$miss $base/$k" ;; esac
      done
      # every doc path must live under the mount, or it reads a cert we never mount
      stray=""
      while IFS= read -r p; do
        [ -n "$p" ] || continue
        case "$p" in "$base"/*) : ;; *) stray="$stray $p" ;; esac
      done <<EOF
$doc_paths
EOF
      if [ -z "$miss" ] && [ -z "$stray" ]; then
        ok "the mount path '$base' matches every --driver-opt cert path in ci-substrate.md"
      else
        [ -n "$miss" ] && bad "the --driver-opt step does not read these mounted certs:$miss"
        [ -n "$stray" ] && bad "the --driver-opt step reads certs outside the mount '$base':$stray"
      fi
    fi
  fi
fi

# ---- 12. never an environment variable --------------------------------------
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
