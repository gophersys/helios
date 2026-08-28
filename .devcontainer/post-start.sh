#!/usr/bin/env bash
set -Eeuo pipefail

socket=/var/run/docker.sock
[[ -S "$socket" ]] || { echo "docker socket is not mounted: $socket" >&2; exit 1; }
gid="$(stat -c %g "$socket")"
getent group "$gid" >/dev/null || sudo groupadd --gid "$gid" docker-host
sudo usermod --append --groups "$gid" dev
sudo git -C /tmp config --system --replace-all safe.directory '*'

codex_seed=/run/eden/host-codex-auth.json
codex_home=/home/dev/.codex
if [[ -f "$codex_seed" && ! -f "$codex_home/auth.json" ]]; then
  install -d -m 700 "$codex_home"
  install -m 600 "$codex_seed" "$codex_home/auth.json"
fi
