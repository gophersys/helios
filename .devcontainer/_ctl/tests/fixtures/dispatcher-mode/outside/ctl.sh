#!/usr/bin/env bash
#
# A dispatcher-SHAPED file that is not an image, and the staged root keeps it
# 100644 in every run of _ctl/tests/dispatcher-mode.test.sh.
#
# `images.yaml` of this fixture declares `first` and `second` and nothing else,
# so `outside` is a directory the executable-bit rule must never judge. The
# repository already holds one of these — _ctl/tests/fixtures/no-platform-list/
# — and .claude/rules/00-identity.md states the rule it demonstrates: the check
# derives its list from the manifest like every other loop in cmd_validate, so a
# directory that is not an image of the manifest is not held to it.
#
# Without this file the rule could be rewritten as a `*/ctl.sh` glob and every
# check of that test would stay green, while the gate started failing on every
# dispatcher-shaped fixture in the tree.
#
set -Eeuo pipefail
IFS=$'\n\t'

printf 'fixture dispatcher: outside %s\n' "${1:-<no verb>}"
