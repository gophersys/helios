# Eden frontend production image — the client-rendered SvelteKit SPA built with adapter-static and
# served by nginx, which ALSO same-origin-proxies /gateway → agentgateway and /platform →
# platformgateway (deploy/nginx.conf). ONE Dockerfile per service; the image-tag-as-environment
# contract carries `:local` for a compose load vs `<registry>/frontend:<tag>` for a registry push.
#
# Build from the MONOREPO ROOT (the frontend is a workspace member depending on @eden/* libs under
# libs/typescript/*, so the whole workspace must be in the context for the build to resolve them):
#   docker build -f apps/frontend/deploy/Dockerfile -t frontend:local .
#
# PREREQUISITE: the @eden/* workspace libraries must be BUILT (their dist/ present) in the build
# context — the frontend consumes each lib's emitted dist (package.json "svelte"/"exports" → ./dist).
# The libs' Svelte build toolchain (@sveltejs/package + vite-plugin-svelte) resolves only through the
# yarn-4 workspace install, which is not reproducible in a lean image, so the libs are built ONCE in
# the devcontainer (the ADR-0022 dev/CI substrate with the full toolchain — the release workflow runs
# `apps/frontend/deploy/build-libs.sh` before this docker build) and their dist is shipped in. The
# Dockerfile-scoped .dockerignore (Dockerfile.dockerignore) un-ignores libs/typescript/*/dist for
# exactly this reason (the root .dockerignore strips **/dist).
#
# The build stage then runs the FRONTEND's own build (bun x resolves vite/svelte-kit on demand),
# emitting the static SPA to build/ via adapter-static (fallback: index.html). The runtime stage is
# nginx:alpine serving that output on 8080 with the SPA + reverse-proxy conf.

# ── build stage: bun over the workspace (frontend build only; libs prebuilt) ────────────────────────
# Pin bun to the SAME version the devcontainer base image bakes (.devcontainer/base/Dockerfile
# BUN_VERSION) so the deploy build matches the dev/CI runtime — no drift.
ARG BUN_VERSION=1.3.14
FROM oven/bun:${BUN_VERSION}-alpine AS build
WORKDIR /src

# Copy the workspace (the root + Dockerfile-scoped .dockerignore keep it lean: node_modules/.svelte-kit
# stripped, but the prebuilt libs/typescript/*/dist kept). Fail fast if the prebuilt lib dist is absent.
COPY . .
RUN test -f libs/typescript/primitives/dist/index.js \
    || { echo "ERROR: @eden/* libs are not built — run apps/frontend/deploy/build-libs.sh in the devcontainer before this docker build" >&2; exit 1; }

# Install the workspace so the frontend resolves its own deps + the workspace:* @eden/* libs (from
# their prebuilt dist), then build ONLY the frontend. The canonical workspace lockfile is yarn.lock
# (yarn 4), and the root bun.lock is a gitignored container-side artifact — absent in a fresh CI
# checkout — so `bun install` here resolves from package.json (no --frozen-lockfile: there is no
# committed root bun.lock to freeze against). svelte-kit sync generates the .svelte-kit types tsconfig
# a fresh checkout lacks; vite build emits the static SPA to build/ (adapter-static SPA fallback).
RUN bun install
WORKDIR /src/apps/frontend
RUN bun x svelte-kit sync && bun x vite build

# ── runtime stage: nginx:alpine serving the static SPA + reverse proxy ──────────────────────────────
FROM nginx:alpine AS runtime
# The Eden SPA + same-origin-proxy config carries a ${NGINX_LOCAL_RESOLVERS} placeholder (the pod's
# cluster DNS, for lazy upstream resolution). Ship it as a template; a docker-entrypoint.d step
# envsubsts it into the real nginx.conf at container start (the base image populates that var in
# 15-local-resolvers.envsh, which runs before our numbered step). Listens on 8080.
COPY apps/frontend/deploy/nginx.conf /etc/nginx/nginx.conf.template
COPY apps/frontend/deploy/16-envsubst-eden-nginx.sh /docker-entrypoint.d/16-envsubst-eden-nginx.sh
# The static build output is the site root nginx serves.
COPY --from=build /src/apps/frontend/build /usr/share/nginx/html
EXPOSE 8080
# nginx runs in the foreground (the image's default CMD already does `nginx -g 'daemon off;'`). The
# container runs as root through the docker-entrypoint.d chain (to render the config + bind), then
# nginx drops its workers to the non-root `nginx` user (the config keeps every writable path in /tmp).
