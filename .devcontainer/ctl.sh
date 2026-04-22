#!/bin/bash

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# CoreKinect internal registry
REGISTRY_HOST="containers.ad.corekinect.com"
REGISTRY_PORT=443

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# ── CA Certificate Management ─────────────────────────────────
# The CoreKinect container registry uses HTTPS with an internal CA.
# This function extracts the CA chain from the live TLS handshake
# and installs it into the system trust store.

install_registry_certs() {
    log_info "Checking CoreKinect registry CA certificates..."

    # Skip if already trusted
    if curl -sf --connect-timeout 5 "https://${REGISTRY_HOST}/v2/" >/dev/null 2>&1; then
        log_success "Registry CA already trusted"
        return 0
    fi

    # Verify the registry is reachable
    if ! openssl s_client -connect "${REGISTRY_HOST}:${REGISTRY_PORT}" \
         -servername "${REGISTRY_HOST}" </dev/null >/dev/null 2>&1; then
        log_warning "Cannot reach ${REGISTRY_HOST}:${REGISTRY_PORT} — skipping CA install"
        return 0
    fi

    log_info "Extracting CA chain from ${REGISTRY_HOST}:${REGISTRY_PORT}..."

    local chain_pem
    chain_pem="$(openssl s_client -showcerts \
        -connect "${REGISTRY_HOST}:${REGISTRY_PORT}" \
        -servername "${REGISTRY_HOST}" </dev/null 2>/dev/null)"

    # Extract individual certs (skip the leaf — we only need CA certs)
    local cert_dir="/usr/local/share/ca-certificates/corekinect"
    mkdir -p "$cert_dir"

    local cert_index=0
    local in_cert=false
    local current_cert=""
    local installed=0

    while IFS= read -r line; do
        if [[ "$line" == "-----BEGIN CERTIFICATE-----" ]]; then
            in_cert=true
            current_cert="$line"$'\n'
        elif [[ "$line" == "-----END CERTIFICATE-----" ]]; then
            current_cert+="$line"$'\n'
            in_cert=false
            cert_index=$((cert_index + 1))

            # Skip cert 0 (leaf/server cert) — only install CA certs
            if [[ $cert_index -gt 1 ]]; then
                local subject
                subject="$(echo "$current_cert" | openssl x509 -noout -subject 2>/dev/null | sed 's/.*CN = //')"
                local cert_file="${cert_dir}/${subject// /_}.crt"
                echo "$current_cert" > "$cert_file"
                log_info "  Installed: ${subject}"
                installed=$((installed + 1))
            fi
        elif [[ "$in_cert" == "true" ]]; then
            current_cert+="$line"$'\n'
        fi
    done <<< "$chain_pem"

    if [[ $installed -eq 0 ]]; then
        log_warning "No CA certificates extracted from ${REGISTRY_HOST}"
        return 0
    fi

    # Update the system trust store
    update-ca-certificates >/dev/null 2>&1
    log_success "Installed ${installed} CA certificate(s) from ${REGISTRY_HOST}"
}

# Inject CA certs into the Docker buildx builder container.
# The buildkit container (Alpine-based) has a separate trust store.
install_buildkit_certs() {
    local builder_container="buildx_buildkit_concord-builder0"

    # Check if the builder container exists and is running
    if ! docker inspect "$builder_container" >/dev/null 2>&1; then
        return 0
    fi

    if ! docker inspect -f '{{.State.Running}}' "$builder_container" 2>/dev/null | grep -q true; then
        return 0
    fi

    log_info "Injecting CA certs into buildkit container..."

    local cert_dir="/usr/local/share/ca-certificates/corekinect"
    if [[ ! -d "$cert_dir" ]] || [[ -z "$(ls -A "$cert_dir" 2>/dev/null)" ]]; then
        log_warning "No CA certs to inject (run install_registry_certs first)"
        return 0
    fi

    # Append all CA certs to buildkit's bundle
    local injected=0
    for cert in "${cert_dir}"/*.crt; do
        [[ -f "$cert" ]] || continue
        docker cp "$cert" "${builder_container}:/tmp/$(basename "$cert")" 2>/dev/null || continue
        docker exec "$builder_container" sh -c "cat /tmp/$(basename "$cert") >> /etc/ssl/certs/ca-certificates.crt && rm /tmp/$(basename "$cert")" 2>/dev/null || continue
        injected=$((injected + 1))
    done

    if [[ $injected -gt 0 ]]; then
        log_success "Injected ${injected} CA cert(s) into buildkit"
    fi
}

# ── Infrastructure Verification ───────────────────────────────
# Pre-flight checks that report pass/fail for each subsystem.

verify_docker() {
    log_info "Checking Docker socket..."
    if docker info >/dev/null 2>&1; then
        log_success "Docker daemon is accessible"
        return 0
    else
        log_error "Docker socket not available — container builds will fail"
        return 1
    fi
}

verify_registry() {
    log_info "Checking container registry (${REGISTRY_HOST})..."

    if ! curl -sf --connect-timeout 5 "https://${REGISTRY_HOST}/v2/" >/dev/null 2>&1; then
        if curl -sfk --connect-timeout 5 "https://${REGISTRY_HOST}/v2/" >/dev/null 2>&1; then
            log_warning "Registry reachable but CA not trusted — installing certs"
            install_registry_certs
            if curl -sf --connect-timeout 5 "https://${REGISTRY_HOST}/v2/" >/dev/null 2>&1; then
                log_success "Registry verified after CA install"
                return 0
            fi
        fi
        log_warning "Registry ${REGISTRY_HOST} not reachable — image pulls/pushes will fail"
        return 1
    fi

    log_success "Registry ${REGISTRY_HOST} is reachable and trusted"
    return 0
}

verify_kubernetes() {
    log_info "Checking Kubernetes access..."

    if [ ! -f /root/.kube/config ]; then
        log_warning "No kubeconfig found at /root/.kube/config — K8s commands will fail"
        return 1
    fi

    if kubectl cluster-info >/dev/null 2>&1; then
        local node_count
        node_count=$(kubectl get nodes --no-headers 2>/dev/null | wc -l)
        log_success "Kubernetes cluster reachable (${node_count} node(s))"
        return 0
    else
        log_warning "Kubeconfig exists but cluster is not reachable"
        return 1
    fi
}

run_preflight() {
    local failures=0

    echo ""
    log_info "──── Preflight Checks ────"
    echo ""

    verify_docker   || failures=$((failures + 1))
    verify_registry || failures=$((failures + 1))
    verify_kubernetes || failures=$((failures + 1))

    echo ""
    if [ "$failures" -eq 0 ]; then
        log_success "All preflight checks passed"
    else
        log_warning "${failures} preflight check(s) failed — some features may not work"
    fi
    echo ""

    return 0
}

# Fix USB device permissions for J-Link and Nordic devices
fix_usb_permissions() {
    # SEGGER J-Link vendor ID: 1366
    # Nordic Semiconductor vendor ID: 1915
    local fixed=0
    for dev in /dev/bus/usb/*/*; do
        if [ -c "$dev" ]; then
            # Get bus and device numbers
            local busnum=$(basename $(dirname $dev))
            local devnum=$(basename $dev)

            # Use lsusb to check if device is J-Link or Nordic
            if lsusb -s "${busnum}:${devnum}" 2>/dev/null | grep -qE "1366:|1915:"; then
                if [ ! -w "$dev" ]; then
                    sudo chmod 666 "$dev" 2>/dev/null && fixed=$((fixed + 1))
                fi
            fi
        fi
    done
    if [ $fixed -gt 0 ]; then
        log_success "Fixed permissions for $fixed USB device(s) (J-Link/Nordic)"
    fi
}

# Start the container
start_container() {
    log_info "Starting the container"

    # Run preflight checks (non-blocking — warns but continues)
    run_preflight

    # Fix USB permissions for J-Link and Nordic devices
    fix_usb_permissions

    # Fix git safe directory for Flutter (if present)
    if [ -d /opt/flutter ]; then
        git config --global --add safe.directory /opt/flutter 2>/dev/null || true
    fi

    # Install dependencies
    yarn

    # Install Python app + test dependencies
    if [ -f apps/backend/http-api/setup.py ]; then
        log_info "Installing http-api Python dependencies..."
        pip3 install --no-cache-dir -e "apps/backend/http-api[test]" 2>/dev/null || \
            pip3 install --no-cache-dir --break-system-packages -e "apps/backend/http-api[test]" 2>/dev/null || true
    fi
}

# Create action for the devcontainers
create_action() {
    log_info "Creating action for the devcontainers"

    # Check if CONCORD_MONOREPO_ROOT is set to the correct path
    if [ "$CONCORD_MONOREPO_ROOT" = "/path/to/concord" ]; then
        echo "Error: CONCORD_MONOREPO_ROOT is set to the default value inside the file \`.env\` (repo root). Please set it to the correct path in your filesystem."
        exit 1
    fi

    # Run preflight checks (non-blocking — warns but continues)
    run_preflight

    # Install all dependencies (root + workspaces)
    yarn

    # Populate .env files from .env.example templates (skip existing)
    log_info "Setting up environment files..."
    nx setup env -c development

    # Create the platform builders
    nx run devcontainer:create-platform-builder

    # Inject CA certs into the newly created buildkit container
    install_buildkit_certs
}

# Show help
show_help() {
    echo "Concord DevContainer Control Script"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  create      Create action for the devcontainers"
    echo "  start       Start action for the devcontainers"
    echo "  preflight   Run infrastructure checks (Docker, registry, K8s)"
    echo "  help        Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 create     # Create action for devcontainers"
    echo "  $0 start      # Start action for devcontainers"
    echo ""
    echo "The script will automatically:"
    echo "  - Extract git information (branch, commit, dirty status, creator email)"
    echo "  - Create the platform builders if it doesn't exist"
    echo "  - Start the devcontainers"
}

# Main script logic
main() {
    case "${1:-help}" in
        "create")
            create_action
            ;;
        "start")
            start_container
            ;;
        "preflight")
            run_preflight
            ;;
        "help"|"-h"|"--help")
            show_help
            ;;
        *)
            log_error "Unknown command: $1"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"
