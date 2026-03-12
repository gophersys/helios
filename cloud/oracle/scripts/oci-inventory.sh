#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# oci-inventory.sh — Dynamic Ansible inventory from OCI Compute API
#
# Queries OCI for running instances, classifies them by name convention:
#   *server*    → servers group   (K3s control plane)
#   *agent*     → agents group    (K3s workers)
#   *sentinel*  → sentinels group (bastion/monitoring)
#
# Requirements:
#   - OCI CLI configured (~/.oci/config)
#   - OCI_COMPARTMENT_OCID env var set
#   - SSH_KEY_PATH env var set (or defaults to ~/.ssh/codectl-bastion)
#
# Usage:
#   ./oci-inventory.sh --list          # Ansible dynamic inventory
#   ./oci-inventory.sh --host <name>   # Host vars (returns {})
#   ./oci-inventory.sh                  # Pretty-print for debugging
###############################################################################

COMPARTMENT="${OCI_COMPARTMENT_OCID:-}"
SSH_KEY="${SSH_KEY_PATH:-$HOME/.ssh/codectl-bastion}"
SSH_USER="${SSH_USER:-ubuntu}"

if [[ -z "${COMPARTMENT}" ]]; then
    # Try sourcing from .env
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    ORACLE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
    ENV_FILE="${ORACLE_DIR}/.env"
    if [[ -f "${ENV_FILE}" ]]; then
        # shellcheck disable=SC1090
        source "${ENV_FILE}"
        COMPARTMENT="${OCI_COMPARTMENT_OCID:-}"
    fi
fi

if [[ -z "${COMPARTMENT}" ]]; then
    echo '{"_meta": {"hostvars": {}}}' >&2
    echo "ERROR: OCI_COMPARTMENT_OCID not set" >&2
    exit 1
fi

# ── Query OCI for all running instances ─────────────────────────────────────

get_instances() {
    oci compute instance list \
        --compartment-id "${COMPARTMENT}" \
        --lifecycle-state RUNNING \
        --query 'data[].{"name":"display-name","id":id,"shape":shape}' \
        --output json 2>/dev/null
}

get_public_ip() {
    local instance_id="$1"
    local vnic_id
    vnic_id=$(oci compute vnic-attachment list \
        --compartment-id "${COMPARTMENT}" \
        --instance-id "${instance_id}" \
        --query 'data[0]."vnic-id"' \
        --raw-output 2>/dev/null)
    if [[ -n "${vnic_id}" && "${vnic_id}" != "null" ]]; then
        oci network vnic get \
            --vnic-id "${vnic_id}" \
            --query 'data."public-ip"' \
            --raw-output 2>/dev/null
    fi
}

# ── Build inventory ─────────────────────────────────────────────────────────

build_inventory() {
    local instances
    instances=$(get_instances)

    local servers_hosts="{}"
    local agents_hosts="{}"
    local sentinels_hosts="{}"

    while IFS= read -r line; do
        local name id shape ip is_a1
        name=$(echo "${line}" | jq -r '.name')
        id=$(echo "${line}" | jq -r '.id')
        shape=$(echo "${line}" | jq -r '.shape')

        ip=$(get_public_ip "${id}")
        [[ -z "${ip}" || "${ip}" == "null" ]] && continue

        is_a1="false"
        [[ "${shape}" == *"A1"* ]] && is_a1="true"

        local host_vars
        host_vars=$(jq -n \
            --arg host "${ip}" \
            --arg user "${SSH_USER}" \
            --arg key "${SSH_KEY}" \
            --arg a1 "${is_a1}" \
            '{
                ansible_host: $host,
                ansible_user: $user,
                ansible_ssh_private_key_file: $key,
                oci_a1_instance: ($a1 == "true")
            }')

        if [[ "${name}" == *"server"* ]]; then
            servers_hosts=$(echo "${servers_hosts}" | jq --arg n "${name}" --argjson v "${host_vars}" '. + {($n): $v}')
        elif [[ "${name}" == *"agent"* ]]; then
            agents_hosts=$(echo "${agents_hosts}" | jq --arg n "${name}" --argjson v "${host_vars}" '. + {($n): $v}')
        elif [[ "${name}" == *"sentinel"* ]]; then
            sentinels_hosts=$(echo "${sentinels_hosts}" | jq --arg n "${name}" --argjson v "${host_vars}" '. + {($n): $v}')
        fi
    done < <(echo "${instances}" | jq -c '.[]')

    # Merge all hostvars for _meta
    local all_hostvars
    all_hostvars=$(echo "${servers_hosts}" "${agents_hosts}" "${sentinels_hosts}" | jq -s 'add')

    jq -n \
        --argjson servers "${servers_hosts}" \
        --argjson agents "${agents_hosts}" \
        --argjson sentinels "${sentinels_hosts}" \
        --argjson meta "${all_hostvars}" \
        '{
            "_meta": { "hostvars": $meta },
            "all": {
                "children": ["servers", "agents", "sentinels"]
            },
            "servers": {
                "hosts": ($servers | keys)
            },
            "agents": {
                "hosts": ($agents | keys)
            },
            "sentinels": {
                "hosts": ($sentinels | keys)
            }
        }'
}

# ── Main ────────────────────────────────────────────────────────────────────

case "${1:-}" in
    --list)
        build_inventory
        ;;
    --host)
        echo '{}'
        ;;
    *)
        echo "=== OCI Dynamic Inventory ===" >&2
        build_inventory | jq .
        ;;
esac
