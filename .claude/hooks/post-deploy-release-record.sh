#!/usr/bin/env bash
# PostToolUse hook: after `nx update platform -c <env>` completes, inject a
# system reminder telling the AI that the release record MUST be created
# before moving on.
#
# Wired in .claude/settings.json under hooks.PostToolUse.Bash.
#
# Input (stdin, JSON):
#   tool_input.command         — the shell command that was run
#   tool_response.stdout       — command stdout
#   tool_response.interrupted  — whether the command was interrupted
#
# Output (stdout, JSON): hookSpecificOutput.additionalContext is surfaced to
# the AI as a system-reminder on the next turn.

set -euo pipefail

payload=$(cat)

command=$(printf '%s' "$payload" | jq -r '.tool_input.command // ""' 2>/dev/null || echo "")

# Match only successful "nx update platform -c <env>" deploys.
if ! printf '%s' "$command" | grep -qE 'nx update platform -c (staging|production)'; then
  exit 0
fi

# Extract environment name.
env=$(printf '%s' "$command" | grep -oE 'nx update platform -c (staging|production)' | awk '{print $NF}' | head -1)
if [ -z "$env" ]; then
  exit 0
fi

# Only remind on apparent success — if stdout does NOT mention the usual
# success markers, skip (let the AI focus on the failure first).
stdout=$(printf '%s' "$payload" | jq -r '.tool_response.stdout // ""' 2>/dev/null || echo "")
if ! printf '%s' "$stdout" | grep -qE 'Platform updated: (staging|production)|Successfully ran target update'; then
  exit 0
fi

reminder="DEPLOY→RECORD PAIRING (concord-release Phase 9/10): the \`nx update platform -c $env\` just succeeded. The release is NOT complete until a matching record exists in the $env database. Immediately: (1) find the http-api pod in the $env namespace, (2) generate a JWT inside the pod using JWT_SECRET_KEY, (3) POST /v2/releases with the full metadata from Phase 5 (version, commitSha, branch=main, status=RELEASED, previousVersion, summary, changelog, linesAdded, linesRemoved, corekinectVersion, migrationHash, etc.), (4) verify with GET /v2/releases?limit=3. Do this BEFORE the other environment's deploy or any other work. Skipping this is the #1 failure mode — see .claude/skills/concord-release/SKILL.md 'Definition of Done'."

jq -n --arg ctx "$reminder" '{
  hookSpecificOutput: {
    hookEventName: "PostToolUse",
    additionalContext: $ctx
  }
}'
