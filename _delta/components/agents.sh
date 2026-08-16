#!/usr/bin/env bash
#
# _delta/components/agents.sh — the harness bake: claude + omp + codex at the
# pins of versions.env (which mirror eden harnesses/versions.env, ADR-0021).
#
# Runs inside a Dockerfile RUN, as the DEV USER: the claude installer writes to
# ${HOME}/.local/bin, and the npm globals land in the nvm-homed node prefix —
# both belong to dev, and both are on the image-wide ENV PATH, so every user
# and every shell resolves them. The /usr/local/bin symlink for claude needs
# root, and dev is sudo-nopasswd, so the script takes it with sudo.
#
# This bake is what retires the eden postCreate installs in the consumer
# migration: what the container needs, the image carries, and an agent pod
# does ZERO network installs at start.
#
# Idempotent: the installer and npm both overwrite.
#
set -Eeuo pipefail
IFS=$'\n\t'

: "${CLAUDE_CODE_VERSION:?CLAUDE_CODE_VERSION is not in versions.env}"
: "${OMP_VERSION:?OMP_VERSION is not in versions.env}"
: "${CODEX_VERSION:?CODEX_VERSION is not in versions.env}"

# claude — the official installer at the exact pin, verified in the same
# breath. pipefail is on, so a failed curl cannot hide behind the bash that
# follows it: a 404 would otherwise send an EMPTY script into bash, which
# exits 0 and leaves the image with no claude at all.
curl -fsSL https://claude.ai/install.sh | bash -s "${CLAUDE_CODE_VERSION}"
installed="$("${HOME}/.local/bin/claude" --version 2>/dev/null || true)"
case "$installed" in
  *"${CLAUDE_CODE_VERSION}"*) : ;;
  *) echo "FATAL: claude reports '${installed}', expected ${CLAUDE_CODE_VERSION}"; exit 1 ;;
esac
sudo ln -sfn "${HOME}/.local/bin/claude" /usr/local/bin/claude

# omp + codex — npm globals at the exact pins. omp's CLI shebang is
# `#!/usr/bin/env bun`; bun is baked into the image so it resolves at runtime.
npm install -g "@oh-my-pi/pi-coding-agent@${OMP_VERSION}"
npm install -g "@openai/codex@${CODEX_VERSION}"

# Proof.
claude --version
omp --version
codex --version
