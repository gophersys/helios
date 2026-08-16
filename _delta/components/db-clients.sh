#!/usr/bin/env bash
#
# _delta/components/db-clients.sh — the data clients: psql, redis-cli, sqlite3.
#
# Runs inside a Dockerfile RUN, as root. The apt packages are distribution
# packages and carry no pin of their own, the same way base/Dockerfile installs
# them. Idempotent: apt-get install of an installed package is a no-op.
#
set -Eeuo pipefail
IFS=$'\n\t'

export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y --no-install-recommends \
  postgresql-client \
  redis-tools \
  sqlite3
apt-get clean
rm -rf /var/lib/apt/lists/*

# Proof — a component that installed nothing must fail here, loudly.
psql --version
redis-cli --version
sqlite3 --version
