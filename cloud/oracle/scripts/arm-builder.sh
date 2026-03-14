#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# arm-builder.sh — On-demand ARM builder on AWS (per-second billing)
#
# Manages a t4g.small (Graviton2 ARM) EC2 instance that is STOPPED when idle
# and STARTED on demand. EBS root volume persists Docker layer cache across
# stop/start cycles. Per-second billing means you pay only for build minutes.
#
# Usage:
#   arm-builder up                            Start the builder (~20s resume)
#   arm-builder down                          Stop the builder ($0 compute)
#   arm-builder ensure                        Idempotent — start if stopped
#   arm-builder status                        Check state and cost
#   arm-builder ssh                           SSH into the builder
#   arm-builder build [options] <context>     Build a container image
#
# Options:
#   -t, --tag <tag>          Image tag (default: test:latest)
#   -f, --file <dockerfile>  Dockerfile path (default: Dockerfile)
#   --push                   Push after build
#   --idle <n>               Idle timeout in minutes (default: 10)
#
# Environment:
#   AWS_ACCESS_KEY_ID        Required (or in ~/.aws/credentials)
#   AWS_SECRET_ACCESS_KEY    Required (or in ~/.aws/credentials)
#   AWS_REGION               Optional (default: us-west-2)
#   GITHUB_TOKEN             Optional (for ghcr.io push)
#
# Cost:
#   Free tier (through Dec 2026): $0 compute, ~$4/mo EBS
#   After free tier: ~$0.017/hr per-second billed
#   Auto-stops after 10 min idle.
###############################################################################

# ── Constants ────────────────────────────────────────────────────────────────

BUILDER_TAG_KEY="Name"
BUILDER_TAG_VALUE="arm-builder"
DEFAULT_IDLE_MINUTES=10
SSH_USER="ubuntu"
AWS_REGION="${AWS_REGION:-us-west-2}"

# ── Resolve paths & env ──────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ORACLE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
INFRA_DIR="$(cd "${ORACLE_DIR}/../.." && pwd)"

# Source .env if available (for GITHUB_TOKEN, AWS creds)
for envfile in \
    "${ORACLE_DIR}/.env" \
    "${INFRA_DIR}/.env" \
    "${INFRA_DIR}/../codectl/.devcontainer/.env" \
    "${INFRA_DIR}/../fintel/.devcontainer/.env"; do
    if [[ -f "${envfile}" ]]; then
        # shellcheck disable=SC1090
        source "${envfile}"
        break
    fi
done

IDLE_MINUTES="${DEFAULT_IDLE_MINUTES}"

# ── Helpers ──────────────────────────────────────────────────────────────────

log()  { echo "▸ $*" >&2; }
ok()   { echo "✓ $*" >&2; }
fail() { echo "✗ $*" >&2; exit 1; }
dim()  { echo "  $*" >&2; }

# ── AWS Instance Discovery ──────────────────────────────────────────────────

get_builder_instance_id() {
    aws ec2 describe-instances \
        --region "${AWS_REGION}" \
        --filters "Name=tag:${BUILDER_TAG_KEY},Values=${BUILDER_TAG_VALUE}" \
                  "Name=instance-state-name,Values=running,stopped,pending,stopping" \
        --query 'Reservations[0].Instances[0].InstanceId' \
        --output text 2>/dev/null || echo "None"
}

get_builder_state() {
    local instance_id="$1"
    aws ec2 describe-instances \
        --region "${AWS_REGION}" \
        --instance-ids "${instance_id}" \
        --query 'Reservations[0].Instances[0].State.Name' \
        --output text 2>/dev/null || echo "unknown"
}

get_builder_ip() {
    local instance_id="$1"
    aws ec2 describe-instances \
        --region "${AWS_REGION}" \
        --instance-ids "${instance_id}" \
        --query 'Reservations[0].Instances[0].PublicIpAddress' \
        --output text 2>/dev/null || echo ""
}

find_ssh_key() {
    for keypath in \
        "${SSH_KEY_PATH:-}" \
        "${HOME}/.ssh/arm-builder" \
        "${ORACLE_DIR}/terraform/cluster-key.pem" \
        "${HOME}/.ssh/codectl-bastion" \
        "${HOME}/.ssh/id_ed25519" \
        "${HOME}/.ssh/id_rsa"; do
        if [[ -n "${keypath}" && -f "${keypath}" ]]; then
            echo "${keypath}"
            return
        fi
    done
    fail "No SSH key found. Set SSH_KEY_PATH or place arm-builder key at ~/.ssh/arm-builder"
}

wait_for_ssh() {
    local ip="$1"
    local key="$2"
    local max_wait=120
    local elapsed=0
    log "Waiting for SSH on ${ip}..."
    while ! ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 -o BatchMode=yes \
        -i "${key}" "${SSH_USER}@${ip}" "true" 2>/dev/null; do
        elapsed=$((elapsed + 3))
        if [[ ${elapsed} -ge ${max_wait} ]]; then
            fail "SSH timeout after ${max_wait}s"
        fi
        sleep 3
    done
}

wait_for_docker() {
    local ip="$1"
    local key="$2"
    local max_wait=60
    local elapsed=0
    while ! ssh -o StrictHostKeyChecking=no -o BatchMode=yes \
        -i "${key}" "${SSH_USER}@${ip}" \
        "sudo docker info > /dev/null 2>&1" 2>/dev/null; do
        elapsed=$((elapsed + 3))
        if [[ ${elapsed} -ge ${max_wait} ]]; then
            fail "Docker timeout after ${max_wait}s"
        fi
        sleep 3
    done
}

setup_ghcr_auth() {
    local ip="$1"
    local key="$2"

    # Resolve GITHUB_TOKEN from env or .env files
    local token="${GITHUB_TOKEN:-}"
    if [[ -z "${token}" ]]; then
        for envfile in \
            "${INFRA_DIR}/../codectl/.devcontainer/.env" \
            "${INFRA_DIR}/../fintel/.devcontainer/.env" \
            "${ORACLE_DIR}/.env" \
            "${INFRA_DIR}/.env"; do
            if [[ -f "${envfile}" ]]; then
                token=$(grep -oP '^GITHUB_TOKEN=\K.*' "${envfile}" 2>/dev/null | head -1 || true)
                [[ -n "${token}" ]] && break
            fi
        done
    fi

    if [[ -z "${token}" ]]; then
        dim "No GITHUB_TOKEN found — builder won't be able to push to ghcr.io"
        dim "Set GITHUB_TOKEN in env or .devcontainer/.env to enable push"
        return 0
    fi

    log "Configuring ghcr.io auth on builder..."
    ssh -o StrictHostKeyChecking=no -o BatchMode=yes -i "${key}" "${SSH_USER}@${ip}" \
        "echo '${token}' | sudo docker login ghcr.io -u MateoSegura --password-stdin" \
        >/dev/null 2>&1 && ok "ghcr.io authenticated on builder" || dim "ghcr.io auth failed (non-fatal)"
}

# ── Commands ─────────────────────────────────────────────────────────────────

cmd_up() {
    local instance_id
    instance_id=$(get_builder_instance_id)

    if [[ "${instance_id}" == "None" || -z "${instance_id}" ]]; then
        fail "No arm-builder instance found in AWS ${AWS_REGION}. Run Terraform first:
  cd cloud/aws/terraform && terraform apply"
    fi

    local state
    state=$(get_builder_state "${instance_id}")

    case "${state}" in
        running)
            local ip
            ip=$(get_builder_ip "${instance_id}")
            ok "Builder already running: ${ip}"
            echo "${ip}"
            return 0
            ;;
        stopped)
            log "Starting builder ${instance_id}..."
            aws ec2 start-instances \
                --region "${AWS_REGION}" \
                --instance-ids "${instance_id}" \
                --query 'StartingInstances[0].CurrentState.Name' \
                --output text > /dev/null 2>&1

            # Wait for running
            log "Waiting for instance to start..."
            aws ec2 wait instance-running \
                --region "${AWS_REGION}" \
                --instance-ids "${instance_id}" 2>/dev/null
            ;;
        pending)
            log "Instance is starting..."
            aws ec2 wait instance-running \
                --region "${AWS_REGION}" \
                --instance-ids "${instance_id}" 2>/dev/null
            ;;
        stopping)
            log "Instance is stopping — waiting, then restarting..."
            aws ec2 wait instance-stopped \
                --region "${AWS_REGION}" \
                --instance-ids "${instance_id}" 2>/dev/null
            aws ec2 start-instances \
                --region "${AWS_REGION}" \
                --instance-ids "${instance_id}" > /dev/null 2>&1
            aws ec2 wait instance-running \
                --region "${AWS_REGION}" \
                --instance-ids "${instance_id}" 2>/dev/null
            ;;
        *)
            fail "Builder in unexpected state: ${state}"
            ;;
    esac

    local ip ssh_key
    ip=$(get_builder_ip "${instance_id}")
    ssh_key=$(find_ssh_key)
    ok "Instance running: ${ip}"

    wait_for_ssh "${ip}" "${ssh_key}"
    ok "SSH ready"

    wait_for_docker "${ip}" "${ssh_key}"
    ok "Docker ready"

    setup_ghcr_auth "${ip}" "${ssh_key}"

    echo "${ip}"
}

cmd_down() {
    local instance_id
    instance_id=$(get_builder_instance_id)

    if [[ "${instance_id}" == "None" || -z "${instance_id}" ]]; then
        ok "No builder found"
        return 0
    fi

    local state
    state=$(get_builder_state "${instance_id}")

    if [[ "${state}" == "stopped" ]]; then
        ok "Builder already stopped"
        return 0
    fi

    log "Stopping builder ${instance_id}..."
    aws ec2 stop-instances \
        --region "${AWS_REGION}" \
        --instance-ids "${instance_id}" \
        --query 'StoppingInstances[0].CurrentState.Name' \
        --output text > /dev/null 2>&1

    ok "Builder stopping (EBS persists, \$0 compute)"
}

cmd_ensure() {
    # Idempotent: return builder IP, starting it if needed. Minimal output.
    local instance_id
    instance_id=$(get_builder_instance_id)

    if [[ "${instance_id}" == "None" || -z "${instance_id}" ]]; then
        fail "No arm-builder instance found in AWS ${AWS_REGION}. Run Terraform first."
    fi

    local state
    state=$(get_builder_state "${instance_id}")

    if [[ "${state}" == "running" ]]; then
        local ip ssh_key
        ip=$(get_builder_ip "${instance_id}")
        ssh_key=$(find_ssh_key 2>/dev/null || true)
        if [[ -n "${ssh_key}" ]]; then
            setup_ghcr_auth "${ip}" "${ssh_key}" 2>/dev/null || true
        fi
        echo "${ip}"
        return 0
    fi

    cmd_up
}

cmd_status() {
    local instance_id
    instance_id=$(get_builder_instance_id)

    if [[ "${instance_id}" == "None" || -z "${instance_id}" ]]; then
        echo "Status:   NOT PROVISIONED"
        echo "Action:   Run Terraform to create the builder"
        return 0
    fi

    local state ip
    state=$(get_builder_state "${instance_id}")
    ip=$(get_builder_ip "${instance_id}")

    echo "Instance: ${instance_id}"
    echo "Region:   ${AWS_REGION}"
    echo "Status:   ${state^^}"
    if [[ "${state}" == "running" ]]; then
        echo "IP:       ${ip}"
        echo "Cost:     \$0.017/hr (free tier: \$0)"
    else
        echo "Cost:     \$0.00/hr (stopped)"
    fi
    echo "EBS:      ~\$4/mo (50 GB gp3, Docker cache persists)"
    echo "Resume:   ~20s from stopped"
}

cmd_ssh() {
    local instance_id ip ssh_key
    instance_id=$(get_builder_instance_id)
    [[ "${instance_id}" == "None" ]] && fail "No builder found. Run: arm-builder up"

    local state
    state=$(get_builder_state "${instance_id}")
    [[ "${state}" != "running" ]] && fail "Builder is ${state}. Run: arm-builder up"

    ip=$(get_builder_ip "${instance_id}")
    ssh_key=$(find_ssh_key)
    exec ssh -o StrictHostKeyChecking=no -i "${ssh_key}" "${SSH_USER}@${ip}"
}

cmd_build() {
    local tag="test:latest"
    local dockerfile="Dockerfile"
    local push=false
    local context="."
    local extra_args=()

    while [[ $# -gt 0 ]]; do
        case "$1" in
            -t|--tag)     tag="$2"; shift 2 ;;
            -f|--file)    dockerfile="$2"; shift 2 ;;
            --push)       push=true; shift ;;
            --idle)       IDLE_MINUTES="$2"; shift 2 ;;
            -*)           extra_args+=("$1"); shift ;;
            *)            context="$1"; shift ;;
        esac
    done

    # Ensure builder is up
    local ip
    ip=$(cmd_up)

    local ssh_key
    ssh_key=$(find_ssh_key)

    # Build via DOCKER_HOST pointed at remote
    log "Building ${tag} on ARM (${SSH_USER}@${ip})..."

    local build_args=(
        "--platform" "linux/arm64"
        "-t" "${tag}"
        "-f" "${dockerfile}"
    )
    if [[ "${push}" == "true" ]]; then
        build_args+=("--push")
    fi
    build_args+=("${extra_args[@]}")
    build_args+=("${context}")

    local start_time
    start_time=$(date +%s)

    DOCKER_HOST="ssh://${SSH_USER}@${ip}" docker buildx build "${build_args[@]}"

    local end_time elapsed
    end_time=$(date +%s)
    elapsed=$((end_time - start_time))
    ok "Build complete in ${elapsed}s"

    # Reset idle timer on the builder
    ssh -o StrictHostKeyChecking=no -o BatchMode=yes -i "${ssh_key}" \
        "${SSH_USER}@${ip}" "touch /tmp/idle-check" 2>/dev/null || true

    dim "Builder will auto-stop after ${IDLE_MINUTES}min idle"
}

# ── Main ─────────────────────────────────────────────────────────────────────

while [[ $# -gt 0 ]]; do
    case "$1" in
        --idle)       IDLE_MINUTES="$2"; shift 2 ;;
        up)           cmd_up; exit $? ;;
        down)         cmd_down; exit $? ;;
        ensure)       cmd_ensure; exit $? ;;
        status)       cmd_status; exit $? ;;
        ssh)          cmd_ssh; exit $? ;;
        build)        shift; cmd_build "$@"; exit $? ;;
        *)
            echo "Usage: arm-builder {up|down|ensure|status|ssh|build} [options]"
            echo ""
            echo "Commands:"
            echo "  up          Start the ARM builder (~20s from stopped)"
            echo "  down        Stop the builder (\$0 compute, EBS persists)"
            echo "  ensure      Idempotent start (for CI/scripts)"
            echo "  status      Show builder state and cost"
            echo "  ssh         SSH into the builder"
            echo "  build       Build a container image on ARM"
            echo ""
            echo "Options:"
            echo "  --idle <n>  Idle timeout in minutes (default: 10)"
            echo ""
            echo "Examples:"
            echo "  arm-builder up                              # Start builder"
            echo "  arm-builder build -t myapp:latest .         # Build on ARM"
            echo "  arm-builder build -t img --push .           # Build and push"
            echo "  arm-builder down                            # Stop it"
            echo ""
            echo "Cost: \$0 compute (free tier through Dec 2026)"
            echo "      ~\$4/mo EBS (Docker cache persists across restarts)"
            echo "      Auto-stops after ${DEFAULT_IDLE_MINUTES}min idle"
            exit 1
            ;;
    esac
done

echo "Usage: arm-builder {up|down|ensure|status|ssh|build}"
exit 1
