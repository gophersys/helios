#!/usr/bin/env bash
set -Eeuo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
shim="$root/.devcontainer/devcontainer"
common_dir="$(git -C "$root" rev-parse --path-format=absolute --git-common-dir)"

grep -q 'versions=/workspace/.agents/versions.env' "$root/.devcontainer/post-create.sh" || {
  echo "post-create does not use the canonical harness version file" >&2
  exit 1
}

[[ "$(jq -r '.containerEnv.COREPACK_ENABLE_DOWNLOAD_PROMPT // empty' "$root/.devcontainer/devcontainer.json")" == 0 ]] || {
  echo "Corepack download prompt is not disabled" >&2
  exit 1
}

[[ -x "$shim" ]] || {
  echo "missing executable .devcontainer/devcontainer" >&2
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
export HOME="$tmp/home"
mkdir -p "$HOME/.codex"
touch "$HOME/.codex/auth.json"

(cd "$root" && "$shim" cloud)

expected="$tmp/expected"
cat >"$expected" <<EOF
up --workspace-folder $root --mount type=bind,source=$common_dir,target=$common_dir
exec --workspace-folder $root zsh -l
EOF
diff -u "$expected" "$DEVCONTAINER_CALLS"

: >"$DEVCONTAINER_CALLS"
(cd "$root" && "$shim" cloud -- nx check docs)
cat >"$expected" <<EOF
up --workspace-folder $root --mount type=bind,source=$common_dir,target=$common_dir
exec --workspace-folder $root zsh -lc exec "\$@" zsh nx check docs
EOF
diff -u "$expected" "$DEVCONTAINER_CALLS"

: >"$DEVCONTAINER_CALLS"
"$shim" read-configuration --workspace-folder "$root"
printf 'read-configuration --workspace-folder %s\n' "$root" >"$expected"
diff -u "$expected" "$DEVCONTAINER_CALLS"

echo "devcontainer entrypoint contract: PASS"
