#!/usr/bin/env bash
# entrypoint.sh — run ONE headless Claude Code session in the container.
#
# Auth contract (07 §2; verified against code.claude.com/docs/en/authentication):
#   The session authenticates ONLY from CLAUDE_CODE_OAUTH_TOKEN in the environment.
#   The token is minted once, interactively, on Mateo's laptop with `claude setup-token`
#   (one-year, inference-only, cannot establish Remote Control) and injected at runtime
#   via the compose env_file. We never print it, never write it to the workspace, never
#   bake it into an image layer.
#
# Flags mirror poc/codingharness (its README §"Flags used to drive Claude Code"):
#   -p / --print                 headless: print and exit, skip the trust dialog
#   --output-format stream-json  one JSON event per line — the transcript stream
#   --verbose                    MANDATORY with stream-json in print mode (CLI errors without it)
#   --allowedTools ...           the minimum the task needs; everything else is denied
#   --permission-mode acceptEdits  unattended edits WITHOUT dropping to bypassPermissions
#
# NOTE: we deliberately do NOT pass --bare. Bare mode does not read
# CLAUDE_CODE_OAUTH_TOKEN (it accepts only ANTHROPIC_API_KEY / apiKeyHelper), so --bare
# is incompatible with the subscription-token flow this spike exists to prove.

set -euo pipefail

# --- preflight: token must be present, and we must never leak it ----------------------
if [[ -z "${CLAUDE_CODE_OAUTH_TOKEN:-}" ]]; then
  echo "FATAL: CLAUDE_CODE_OAUTH_TOKEN is not set." >&2
  echo "       Mint it once on a workstation with:  claude setup-token" >&2
  echo "       then put it in .env (see README) so compose injects it here." >&2
  exit 78  # EX_CONFIG: configuration error, distinct from a runtime auth failure
fi

# Defense in depth: scrub any credential the harness must NOT consume. Per the docs'
# precedence list, ANTHROPIC_AUTH_TOKEN / ANTHROPIC_API_KEY / apiKeyHelper all OUTRANK
# CLAUDE_CODE_OAUTH_TOKEN — a stray API key in the env would silently take over. Unset
# them so this run is provably exercising the subscription-token path and nothing else.
unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN ANTHROPIC_BEARER_TOKEN || true

# Task + tool allowlist are overridable for experimentation but default to the same
# trivial, self-contained task the codingharness spike used.
TASK="${TASK:-Create a file named hello.txt whose only contents are the word: eden}"

# Space-separated allowlist; narrow by default. Read+Write to do the task, Bash scoped
# to `ls`/`cat` only so verification commands work and nothing else does.
ALLOWED_TOOLS_DEFAULT=(Write Read "Bash(ls *)" "Bash(cat *)")
if [[ -n "${ALLOWED_TOOLS:-}" ]]; then
  # caller-provided, space-separated
  read -r -a ALLOWED_TOOLS_ARR <<< "${ALLOWED_TOOLS}"
else
  ALLOWED_TOOLS_ARR=("${ALLOWED_TOOLS_DEFAULT[@]}")
fi

echo "=== agentsession-spike :: headless Claude Code ===" >&2
echo "cwd:        $(pwd)" >&2
echo "user:       $(id -un) (uid $(id -u))" >&2
echo "cli:        $(claude --version 2>/dev/null || echo 'unknown')" >&2
echo "auth:       CLAUDE_CODE_OAUTH_TOKEN present (value redacted)" >&2
echo "task:       ${TASK}" >&2
echo "allowed:    ${ALLOWED_TOOLS_ARR[*]}" >&2
echo "===================================================" >&2

# The session. stdout is the stream-json transcript (one JSON object per line) — let it
# flow to the caller verbatim, exactly as the Go codingharness captures it.
exec claude \
  -p "${TASK}" \
  --output-format stream-json \
  --verbose \
  --allowedTools "${ALLOWED_TOOLS_ARR[@]}" \
  --permission-mode acceptEdits
