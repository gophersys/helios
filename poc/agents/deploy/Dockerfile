FROM oven/bun:1.3 AS omp-base

# Install OMP CLI globally
RUN bun add -g @oh-my-pi/pi-coding-agent@15.9.67

# Build Go runtime
FROM golang:1.26 AS go-build

WORKDIR /build
COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 go build -o /build/agentd ./cmd/agentd

# Runtime image
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Install Bun and OMP in the runtime image
RUN apt-get update && apt-get install -y --no-install-recommends unzip && \
    curl -fsSL https://bun.sh/install | bash && \
    ln -s /root/.bun/bin/bun /usr/local/bin/bun && \
    /root/.bun/bin/bun add -g @oh-my-pi/pi-coding-agent@15.9.67 && \
    ln -s /root/.bun/bin/omp /usr/local/bin/omp && \
    apt-get remove -y unzip && \
    rm -rf /var/lib/apt/lists/*

# Verify installation
RUN omp --version

# Copy Go agent runtime
COPY --from=go-build /build/agentd /usr/local/bin/agentd

# Create OMP directory structure
RUN mkdir -p /etc/omp/agent /etc/omp/project /var/lib/omp/sessions /var/lib/omp/reports

# Expose ports
EXPOSE 8080 9090

# Health check
HEALTHCHECK --interval=15s --timeout=5s --retries=3 \
    CMD curl -sf http://localhost:8080/api/v1/health || exit 1

# Entrypoint
COPY deploy/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV OMP_AGENT_DIR=/etc/omp/agent \
    OMP_PROJECT_DIR=/etc/omp/project \
    PORT=8080 \
    OMP_PATH=omp

ENTRYPOINT ["/entrypoint.sh"]