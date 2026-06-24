# http-gateway image (the application-template default, ADR-0023). ONE Dockerfile per service; the
# image-tag-as-environment-contract carries `:local` for a compose load vs
# `<registry>/http-gateway:<tag>` for a registry push. The gateway holds no harness and resolves its
# secret values at runtime through the Vault sidecar, so its runtime stage is a minimal, non-root
# distroless base (no harness toolchain needed).
#
# Build from the MONOREPO ROOT (the build stage regenerates go.work via scripts/gen-go-work.sh, so a
# clean checkout with no committed go.work still resolves the in-repo sibling libraries):
#   docker build -f libs/templates/go/http-gateway/deploy/Dockerfile -t http-gateway:local .
#
# SKELETON: a generated app keeps this shape; it changes only the binary name / exposed port if it
# diverges from the template defaults.

# ── build stage ───────────────────────────────────────────────────────────────────────────────────
# Pin the Go patch (not the floating golang:1.26) — matches the devcontainer ARG GO_VERSION + go.mod
# toolchain, closing the stdlib-CVE window a floating tag drifts into.
ARG GO_VERSION=1.26.4
FROM golang:${GO_VERSION} AS build
WORKDIR /src
COPY . .
# Regenerate go.work from the tracked module list (scripts/gen-go-work.sh) — go.work is gitignored,
# so a clean checkout / git-archive build context has none; the generator pins the v0.0.0 sibling
# libs to in-repo source deterministically before the build resolves them.
RUN bash scripts/gen-go-work.sh
ENV GOWORK=/src/go.work CGO_ENABLED=0
RUN --mount=type=cache,target=/root/.cache/go-build \
    --mount=type=cache,target=/go/pkg/mod \
    go build -trimpath -ldflags='-s -w' -o /out/http-gateway \
      ./libs/templates/go/http-gateway/cmd/gateway

# ── runtime stage: minimal, non-root ──────────────────────────────────────────────────────────────
FROM gcr.io/distroless/static-debian12:nonroot AS runtime
COPY --from=build /out/http-gateway /usr/local/bin/http-gateway
EXPOSE 8080
# EDEN_GATEWAY_JWT_SECRET_REF (a Vault reference), VAULT_ADDR, EDEN_VAULT_MODE, EDEN_GATEWAY_ADDRESS
# are injected by the deployment; the gateway requires the JWT secret reference (behind auth even
# locally) and resolves its value through the Vault sidecar at startup — never an inlined value.
ENTRYPOINT ["/usr/local/bin/http-gateway"]
