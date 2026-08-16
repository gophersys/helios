#!/usr/bin/env bash
#
# _delta/components/comforts.sh — the interactive comforts the census kept:
# bat, htop, btop, httpie. Exactly these 4 — speedtest-cli, ncat and net-tools
# stay dropped by decision.
#
# Runs inside a Dockerfile RUN, as root. Distribution packages, no pin of their
# own. Idempotent.
#
set -Eeuo pipefail
IFS=$'\n\t'

export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y --no-install-recommends \
  bat \
  btop \
  htop \
  httpie
apt-get clean
rm -rf /var/lib/apt/lists/*

# Debian renames the binary; provide the name the ecosystem expects.
ln -sf /usr/bin/batcat /usr/local/bin/bat

# Proof.
bat --version
htop --version
btop --version
http --version
