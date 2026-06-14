# Eden agentgateway image (Milestone-B B8). The STATELESS NATS→SSE bridge + REST-POST control
# plane (ADR-0022 #3): any replica serves any session via JetStream durable replay, so it scales
# horizontally. The container's main process is the production gateway (cmd/agentgateway) — NOT the
# dev/live convenience binaries (those import test fakes and are never shipped).
#
# The gateway holds no harness and resolves no credential value, so its runtime stage is a minimal
# distroless base (no harness toolchain needed) — unlike agent-runtime, which dogfoods the
# devcontainer base because it spawns the real harness.
#
# Build (from the repo root, with the go.work in context):
#   docker build -f deploy/image/agentgateway.Dockerfile -t agentgateway:local .
#
# Image-tag-as-environment-contract: `:local` for a compose load, `<registry>/agentgateway:<tag>`
# for a registry push.

# ── build stage ───────────────────────────────────────────────────────────────────────────────────
FROM golang:1.26 AS build
WORKDIR /src
COPY . .
ENV GOWORK=/src/go.work CGO_ENABLED=0
RUN --mount=type=cache,target=/root/.cache/go-build \
    --mount=type=cache,target=/go/pkg/mod \
    go build -trimpath -ldflags='-s -w' -o /out/agentgateway ./apps/agentgateway/cmd/agentgateway

# ── runtime stage: minimal, non-root ──────────────────────────────────────────────────────────────
FROM gcr.io/distroless/static-debian12:nonroot AS runtime
COPY --from=build /out/agentgateway /usr/local/bin/agentgateway
EXPOSE 8080
# EDEN_GATEWAY_JWT_SECRET (a kubernetes Secret reference), EDEN_NATS_URL, EDEN_GATEWAY_ADDRESS are
# injected by the deployment; the gateway requires the JWT secret (behind auth even locally).
ENTRYPOINT ["/usr/local/bin/agentgateway"]
