# Eden agentgateway image (Milestone-B B8 + W5). It ships TWO production binaries built from this
# app, selected by the container command:
#
#   - /usr/local/bin/agentgateway (the ENTRYPOINT default) — the STATELESS NATS→SSE bridge +
#     REST-POST control plane (ADR-0022 #3): any replica serves any session via JetStream durable
#     replay, so it scales horizontally.
#   - /usr/local/bin/agentgateway-orchestrator — the KUBERNETES orchestrator role (W5): runs the
#     reconcile loop under a real coordination.k8s.io/v1 Lease. The orchestrator Deployment
#     (apps/agentgateway/deploy/kubernetes/40-orchestrator-deployment.yaml) invokes it explicitly
#     via `command: ["/usr/local/bin/agentgateway-orchestrator"]`.
#
# NEITHER is the dev/live convenience binary (those import test fakes and are never shipped).
#
# The gateway holds no harness, so its runtime stage is a minimal distroless base (no harness
# toolchain needed) — unlike agent-runtime, which dogfoods the devcontainer base because it spawns
# the real harness. It DOES resolve exactly one credential VALUE at boot — its dev-JWT HMAC signing
# key — from Vault via EDEN_GATEWAY_JWT_SECRET_REF (an HTTP resolution, no toolchain), used
# point-of-use and zeroized (H8). The orchestrator role likewise spawns no harness in-process (the
# supervisor runs in a provisioned workspace pod), so it shares this minimal base; it resolves the
# harness credential only as an opaque Vault reference (server-side at Open).
#
# Build from the repo root (the build stage regenerates go.work via scripts/gen-go-work.sh, so a
# clean checkout with no committed go.work still resolves the in-repo sibling libs):
#   docker build -f deploy/image/agentgateway.Dockerfile -t agentgateway:local .
#
# Image-tag-as-environment-contract: `:local` for a compose load, `<registry>/agentgateway:<tag>`
# for a registry push.

# ── build stage ───────────────────────────────────────────────────────────────────────────────────
# Pin the Go patch (not the floating golang:1.26) — matches the devcontainer ARG GO_VERSION + go.mod
# toolchain, and closes the stdlib-CVE window a floating tag drifts into. cictl can track this ARG.
ARG GO_VERSION=1.26.4
FROM golang:${GO_VERSION} AS build
WORKDIR /src
COPY . .
# Regenerate go.work from the tracked module list (scripts/gen-go-work.sh) — go.work is gitignored,
# so a clean checkout / git-archive build context has none; the generator pins the v0.0.0 sibling
# libs to in-repo source deterministically before the build resolves them.
RUN bash scripts/gen-go-work.sh
ENV GOWORK=/src/go.work CGO_ENABLED=0
# Build BOTH production binaries in one layer (shared build/module caches). The orchestrator role is
# the W5 kubernetes reconcile-loop composition root; the manifest selects it via an explicit command.
RUN --mount=type=cache,target=/root/.cache/go-build \
    --mount=type=cache,target=/go/pkg/mod \
    go build -trimpath -ldflags='-s -w' -o /out/agentgateway ./apps/agentgateway/cmd/agentgateway && \
    go build -trimpath -ldflags='-s -w' -o /out/agentgateway-orchestrator ./apps/agentgateway/cmd/agentgateway-orchestrator

# ── runtime stage: minimal, non-root ──────────────────────────────────────────────────────────────
FROM gcr.io/distroless/static-debian12:nonroot AS runtime
COPY --from=build /out/agentgateway /usr/local/bin/agentgateway
COPY --from=build /out/agentgateway-orchestrator /usr/local/bin/agentgateway-orchestrator
EXPOSE 8080
# EDEN_GATEWAY_JWT_SECRET_REF (an opaque vault:// reference the gateway resolves through the
# dual-mode Vault provider — EDEN_VAULT_MODE/EDEN_VAULT_TOKEN_FILE/VAULT_ADDR), EDEN_NATS_URL, and
# EDEN_GATEWAY_ADDRESS are injected by the deployment; the gateway requires the JWT signing-key
# reference (behind auth even locally). The orchestrator Deployment overrides this ENTRYPOINT with an
# explicit command to select its binary.
ENTRYPOINT ["/usr/local/bin/agentgateway"]
