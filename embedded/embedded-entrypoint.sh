#!/usr/bin/env bash
#
# embedded-entrypoint.sh — PID 1 of the embedded image.
#
# It does ONE thing: it execs the argv docker hands it — the image CMD when the
# caller named none — as `dev`.
#
# WHY A SCRIPT AT ALL, AND NOT `USER dev`. The image ships `USER root`, so
# without this file `docker run embedded id` would answer `root` while every
# other image of this repository answers `dev`. A Dockerfile names 1 USER, and
# this file is what put the second identity back while `embedded` still carried
# a pod half that bound sshd.
#
# THE POD HALF IS DELETED — Mateo, 2026-08-19, "yes strip and delete and clean
# up anything devbox we don't need any of it anymore"; the record is "The devbox
# mode is deleted" in .claude/rules/00-identity.md. So nothing in this image
# needs root at runtime any more, and collapsing `USER root` + this file into a
# plain `USER dev` is REAL open work rather than a thing already done: it also
# moves .ci/smoke.sh's embedded-only `--user dev` arm and the identity sentences
# 2 other files state, which is a second decision and not this one. Recorded
# here so a reader does not read `USER root` as load-bearing.
#
set -Eeuo pipefail
IFS=$'\n\t'

function log() { printf '[embedded-entrypoint] %s\n' "$*" >&2; }

# An empty argv would `exec` NOTHING — a no-op in bash, under which control
# falls to the next statement — and this script would then simply end, handing
# the caller an empty container that exited 0. The image declares CMD, so
# reaching this needs a caller who replaced it with nothing.
#
# EXIT 2 is the documented answer: the code every driver script of this
# repository uses for a caller error, spelled beside this step in README.md and
# in .claude/rules/00-identity.md. The log line is the whole record — the
# /run/devbox-degraded marker that used to accompany it went with the pod, whose
# probe was its only reader. A file written into a container that is exiting is
# state nothing can read.
if [[ $# -eq 0 ]]; then
  log "ERROR: no command to exec — the image CMD is /usr/bin/zsh and this caller replaced it with an empty argv"
  exit 2
fi

# runuser is correct at euid 0 and WRONG below it — under `docker run --user
# dev` (which .ci/smoke.sh does) the binary is there and unprivileged, and it
# would refuse with "may not be used by non-root users", turning a working
# invocation into an error. The euid test is what makes both callers work.
#
# Plain `runuser -u dev --`, deliberately NOT `--preserve-environment`.
# Measured on ubuntu:24.04: it PRESERVES PATH and every exported variable, and
# sets HOME=/home/dev, USER=dev and LOGNAME=dev — which is the environment
# `USER dev` in a Dockerfile produces. --preserve-environment would keep
# HOME=/root, and the toolchain's caches and oh-my-zsh live in /home/dev.
if [[ "$(id -u)" -eq 0 ]]; then
  exec runuser -u dev -- "$@"
fi
exec "$@"
