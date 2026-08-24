#!/usr/bin/env bash
# Assert the admission policy in platform/core/policy/ still ENFORCES, and that
# the storage it guards is still guardable. Manifest-only: no cluster, no network.
#
# The failure this exists to prevent is the one that got Kyverno removed. Kyverno
# ran for months in `audit-only` with a single ClusterPolicy that excluded 8
# namespaces. Every document said "enforced at admission". Nothing was. The cost
# was 4 controller pods and a permanent OutOfSync line, and the benefit was zero.
# A policy that has quietly stopped denying looks exactly like one that works.
#
# Seven ways this component silently stops protecting anything, all asserted here:
#
#   1. THE BINDING STOPS DENYING. `validationActions: [Audit]` or `[Warn]` is a
#      one-word edit that reverts this whole component to enforcement theatre and
#      changes no other observable thing in the repo.
#   2. THE POLICY STOPS FAILING CLOSED. `failurePolicy: Ignore` means a broken
#      expression admits the delete instead of refusing it — FAIL-NOT-SKIP,
#      inverted, in the one place where the skip is unrecoverable.
#   3. A POLICY LOSES ITS BINDING, OR A BINDING NAMES A POLICY THAT IS GONE. An
#      unbound ValidatingAdmissionPolicy is inert: the apiserver stores it and
#      evaluates nothing. It reads, in `kubectl get`, exactly like a live one.
#   4. ARGO STOPS APPLYING IT, OR STARTS PRUNING IT. `prune: true` on this
#      Application means deleting a manifest FILE removes the live guard.
#   5. NOTHING IS LABELLED. The policies are gated on labels, so a correct,
#      enforcing, bound policy set that matches zero objects is a green check over
#      an empty guard. This is the exact class of false green the floor in
#      lint-manifests.sh exists for.
#   6. A PVC IN A PROTECTED NAMESPACE LOSES ITS OWN LABEL. The namespace label is
#      the primary guard; the per-PVC label is what keeps the chart contract in
#      charts/stateful-app true, and what survives the namespace label being
#      removed.
#   7. A StatefulSet RELIES ON THE DEFAULT RETENTION POLICY. Setting
#      `persistentVolumeClaimRetentionPolicy` to `Delete` puts an ownerReference
#      on the PVCs, and garbage collection then removes them BELOW admission —
#      the policy never receives a DELETE to refuse. The default is `Retain`, so
#      the safe value must be WRITTEN, not assumed, or the flip is invisible.
#
# Exit 0 = every property holds. Exit 1 = at least one does not. Exit 127 = yq is
# missing.
#
# Usage: verify-vap-policies.sh [root]   # root defaults to the repo root
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${1:-$(cd "$HERE/.." && pwd)}"
POLICY_DIR="$ROOT/platform/core/policy/manifests"
POLICY_PATH="platform/core/policy/manifests"   # the path an Argo Application must deploy
REGISTRY="$ROOT/platform/services/gitops/registry"

NS_STORAGE_LABEL="platform.gophersys/protected-storage"
NS_LABEL="platform.gophersys/protected"
PVC_LABEL="platform.gophersys/retain"

pass=0; fail=0
red() { printf '\033[0;31m%s\033[0m' "$1"; }
grn() { printf '\033[0;32m%s\033[0m' "$1"; }

ok()  { printf '  %s %s\n' "$(grn PASS)" "$1"; pass=$((pass + 1)); }
bad() { printf '  %s %s\n' "$(red FAIL)" "$1"; echo "::error::$1"; fail=$((fail + 1)); }

# joinsp: a newline list -> one space-separated line, with a trailing space, so a
# `case` membership test can anchor on " <item> ".
joinsp() { printf '%s' "$1" | awk 'NF' | tr '\n' ' '; }

if ! command -v yq >/dev/null 2>&1; then
  # A missing tool is a failure, never a skip: a skipped structural check is a
  # green line that asserted nothing.
  printf '  %s yq is required and is not installed\n' "$(red FAIL)"
  exit 127
fi

echo "verifying admission policy enforcement under $POLICY_PATH"

# ---- 0. the floor: the component exists and declares at least one policy ----
if [ ! -d "$POLICY_DIR" ]; then
  bad "$POLICY_PATH does not exist — the admission guard is gone, not merely broken"
  echo; echo "  pass=$pass fail=$fail"
  exit 1
fi

manifests=()
while IFS= read -r -d '' f; do
  manifests+=("$f")
done < <(find "$POLICY_DIR" -name '*.yaml' -print0 | sort -z)

if [ "${#manifests[@]}" -eq 0 ]; then
  bad "$POLICY_PATH holds no manifest — nothing is enforced"
  echo; echo "  pass=$pass fail=$fail"
  exit 1
fi

# A policy manifest that does not parse would yield an empty policy list, and the
# verdict below would then be "no ValidatingAdmissionPolicy is declared" — the
# right exit code for the wrong reason, which sends the reader to the wrong fix.
for m in "${manifests[@]}"; do
  if ! err="$(yq eval-all -N 'true' "$m" 2>&1 >/dev/null)" || [ -n "$err" ]; then
    bad "yq could not read ${m#"$ROOT"/}: $(printf '%s' "$err" | head -1)"
    echo; echo "  pass=$pass fail=$fail"
    exit 1
  fi
done

policies="$(yq eval-all -N 'select(.kind == "ValidatingAdmissionPolicy") | .metadata.name' "${manifests[@]}" 2>/dev/null | awk 'NF' | sort -u)"
bindings="$(yq eval-all -N 'select(.kind == "ValidatingAdmissionPolicyBinding") | .metadata.name' "${manifests[@]}" 2>/dev/null | awk 'NF' | sort -u)"

if [ -z "$policies" ]; then
  bad "no ValidatingAdmissionPolicy is declared under $POLICY_PATH"
  echo; echo "  pass=$pass fail=$fail"
  exit 1
fi
ok "$(printf '%s\n' "$policies" | wc -l | tr -d ' ') ValidatingAdmissionPolic(y|ies) declared: $(joinsp "$policies")"

# ---- 1. every policy fails CLOSED -------------------------------------------
while IFS= read -r p; do
  [ -n "$p" ] || continue
  fp="$(yq eval-all -N "select(.kind == \"ValidatingAdmissionPolicy\") | select(.metadata.name == \"$p\") | .spec.failurePolicy // \"Fail\"" "${manifests[@]}" 2>/dev/null | head -1)"
  if [ "$fp" = "Fail" ]; then
    ok "policy '$p' fails closed (failurePolicy: Fail)"
  else
    bad "policy '$p' has failurePolicy: ${fp:-<unset>} — a broken expression would ADMIT the delete"
  fi
done <<EOF
$policies
EOF

# ---- 2. every policy is bound, and every binding DENIES ---------------------
while IFS= read -r p; do
  [ -n "$p" ] || continue
  bound="$(yq eval-all -N "select(.kind == \"ValidatingAdmissionPolicyBinding\") | select(.spec.policyName == \"$p\") | .metadata.name" "${manifests[@]}" 2>/dev/null | awk 'NF')"
  if [ -z "$bound" ]; then
    bad "policy '$p' has no ValidatingAdmissionPolicyBinding — the apiserver stores it and evaluates nothing"
    continue
  fi
  ok "policy '$p' is bound by: $(joinsp "$bound")"

  while IFS= read -r b; do
    [ -n "$b" ] || continue
    actions="$(yq eval-all -N "select(.kind == \"ValidatingAdmissionPolicyBinding\") | select(.metadata.name == \"$b\") | .spec.validationActions[]" "${manifests[@]}" 2>/dev/null | awk 'NF' | sort -u | tr '\n' ' ' | sed 's/ $//')"
    if [ "$actions" = "Deny" ]; then
      ok "binding '$b' ENFORCES (validationActions: [Deny])"
    else
      bad "binding '$b' has validationActions: [${actions:-<unset>}] — only [Deny] enforces; Audit and Warn are the Kyverno failure repeated"
    fi
  done <<EOB
$bound
EOB
done <<EOF
$policies
EOF

# ---- 3. no binding points at a policy that does not exist -------------------
while IFS= read -r b; do
  [ -n "$b" ] || continue
  target="$(yq eval-all -N "select(.kind == \"ValidatingAdmissionPolicyBinding\") | select(.metadata.name == \"$b\") | .spec.policyName" "${manifests[@]}" 2>/dev/null | head -1)"
  case " $(joinsp "$policies")" in
    *" $target "*) : ;;
    *) bad "binding '$b' names policyName '$target', which no manifest here declares — it binds nothing" ;;
  esac
done <<EOF
$bindings
EOF

# ---- 4. Argo applies it, and cannot prune it --------------------------------
app_file=""
if [ -d "$REGISTRY" ]; then
  for f in "$REGISTRY"/*.yaml; do
    [ -e "$f" ] || continue
    if [ "$(yq '.spec.source.path // ""' "$f" 2>/dev/null)" = "$POLICY_PATH" ]; then
      app_file="$f"; break
    fi
  done
fi
if [ -z "$app_file" ]; then
  bad "no Argo Application in the registry deploys $POLICY_PATH — the policies are in git and on no cluster"
else
  ok "Argo Application deploys it (${app_file#"$ROOT"/})"
  prune="$(yq '.spec.syncPolicy.automated.prune // false' "$app_file" 2>/dev/null)"
  if [ "$prune" = "false" ]; then
    ok "the policy Application does not prune — removing a manifest file cannot remove the live guard"
  else
    bad "the policy Application sets prune: $prune — deleting a manifest file would delete the live enforcement"
  fi
fi

# ---- the manifest scan ------------------------------------------------------
# Scan the two trees that hold real cluster manifests. charts/ is excluded on
# purpose: it holds Go templates, which are not YAML.
scan_roots=()
for r in apps platform; do
  [ -d "$ROOT/$r" ] && scan_roots+=("$ROOT/$r")
done

# The policy manifests themselves are excluded: they are the subject of checks
# 0-3, and counting them here would make the floor below unreachable — the
# component's own files would always keep the scan non-empty.
#
# A HELM TEMPLATE IS NOT YAML — but ONLY the template is exempt. The anchor is
# the same as lint-manifests.sh (a Chart.yaml at or above the file defines a
# chart), the scope is deliberately NARROWER: only files under that chart's
# templates/ are dropped, because only they carry `{{ }}` where a value belongs
# (first hit: platform/services/observability/chart/templates/, 2026-08-24).
# The chart's OWN Chart.yaml and values*.yaml files STAY in the scan: they are
# real YAML, this parse pass (4b) is the only CI gate that reads them — the
# kubeconform gate skips the whole chart directory — and a blanket Chart.yaml
# exclusion here was proven to let a syntax error in values-homelab.yaml ride
# green to Argo (adversarial verify on #202). They carry no `kind:`, so checks
# 5-7 select nothing from them; parse coverage is the point.
# The skipped count is PRINTED below so the exemption cannot quietly grow to
# swallow a real manifest tree.
scan_files=()
chart_skipped=0
if [ "${#scan_roots[@]}" -gt 0 ]; then
  while IFS= read -r -d '' f; do
    case "$f" in "$POLICY_DIR"/*) continue ;; esac
    d="$(dirname "$f")"
    in_chart_templates=0
    while [ "$d" != "." ] && [ "$d" != "/" ]; do
      if [ -f "$d/Chart.yaml" ]; then
        case "$f" in "$d"/templates/*) in_chart_templates=1 ;; esac
        break
      fi
      d="$(dirname "$d")"
    done
    if [ "$in_chart_templates" -eq 1 ]; then
      chart_skipped=$((chart_skipped + 1))
      continue
    fi
    scan_files+=("$f")
  done < <(find "${scan_roots[@]}" -name '*.yaml' \
    -not -path '*/config-enforce/*' -not -path '*/envs/*' -print0 | sort -z)
fi
if [ "$chart_skipped" -gt 0 ]; then
  printf '  note %d Helm template file(s) excluded from the scan (templates/ under a Chart.yaml is Go template source, not YAML)\n' "$chart_skipped"
fi

if [ "${#scan_files[@]}" -eq 0 ]; then
  # The floor again: a scan over zero files reports every property below as
  # satisfied. That is the false green, not a pass.
  bad "no manifest found under ${scan_roots[*]:-<no root>} — checks 5-7 measured nothing"
  echo; echo "  pass=$pass fail=$fail"
  exit 1
fi

# ---- 4b. every scanned manifest PARSES --------------------------------------
# An unreadable file must FAIL, never read as "this file declares no PVC" — and
# the file most likely to be malformed is the one just edited. This runs as its
# own pass, outside any command substitution, because a `bad` called inside
# `x="$(...)"` runs in a subshell: its line is captured into the variable instead
# of printed, and its increment of `fail` is discarded when the subshell exits.
# That defect made this very check pass over a broken fixture until the spec
# suite caught it.
parse_ok=()
for f in "${scan_files[@]}"; do
  if err="$(yq eval-all -N 'true' "$f" 2>&1 >/dev/null)" && [ -z "$err" ]; then
    parse_ok+=("$f")
  else
    bad "yq could not read ${f#"$ROOT"/}: $(printf '%s' "$err" | head -1)"
  fi
done
scan_files=("${parse_ok[@]+"${parse_ok[@]}"}")

# ---- 5. the floor: something is actually labelled ---------------------------
protected_storage_ns=""
protected_ns=""
for f in "${scan_files[@]+"${scan_files[@]}"}"; do
  n="$(yq eval-all -N "select(.kind == \"Namespace\") | select(.metadata.labels.\"$NS_STORAGE_LABEL\" == \"true\") | .metadata.name" "$f" | awk 'NF')"
  [ -n "$n" ] && protected_storage_ns="$protected_storage_ns$n"$'\n'
  n="$(yq eval-all -N "select(.kind == \"Namespace\") | select(.metadata.labels.\"$NS_LABEL\" == \"true\") | .metadata.name" "$f" | awk 'NF')"
  [ -n "$n" ] && protected_ns="$protected_ns$n"$'\n'
done
protected_storage_ns="$(printf '%s' "$protected_storage_ns" | awk 'NF' | sort -u)"
protected_ns="$(printf '%s' "$protected_ns" | awk 'NF' | sort -u)"

if [ -n "$protected_storage_ns" ]; then
  ok "namespaces carrying $NS_STORAGE_LABEL=true: $(joinsp "$protected_storage_ns")"
else
  bad "no Namespace manifest carries $NS_STORAGE_LABEL=true — storage-delete-guard matches nothing"
fi
if [ -n "$protected_ns" ]; then
  ok "namespaces carrying $NS_LABEL=true: $(joinsp "$protected_ns")"
else
  bad "no Namespace manifest carries $NS_LABEL=true — namespace-delete-guard matches nothing"
fi

# ---- 6. every PVC in a protected namespace carries its own retain label -----
if [ -n "$protected_storage_ns" ]; then
  for f in "${scan_files[@]+"${scan_files[@]}"}"; do
    rows="$(yq eval-all -N "select(.kind == \"PersistentVolumeClaim\") | (.metadata.namespace // \"\") + \"|\" + .metadata.name + \"|\" + (.metadata.labels.\"$PVC_LABEL\" // \"\")" "$f" | awk 'NF')"
    while IFS= read -r line; do
      [ -n "$line" ] || continue
      pvc_ns="${line%%|*}"; rest="${line#*|}"
      pvc_name="${rest%%|*}"; retain="${rest##*|}"
      case $'\n'"$protected_storage_ns"$'\n' in
        *$'\n'"$pvc_ns"$'\n'*) : ;;
        *) continue ;;
      esac
      if [ "$retain" = "true" ]; then
        ok "PVC $pvc_ns/$pvc_name carries $PVC_LABEL=true"
      else
        bad "PVC $pvc_ns/$pvc_name is in protected namespace '$pvc_ns' but carries no $PVC_LABEL=true (${f#"$ROOT"/}) — it loses its guard the moment the namespace label goes"
      fi
    done <<EOP
$rows
EOP
  done
fi

# ---- 7. every StatefulSet with volumeClaimTemplates PINS its retention ------
for f in "${scan_files[@]+"${scan_files[@]}"}"; do
  rows="$(yq eval-all -N '
    select(.kind == "StatefulSet")
    | select((.spec.volumeClaimTemplates // []) | length > 0)
    | .metadata.name
      + "|" + (.spec.persistentVolumeClaimRetentionPolicy.whenDeleted // "")
      + "|" + (.spec.persistentVolumeClaimRetentionPolicy.whenScaled // "")' "$f" | awk 'NF')"
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    sts_name="${line%%|*}"; rest="${line#*|}"
    when_deleted="${rest%%|*}"; when_scaled="${rest##*|}"
    if [ "$when_deleted" = "Retain" ] && [ "$when_scaled" = "Retain" ]; then
      ok "StatefulSet '$sts_name' pins persistentVolumeClaimRetentionPolicy Retain/Retain"
    else
      bad "StatefulSet '$sts_name' (${f#"$ROOT"/}) has volumeClaimTemplates but persistentVolumeClaimRetentionPolicy is ${when_deleted:-<unset>}/${when_scaled:-<unset>} — 'Delete' garbage-collects the PVCs below admission, where no policy can refuse it"
    fi
  done <<EOS
$rows
EOS
done

echo
echo "  pass=$pass fail=$fail"
[ "$fail" -eq 0 ] || exit 1
