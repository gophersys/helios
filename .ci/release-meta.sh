#!/usr/bin/env bash
#
# .ci/release-meta.sh — emit the release metadata the release.yml jobs consume as step outputs
# (KEY=VALUE lines the caller appends to $GITHUB_OUTPUT). ONE home for the version/sha/pin derivation
# so every per-service job (and the promote job) resolves them identically.
#
#   version              the image tag: on a `v<semver>` tag push it is the tag; on a workflow_dispatch
#                        (a branch ref) it is `<short-sha>-dispatch` (a unique, valid image ref).
#   short_sha            the 7-char commit sha (the sha-<short> edge tag).
#   claude_code_version  the pinned Claude Code version from harnesses/versions.env (ADR-0021 — the
#                        agent-runtime build's REQUIRED CLAUDE_CODE_VERSION build-arg; the ONE home).
#
set -Eeuo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# The commit sha: prefer the actions-provided GITHUB_SHA, fall back to git.
sha="${GITHUB_SHA:-$(git -C "$REPO_ROOT" rev-parse HEAD)}"
short_sha="${sha:0:7}"

# The version: a tag ref (refs/tags/v1.2.3) → the tag; anything else (a dispatch on a branch) →
# <short-sha>-dispatch so the pushed image is still uniquely, validly tagged.
ref="${GITHUB_REF:-}"
case "$ref" in
  refs/tags/*) version="${ref#refs/tags/}" ;;
  *)           version="${short_sha}-dispatch" ;;
esac

# The pinned Claude Code version (the agent-runtime build-arg). Sourced from the ONE manifest.
claude_code_version=""
if [ -f "$REPO_ROOT/harnesses/versions.env" ]; then
  # shellcheck disable=SC1091
  . "$REPO_ROOT/harnesses/versions.env"
  claude_code_version="${CLAUDE_CODE_VERSION:-}"
fi

printf 'version=%s\n' "$version"
printf 'short_sha=%s\n' "$short_sha"
printf 'claude_code_version=%s\n' "$claude_code_version"
