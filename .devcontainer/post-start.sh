#!/usr/bin/env bash
set -Eeuo pipefail

socket=/var/run/docker.sock
[[ -S "$socket" ]] || { echo "docker socket is not mounted: $socket" >&2; exit 1; }
gid="$(stat -c %g "$socket")"
getent group "$gid" >/dev/null || sudo groupadd --gid "$gid" docker-host
sudo usermod --append --groups "$gid" dev
sudo git config --system --replace-all safe.directory '*'
