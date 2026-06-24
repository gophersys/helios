# Eden agent-runtime pod image (Milestone-B B8, the B4 b8Handoff). The agent pod's MAIN process IS
# this binary (the workspaceprovider Entrypoint capability, ADR-0022 #4): a PID-1 graceful-shutdown
# state machine that runs the harness via agentsession and bridges its event stream to JetStream.
#
# It DOGFOODS the .devcontainer base image family (ADR-0022 #2): the runtime stage is FROM the same
# ghcr.io/gophersys/base image the dev + CI substrate uses, so the spawned pod carries the EXACT
# pinned harness toolchain (claude/omp) the adapters parse — no drift between "what the agent runs"
# and "what the gate proved".
#
# Build from the repo root (the build stage regenerates go.work via scripts/gen-go-work.sh, so a
# clean checkout with no committed go.work still resolves the in-repo sibling libs); the Claude Code
# version is REQUIRED and sourced from harnesses/versions.env (ADR-0021 — the pin has one home):
#   docker build -f deploy/image/agent-runtime.Dockerfile \
#     --build-arg CLAUDE_CODE_VERSION="$(grep ^CLAUDE_CODE_VERSION harnesses/versions.env | cut -d= -f2)" \
#     -t agent-runtime:local .
#
# Image-tag-as-environment-contract: tag `:local` for a compose load, `<registry>/agent-runtime:<tag>`
# for a registry push (one Dockerfile, the tag is the only difference).

# ── build stage: compile the static-ish Go binary over the workspace ──────────────────────────────
ARG BASE_IMAGE=ghcr.io/gophersys/base:latest
# Pin the Go patch (not the floating golang:1.26) — matches the devcontainer ARG GO_VERSION + go.mod
# toolchain, closing the stdlib-CVE window a floating tag drifts into.
ARG GO_VERSION=1.26.4
FROM golang:${GO_VERSION} AS build
WORKDIR /src

# Copy the whole workspace (the go.work pins the sibling libs to in-repo source). A .dockerignore
# trims node_modules/.git/etc so the context stays lean.
COPY . .

# Regenerate go.work from the tracked module list (scripts/gen-go-work.sh) — go.work is gitignored,
# so a clean checkout / git-archive build context has none; the generator pins the v0.0.0 sibling
# libs to in-repo source deterministically before the build resolves them.
RUN bash scripts/gen-go-work.sh

ENV GOWORK=/src/go.work CGO_ENABLED=0
RUN --mount=type=cache,target=/root/.cache/go-build \
    --mount=type=cache,target=/go/pkg/mod \
    go build -trimpath -ldflags='-s -w' -o /out/agent-runtime ./apps/agent-runtime/cmd/agent-runtime

# ── runtime stage: dogfood the devcontainer base (carries the pinned harnesses) ───────────────────
FROM ${BASE_IMAGE} AS runtime
# The base image runs as user `dev`; the workload provisions its workspace under /workspace.
USER dev
WORKDIR /workspace
COPY --from=build /out/agent-runtime /usr/local/bin/agent-runtime

# Bake the supervisor `.claude` operating manual into the image (ADDITIVE — the in-pod clone-on-boot
# path, gated on EDEN_WORKDIR_REPO, overlays it; the existing assistant/probe boot never reads it).
# The agent-runtime binary's workdir.go reads /opt/eden/supervisor-manual at boot and os.CopyFS's it
# over the cloned repo's .claude — cross-module go:embed is impossible (the manual lives in the libs
# submodule, not this app's Go module), so it is a baked filesystem path, not an embedded asset. This
# is the image-side half of the in-pod analog of the host-side projectcreate.Materializer.
COPY libs/plugins/supervisor/template/.claude /opt/eden/supervisor-manual

# Install the pinned Claude Code harness. The base image installs harnesses at devcontainer
# post-create (NOT baked into base), so the agent-pod image MUST install it explicitly — the in-pod
# supervisor runs `claude` as its PID-1 child, and an absent binary is a boot failure, not a skip.
# Installed via the official installer to /home/dev/.local/bin (already on PATH). The version is a
# REQUIRED build ARG sourced from harnesses/versions.env (ADR-0021: the pin has ONE home; never a
# hardcoded second source of truth). omp/codex are not installed here (the supervisor is claude-only).
ARG CLAUDE_CODE_VERSION
RUN test -n "${CLAUDE_CODE_VERSION}" || { echo "CLAUDE_CODE_VERSION build-arg required (source harnesses/versions.env)" >&2; exit 1; }; \
    curl -fsSL https://claude.ai/install.sh | bash -s "${CLAUDE_CODE_VERSION}" \
    && /home/dev/.local/bin/claude --version

# The PID-1 workload. The orchestrator/provider sets EDEN_AGENT_ID, EDEN_NATS_URL, EDEN_HARNESS,
# EDEN_CREDENTIAL_REF, EDEN_WORKSPACE, and mounts the Vault sidecar token at /vault/secrets/token.
ENTRYPOINT ["/usr/local/bin/agent-runtime"]
