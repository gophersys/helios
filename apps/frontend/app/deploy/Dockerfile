# Multi-stage build: Node build → Nginx serve
# -----------------------------------------------------------
#                                                  Build Stage
# -----------------------------------------------------------
FROM node:22-alpine AS builder

WORKDIR /app

# Build arguments injected at build time (baked into static JS)
ARG PUBLIC_APP_VERSION=0.0.0
ARG PUBLIC_APP_ENVIRONMENT=production
ENV PUBLIC_APP_VERSION=${PUBLIC_APP_VERSION}
ENV PUBLIC_APP_ENVIRONMENT=${PUBLIC_APP_ENVIRONMENT}

# Install dependencies first (better layer caching)
COPY apps/frontend/app/package.json ./
COPY apps/frontend/app/package-lock.json* ./
RUN npm ci --ignore-scripts 2>/dev/null || npm install

# Copy source
COPY apps/frontend/app/ ./

# Build static site (outputs to dist/)
RUN npm run build

# -----------------------------------------------------------
#                                                 Serve Stage
# -----------------------------------------------------------
FROM nginx:1.27-alpine

# Build metadata (re-declared for this stage)
ARG PUBLIC_APP_VERSION=0.0.0
ARG PUBLIC_APP_ENVIRONMENT=production
ARG GIT_COMMIT=unknown
ARG GIT_BRANCH=unknown
ARG GIT_DIRTY=false
ARG BUILD_TIME=unknown
ARG BUILD_HOST=unknown

# Copy built static files
COPY --from=builder /app/dist /usr/share/nginx/html

# Write build metadata as a static JSON file served at /build-info.json
RUN printf '{"service":"concord-frontend","version":"%s","environment":"%s","git_commit":"%s","git_branch":"%s","git_dirty":"%s","build_time":"%s","build_host":"%s"}' \
  "${PUBLIC_APP_VERSION}" "${PUBLIC_APP_ENVIRONMENT}" "${GIT_COMMIT}" "${GIT_BRANCH}" "${GIT_DIRTY}" "${BUILD_TIME}" "${BUILD_HOST}" \
  > /usr/share/nginx/html/build-info.json

# Copy nginx config template + entrypoint
COPY apps/frontend/app/deploy/nginx.conf.template /etc/nginx/templates/default.conf.template
COPY apps/frontend/app/deploy/docker-entrypoint.sh /docker-entrypoint.d/40-envsubst-concord.sh
RUN chmod +x /docker-entrypoint.d/40-envsubst-concord.sh

# Default env vars (overridden at runtime)
ENV API_HOST=http-api
ENV API_PORT=9001

EXPOSE 80

# nginx:alpine image auto-runs /docker-entrypoint.d/*.sh scripts
