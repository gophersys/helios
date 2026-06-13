# agentsession-spike — headless Claude Code in a container (de-risks REQ-0021).
#
# Design constraints (07 security-model §3 "Agent sandboxing"):
#   - non-root user                         (no privileged process inside the pod)
#   - workspace is the only writable mount   (compose owns the bind; nothing else)
#   - NO listening sockets / EXPOSE          (dial-out-only; the agent connects OUT
#                                             to the model provider, opens nothing in)
#   - credential arrives only at RUNTIME via env (07 §2 "never in agent context" — and
#                                             here, never baked into an image layer)
#
# Pin: @anthropic-ai/claude-code is pinned to an exact version. Bump deliberately; the
# F4 adapter (ADR-0008) owes a pinned-and-tested CLI version + a conformance suite over
# the event stream (codingharness "schema drift / version pinning" open question).

FROM node:22-slim

# Pinned Claude Code CLI version. `stable` dist-tag at authoring time (2026-06-12).
# The host CLI used to verify the token flow was 2.1.176 (npm `latest`); we pin the
# more conservative `stable` for the container baseline and record the delta in README.
ARG CLAUDE_CODE_VERSION=2.1.153

# git + ca-certificates: the CLI shells out to git in real workspaces, and TLS to the
# model provider needs the CA bundle. No build tools, no extra surface.
RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Install the CLI globally at the pinned version. This is the ONLY network fetch baked
# into the image; the layer contains the CLI, never a credential.
RUN npm install -g "@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}" \
 && npm cache clean --force

# Non-root identity. node:22-slim ships a `node` user (uid 1000); reuse it rather than
# minting another. The workspace is owned by this user so the agent can write there and
# nowhere else it has no business writing.
ENV HOME=/home/node
RUN mkdir -p /workspace /home/node/.claude \
 && chown -R node:node /workspace /home/node

WORKDIR /workspace
USER node

# entrypoint expects CLAUDE_CODE_OAUTH_TOKEN in the env at `docker run` time (compose
# injects it via env_file). It is NOT an ARG and NOT an ENV here — keeping it out of
# every image layer and out of `docker history`.
COPY --chown=node:node entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod 0755 /usr/local/bin/entrypoint.sh

# No EXPOSE. No ports. Dial-out only.
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
