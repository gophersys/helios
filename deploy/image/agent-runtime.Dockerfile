# Eden agent-runtime pod image (Milestone-B B8, the B4 b8Handoff). The agent pod's MAIN process IS
# this binary (the workspaceprovider Entrypoint capability, ADR-0022 #4): a PID-1 graceful-shutdown
# state machine that runs the harness via agentsession and bridges its event stream to JetStream.
#
# It DOGFOODS the .devcontainer base image family (ADR-0022 #2): the runtime stage is FROM the same
# ghcr.io/gophersys/base image the dev + CI substrate uses, so the spawned pod carries the EXACT
# pinned harness toolchain (claude/omp) the adapters parse — no drift between "what the agent runs"
# and "what the gate proved".
#
# Build (from the repo root, with the go.work in context):
#   docker build -f deploy/image/agent-runtime.Dockerfile -t agent-runtime:local .
#
# Image-tag-as-environment-contract: tag `:local` for a compose load, `<registry>/agent-runtime:<tag>`
# for a registry push (one Dockerfile, the tag is the only difference).

# ── build stage: compile the static-ish Go binary over the workspace ──────────────────────────────
ARG BASE_IMAGE=ghcr.io/gophersys/base:latest
FROM golang:1.26 AS build
WORKDIR /src

# Copy the whole workspace (the go.work pins the sibling libs to in-repo source). A .dockerignore
# trims node_modules/.git/etc so the context stays lean.
COPY . .

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

# The PID-1 workload. The orchestrator/provider sets EDEN_AGENT_ID, EDEN_NATS_URL, EDEN_HARNESS,
# EDEN_CREDENTIAL_REF, EDEN_WORKSPACE, and mounts the Vault sidecar token at /vault/secrets/token.
ENTRYPOINT ["/usr/local/bin/agent-runtime"]
