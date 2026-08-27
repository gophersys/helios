#!/usr/bin/env bash
#
# _ctl/standard.sh — the PORTABLE core of the ctl.sh standard.
#
# The written standard is docs/ctl-standard.md. This file is the part of it that
# is CODE: C1 (the shell options), C4 (the four loggers), C5 (the tool gate) and
# I7 (root discovery by marker). Everything else in that document is a rule about
# how a script is written, which no file can hand out.
#
# IT SOURCES WITH NOTHING CONFIGURED, AND THAT IS THE WHOLE REASON IT IS A
# SECOND FILE. _ctl/lib.sh:55 asserts PROJECT_ROOT before it does any work —
# correct for a dispatcher of this repository, and fatal for a consumer that
# wants only the loggers: `bash -c 'unset PROJECT_ROOT; source _ctl/lib.sh'`
# exits 1. eden, libs and infrastructure each carry their own spelling of these
# same five symbols because there was nothing they could take. C9 is not
# weakened by this file: lib.sh keeps its assertion, because PROJECT_ROOT really
# is a required input THERE.
#
# lib.sh sources this file, so a script that already takes the library takes the
# standard with it and adds no source line of its own.
#
# Usage, from a consumer that has configured nothing:
#   source <path>/_ctl/standard.sh
#
# shellcheck shell=bash

# -------- C1: the shell options, in every script --------
set -Eeuo pipefail
IFS=$'\n\t'

# -------- C4: the four loggers, defined once --------
# printf and never echo: echo's handling of a leading `-` and of a backslash is
# implementation-defined, and a message is data.
#
# The STREAM is part of the contract. warn and error go to stderr, so a caller
# reading a verb's stdout through a command substitution still sees them; info
# and success go to stdout, so a run's narrative is one ordered stream.
#
# THESE FOUR BODIES ARE COPIED FROM NOWHERE — they are what the fleet already
# writes. Measured 2026-08-26, all four are byte-identical in eden `.ci/ctl.sh:17-20`
# and libs `.ci/ctl.sh:46-49`, and the first three in `_ctl/lib.sh:171-174`. The
# only thing missing was a file any of them could take them FROM, which is why
# log_success existed in 2 of the 3 repositories and in none of this one.
function log_info()    { printf '\033[0;36m[info]\033[0m  %s\n' "$*"; }
function log_warn()    { printf '\033[0;33m[warn]\033[0m  %s\n' "$*" >&2; }
function log_error()   { printf '\033[0;31m[error]\033[0m %s\n' "$*" >&2; }
function log_success() { printf '\033[0;32m[ok]\033[0m    %s\n' "$*"; }

# -------- C5: FAIL-NOT-SKIP, the tool gate --------
# require_cmd <tool>... — every tool must be an executable FILE on PATH.
# Exits 127 naming EVERY tool that is not, in 1 message: a gate that stops at
# the first absent tool sends the operator round the loop once per tool.
#
# `type -t` and NOT `command -v`, measured by gophersys/libs .ci/ctl.sh:64-83.
# `command -v` reports a shell FUNCTION of the tool's name as a present tool,
# and the caller then reads a shell BODY's exit status where it meant to read
# the TOOL's — only the body's last command survives. With a `cictl()` injected
# by `export -f`, that tier printed git's own `fatal:` and still exited 0 with
# "all 1 affected project(s) green". `type -t` answers what the next call would
# really RUN, so `file` is the only kind that satisfies this gate: an alias, a
# builtin, a keyword and a function are each refused.
function require_cmd() {
  local missing=()
  local cmd kind
  for cmd in "$@"; do
    # `type -t` on an unknown name prints nothing and returns 1, with an empty
    # stderr — so the status is read here rather than swallowed, and no
    # redirection is needed to keep the run quiet.
    kind="$(type -t "$cmd")" || kind=""
    [[ "$kind" == "file" ]] || missing+=("$cmd")
  done
  if [[ ${#missing[@]} -gt 0 ]]; then
    log_error "missing required tool(s): ${missing[*]}"
    exit 127
  fi
}

# -------- I7: root discovery by marker, never a counted ../../.. --------
# find_repository_root [start-directory] — print the NEAREST ancestor of the
# start directory (default $PWD) that holds a `.git` entry, and return 0.
# With no marker up to `/`: nothing on stdout, a message on stderr, return 1.
#
# `-e` and not `-d`: `.git` is a DIRECTORY in a normal clone and a FILE in a
# submodule and in a worktree, and this repository is checked out both ways —
# it is a submodule of eden, and the development process gives every feature a
# worktree of its own.
#
# THE THREE PROPERTIES ARE ONE CONTRACT, and the caller shape is why.
# iotea's `libs/bash/source.sh:17-18` is `ROOT=$(find_workspace_root)` followed
# by `if [ $? -ne 0 ]`. A finder that returned 0 having found nothing makes that
# guard dead; one that printed a path it never verified makes every path built
# from it wrong in silence; one that refused without a message leaves the
# operator a number and no next step.
#
# The start directory is RESOLVED first, so the walk is over physical
# components: with a symlinked ancestor, `dirname` on the unresolved path climbs
# a tree that does not exist. `/` itself is deliberately not probed — the loop
# stops there — because a checkout at the filesystem root is not a shape any
# repository of this organization takes, and an unreachable branch in a file
# every consumer sources is worse than a stated boundary.
function find_repository_root() {
  local start="${1:-$PWD}" directory
  directory="$(cd -P "$start" && pwd -P)" || {
    log_error "find_repository_root: cannot enter the start directory: ${start}"
    return 1
  }
  while [[ "$directory" != "/" ]]; do
    if [[ -e "${directory}/.git" ]]; then
      printf '%s\n' "$directory"
      return 0
    fi
    directory="$(dirname "$directory")"
  done
  log_error "find_repository_root: no .git marker above ${start} — not inside a checkout"
  return 1
}
