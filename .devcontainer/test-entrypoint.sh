#!/usr/bin/env bash
set -Eeuo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
shim="$root/scripts/devcontainer"

[[ -x "$shim" ]] || {
  echo "missing executable scripts/devcontainer" >&2
  exit 1
}

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

cat >"$tmp/devcontainer" <<'UPSTREAM'
#!/usr/bin/env bash
printf '%s\n' "$*" >>"$DEVCONTAINER_CALLS"
UPSTREAM
chmod +x "$tmp/devcontainer"

export DEVCONTAINER_UPSTREAM="$tmp/devcontainer"
export DEVCONTAINER_CALLS="$tmp/calls"

(cd "$root" && "$shim" cloud)

expected="$tmp/expected"
cat >"$expected" <<EOF
up --workspace-folder $root
exec --workspace-folder $root zsh -l
EOF
diff -u "$expected" "$DEVCONTAINER_CALLS"

: >"$DEVCONTAINER_CALLS"
"$shim" read-configuration --workspace-folder "$root"
printf 'read-configuration --workspace-folder %s\n' "$root" >"$expected"
diff -u "$expected" "$DEVCONTAINER_CALLS"

echo "devcontainer entrypoint contract: PASS"
