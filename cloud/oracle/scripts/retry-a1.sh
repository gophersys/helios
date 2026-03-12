#!/usr/bin/env bash
set -uo pipefail

# retry-a1.sh — Acquire A1.Flex (Ampere) instances across OCI North American regions
#
# Uses the OCI CLI directly (no terraform dependency) to cycle through regions
# and availability domains until capacity is found. Sends a Discord webhook
# notification on success with region, AD, timestamp, and instance details.
#
# Node layout target:
#   server-00    K3s control plane
#   agent-00     K3s worker (ARM)
#
# Usage:
#   ./retry-a1.sh [options]
#
# Options:
#   --duration <hours>      How long to retry (default: 168 = 1 week)
#   --interval <seconds>    Pause between attempts (default: 60)
#   --webhook <url>         Discord webhook URL for notifications
#   --compartment <ocid>    OCI compartment OCID (or set OCI_COMPARTMENT_OCID)
#   --ssh-key <path>        SSH public key file to inject (or set SSH_PUBLIC_KEY_PATH)
#   --ocpus <n>             OCPUs per instance (default: 2)
#   --memory <gb>           Memory per instance in GB (default: 12)
#   --boot-volume <gb>      Boot volume size in GB (default: 50)
#   --server-only           Only create the server instance (skip agent)
#   --dry-run               Show what would be done without launching
#
# Required env vars (from .env):
#   OCI_COMPARTMENT_OCID   — target compartment
#
# The OCI CLI must be configured (~/.oci/config).

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ORACLE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# ── defaults ────────────────────────────────────────────────────────────────
DURATION_HOURS=168          # 1 week
INTERVAL=60                 # seconds between attempts
DISCORD_WEBHOOK=""
COMPARTMENT_OCID="${OCI_COMPARTMENT_OCID:-}"
SSH_KEY_PATH="${SSH_PUBLIC_KEY_PATH:-${ORACLE_DIR}/terraform/codectl-key.pub}"
OCPUS=2
MEMORY_GB=12
BOOT_VOLUME_GB=50
SERVER_ONLY=false
DRY_RUN=false

# North American regions — preferred order (PHX first)
NA_REGIONS_PREFERRED=(
  "us-phoenix-1"
  "us-ashburn-1"
  "us-chicago-1"
  "us-sanjose-1"
  "ca-toronto-1"
  "ca-montreal-1"
)

# ── helpers ─────────────────────────────────────────────────────────────────
info()  { echo "  [retry] $(date '+%Y-%m-%d %H:%M:%S') $*"; }
ok()    { echo "  [retry] $(date '+%Y-%m-%d %H:%M:%S') $*"; }
warn()  { echo "  [retry] $(date '+%Y-%m-%d %H:%M:%S') ! $*"; }
die()   { echo "  [retry] $(date '+%Y-%m-%d %H:%M:%S') $*" >&2; exit 1; }

# ── parse args ──────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --duration)     DURATION_HOURS="$2"; shift 2 ;;
    --interval)     INTERVAL="$2"; shift 2 ;;
    --webhook)      DISCORD_WEBHOOK="$2"; shift 2 ;;
    --compartment)  COMPARTMENT_OCID="$2"; shift 2 ;;
    --ssh-key)      SSH_KEY_PATH="$2"; shift 2 ;;
    --ocpus)        OCPUS="$2"; shift 2 ;;
    --memory)       MEMORY_GB="$2"; shift 2 ;;
    --boot-volume)  BOOT_VOLUME_GB="$2"; shift 2 ;;
    --server-only)  SERVER_ONLY=true; shift ;;
    --dry-run)      DRY_RUN=true; shift ;;
    *)              die "Unknown option: $1" ;;
  esac
done

# ── validation ──────────────────────────────────────────────────────────────
command -v oci > /dev/null 2>&1 || die "OCI CLI not found — install with: pip3 install oci-cli"
command -v jq > /dev/null 2>&1  || die "jq not found"
[ -n "${COMPARTMENT_OCID}" ]    || die "Set OCI_COMPARTMENT_OCID env var or pass --compartment"
[ -f "${SSH_KEY_PATH}" ]        || die "SSH public key not found at ${SSH_KEY_PATH}"

SSH_PUBLIC_KEY=$(cat "${SSH_KEY_PATH}")
MAX_ATTEMPTS=$(( DURATION_HOURS * 3600 / INTERVAL ))

# ── Detect subscribed regions ───────────────────────────────────────────────
info "Detecting subscribed OCI regions..."
TENANCY_OCID=$(grep "tenancy=" ~/.oci/config | head -1 | cut -d= -f2)
subscribed_raw=$(oci iam region-subscription list \
  --tenancy-id "${TENANCY_OCID}" \
  2>/dev/null | jq -r '.data[]."region-name"')

NA_REGIONS=()
for region in "${NA_REGIONS_PREFERRED[@]}"; do
  if echo "${subscribed_raw}" | grep -qx "${region}"; then
    NA_REGIONS+=("${region}")
  fi
done

if [ ${#NA_REGIONS[@]} -eq 0 ]; then
  die "No subscribed NA regions found. Subscribe to regions at: OCI Console -> Identity -> Region Management"
fi

if [ ${#NA_REGIONS[@]} -lt ${#NA_REGIONS_PREFERRED[@]} ]; then
  not_subscribed=()
  for region in "${NA_REGIONS_PREFERRED[@]}"; do
    if ! echo "${subscribed_raw}" | grep -qx "${region}"; then
      not_subscribed+=("${region}")
    fi
  done
  warn "Not subscribed to: ${not_subscribed[*]}"
  info "Subscribe at: OCI Console -> Identity -> Region Management (free, takes ~1 min)"
fi

info "Starting A1.Flex multi-region retry"
info "Duration: ${DURATION_HOURS}h (${MAX_ATTEMPTS} attempts at ${INTERVAL}s intervals)"
info "Subscribed NA regions: ${NA_REGIONS[*]}"
info "Shape: VM.Standard.A1.Flex — ${OCPUS} OCPU / ${MEMORY_GB} GB"
info "Compartment: ${COMPARTMENT_OCID}"
[ -n "${DISCORD_WEBHOOK}" ] && info "Discord notifications: enabled"
[ "${DRY_RUN}" = true ] && info "DRY RUN — no instances will be created"
echo ""

# ── Discord notification ────────────────────────────────────────────────────
send_discord() {
  local message="$1"
  if [ -n "${DISCORD_WEBHOOK}" ]; then
    curl -sS -H "Content-Type: application/json" \
      -d "{\"content\": $(jq -Rs . <<< "${message}")}" \
      "${DISCORD_WEBHOOK}" > /dev/null 2>&1 || warn "Discord notification failed"
  fi
}

# ── Find or create VCN + subnet in a region ─────────────────────────────────
ensure_network() {
  local region="$1"

  # Check for existing VCN tagged with our project
  local vcn_id
  vcn_id=$(oci network vcn list \
    --compartment-id "${COMPARTMENT_OCID}" \
    --region "${region}" \
    --display-name "infra-retry-vcn" \
    --lifecycle-state AVAILABLE \
    2>/dev/null | jq -r '.data[0].id // empty')

  if [ -n "${vcn_id}" ]; then
    # Find the subnet in this VCN
    local subnet_id
    subnet_id=$(oci network subnet list \
      --compartment-id "${COMPARTMENT_OCID}" \
      --vcn-id "${vcn_id}" \
      --region "${region}" \
      --display-name "infra-retry-subnet" \
      --lifecycle-state AVAILABLE \
      2>/dev/null | jq -r '.data[0].id // empty')

    if [ -n "${subnet_id}" ]; then
      echo "${subnet_id}"
      return 0
    fi
  fi

  # Create VCN
  info "Creating VCN in ${region}..."
  vcn_id=$(oci network vcn create \
    --compartment-id "${COMPARTMENT_OCID}" \
    --region "${region}" \
    --display-name "infra-retry-vcn" \
    --cidr-blocks '["10.0.0.0/16"]' \
    --dns-label "infra" \
    --freeform-tags '{"project":"infrastructure","managed-by":"retry-a1"}' \
    --wait-for-state AVAILABLE \
    --wait-interval-seconds 5 \
    2>/dev/null | jq -r '.data.id // empty')

  [ -z "${vcn_id}" ] && { warn "Failed to create VCN in ${region}"; return 1; }

  # Create internet gateway
  local igw_id
  igw_id=$(oci network internet-gateway create \
    --compartment-id "${COMPARTMENT_OCID}" \
    --vcn-id "${vcn_id}" \
    --region "${region}" \
    --display-name "infra-retry-igw" \
    --is-enabled true \
    --wait-for-state AVAILABLE \
    --wait-interval-seconds 5 \
    2>/dev/null | jq -r '.data.id // empty')

  [ -z "${igw_id}" ] && { warn "Failed to create IGW in ${region}"; return 1; }

  # Get the default route table
  local rt_id
  rt_id=$(oci network route-table list \
    --compartment-id "${COMPARTMENT_OCID}" \
    --vcn-id "${vcn_id}" \
    --region "${region}" \
    2>/dev/null | jq -r '.data[0].id // empty')

  # Add default route via IGW
  oci network route-table update \
    --rt-id "${rt_id}" \
    --region "${region}" \
    --route-rules "[{\"destination\":\"0.0.0.0/0\",\"destinationType\":\"CIDR_BLOCK\",\"networkEntityId\":\"${igw_id}\"}]" \
    --force \
    2>/dev/null > /dev/null

  # Create security list allowing SSH + all egress
  local sl_id
  sl_id=$(oci network security-list list \
    --compartment-id "${COMPARTMENT_OCID}" \
    --vcn-id "${vcn_id}" \
    --region "${region}" \
    2>/dev/null | jq -r '.data[0].id // empty')

  oci network security-list update \
    --security-list-id "${sl_id}" \
    --region "${region}" \
    --ingress-security-rules '[{"protocol":"6","source":"0.0.0.0/0","tcpOptions":{"destinationPortRange":{"min":22,"max":22}}}]' \
    --egress-security-rules '[{"protocol":"all","destination":"0.0.0.0/0"}]' \
    --force \
    2>/dev/null > /dev/null

  # Create subnet
  local subnet_id
  subnet_id=$(oci network subnet create \
    --compartment-id "${COMPARTMENT_OCID}" \
    --vcn-id "${vcn_id}" \
    --region "${region}" \
    --display-name "infra-retry-subnet" \
    --cidr-block "10.0.1.0/24" \
    --dns-label "retry" \
    --freeform-tags '{"project":"infrastructure","managed-by":"retry-a1"}' \
    --wait-for-state AVAILABLE \
    --wait-interval-seconds 5 \
    2>/dev/null | jq -r '.data.id // empty')

  [ -z "${subnet_id}" ] && { warn "Failed to create subnet in ${region}"; return 1; }
  ok "Network ready in ${region} (VCN: ${vcn_id})"
  echo "${subnet_id}"
}

# ── Find latest Ubuntu ARM64 image ──────────────────────────────────────────
find_arm64_image() {
  local region="$1"
  oci compute image list \
    --compartment-id "${COMPARTMENT_OCID}" \
    --region "${region}" \
    --operating-system "Canonical Ubuntu" \
    --operating-system-version "22.04" \
    --shape "VM.Standard.A1.Flex" \
    --sort-by TIMECREATED \
    --sort-order DESC \
    --limit 1 \
    2>/dev/null | jq -r '.data[0].id // empty'
}

# ── List availability domains ───────────────────────────────────────────────
list_ads() {
  local region="$1"
  oci iam availability-domain list \
    --compartment-id "${COMPARTMENT_OCID}" \
    --region "${region}" \
    2>/dev/null | jq -r '.data[].name'
}

# ── Launch a single A1.Flex instance ────────────────────────────────────────
launch_instance() {
  local region="$1" ad_name="$2" subnet_id="$3" image_id="$4" display_name="$5"

  if [ "${DRY_RUN}" = true ]; then
    info "[dry-run] Would launch ${display_name} in ${region} / ${ad_name}"
    return 1  # pretend failure so loop continues
  fi

  local output
  output=$(oci compute instance launch \
    --compartment-id "${COMPARTMENT_OCID}" \
    --availability-domain "${ad_name}" \
    --region "${region}" \
    --display-name "${display_name}" \
    --shape "VM.Standard.A1.Flex" \
    --shape-config "{\"ocpus\": ${OCPUS}, \"memoryInGBs\": ${MEMORY_GB}}" \
    --image-id "${image_id}" \
    --subnet-id "${subnet_id}" \
    --assign-public-ip true \
    --boot-volume-size-in-gbs "${BOOT_VOLUME_GB}" \
    --ssh-authorized-keys-file "${SSH_KEY_PATH}" \
    --freeform-tags '{"project":"infrastructure","managed-by":"retry-a1"}' \
    --wait-for-state RUNNING \
    --wait-interval-seconds 10 \
    --max-wait-seconds 600 \
    2>&1)

  local exit_code=$?

  if [ ${exit_code} -eq 0 ]; then
    # Extract instance details
    local instance_id public_ip
    instance_id=$(echo "${output}" | jq -r '.data.id // empty' 2>/dev/null)
    public_ip=$(oci compute instance list-vnics \
      --instance-id "${instance_id}" \
      --region "${region}" \
      2>/dev/null | jq -r '.data[0]."public-ip" // "pending"')

    echo "${instance_id}|${public_ip}"
    return 0
  fi

  if echo "${output}" | grep -qi "out of.*capacity\|capacity.*constraint\|InternalError\|LimitExceeded"; then
    return 1  # expected — no capacity
  fi

  # Unexpected error — dump for debugging
  warn "Unexpected error launching ${display_name}:"
  echo "${output}" | tail -5
  return 1
}

# ── Main retry loop ─────────────────────────────────────────────────────────
attempt=0
num_regions=${#NA_REGIONS[@]}
start_time=$(date +%s)

# Notify start
send_discord "A1.Flex Retry Started
> Regions: ${NA_REGIONS[*]}
> Shape: ${OCPUS} OCPU / ${MEMORY_GB} GB
> Duration: ${DURATION_HOURS}h (${MAX_ATTEMPTS} attempts)
> Started: $(date '+%Y-%m-%d %H:%M:%S %Z')"

while [ "${attempt}" -lt "${MAX_ATTEMPTS}" ]; do
  attempt=$(( attempt + 1 ))
  region_index=$(( (attempt - 1) % num_regions ))
  region="${NA_REGIONS[${region_index}]}"

  # Get ADs for this region
  ads_raw=$(list_ads "${region}" 2>/dev/null)
  if [ -z "${ads_raw}" ]; then
    warn "Cannot list ADs in ${region} — skipping"
    sleep "${INTERVAL}"
    continue
  fi

  mapfile -t ads <<< "${ads_raw}"
  ad_index=$(( (attempt - 1) / num_regions % ${#ads[@]} ))
  ad_name="${ads[${ad_index}]}"

  info "Attempt ${attempt}/${MAX_ATTEMPTS} — ${region} / ${ad_name}"

  # Find ARM64 image (cached per region in the loop naturally)
  image_id=$(find_arm64_image "${region}")
  if [ -z "${image_id}" ]; then
    warn "No Ubuntu ARM64 image in ${region} — skipping"
    sleep "${INTERVAL}"
    continue
  fi

  # Ensure network exists
  subnet_id=$(ensure_network "${region}")
  if [ -z "${subnet_id}" ]; then
    warn "Network setup failed in ${region} — skipping"
    sleep "${INTERVAL}"
    continue
  fi

  # Try launching server
  result=$(launch_instance "${region}" "${ad_name}" "${subnet_id}" "${image_id}" "server-00")
  launch_exit=$?
  if [ ${launch_exit} -eq 0 ] && [ -n "${result}" ]; then
    server_id="${result%%|*}"
    server_ip="${result##*|}"

    echo ""
    ok "============================================"
    ok "  A1 SERVER ACQUIRED ON ATTEMPT ${attempt}"
    ok "  Region: ${region}"
    ok "  AD:     ${ad_name}"
    ok "  IP:     ${server_ip}"
    ok "  Time:   $(date '+%Y-%m-%d %H:%M:%S %Z')"
    ok "============================================"
    echo ""

    elapsed=$(( $(date +%s) - start_time ))
    elapsed_human="$(( elapsed / 3600 ))h $(( (elapsed % 3600) / 60 ))m"

    # Try agent if not server-only
    agent_msg=""
    if [ "${SERVER_ONLY}" = false ]; then
      info "Launching agent-00 in same region/AD..."
      agent_result=$(launch_instance "${region}" "${ad_name}" "${subnet_id}" "${image_id}" "agent-00")
      if [ $? -eq 0 ] && [ -n "${agent_result}" ]; then
        agent_ip="${agent_result##*|}"
        ok "Agent acquired — IP: ${agent_ip}"
        agent_msg="
> **Agent (agent-00):** \`${agent_ip}\`"
      else
        warn "Agent launch failed — server is up, agent will need manual retry"
        agent_msg="
> **Agent (agent-00):** failed (retry manually in same region/AD)"
      fi
    fi

    # Discord notification with details
    send_discord "A1.Flex Instances Acquired!

> **Region:** \`${region}\`
> **AD:** \`${ad_name}\`
> **Server (server-00):** \`${server_ip}\`${agent_msg}

> **When:** $(date '+%Y-%m-%d %H:%M:%S %Z')
> **After:** ${elapsed_human} (attempt ${attempt})
> **Shape:** ${OCPUS} OCPU / ${MEMORY_GB} GB RAM

SSH: \`ssh -i codectl-key.pem ubuntu@${server_ip}\`"

    exit 0
  else
    info "No capacity in ${region} / ${ad_name} — sleeping ${INTERVAL}s..."
  fi

  # Progress update every 100 attempts
  if [ $(( attempt % 100 )) -eq 0 ]; then
    elapsed=$(( $(date +%s) - start_time ))
    elapsed_human="$(( elapsed / 3600 ))h $(( (elapsed % 3600) / 60 ))m"
    info "Progress: ${attempt}/${MAX_ATTEMPTS} attempts — ${elapsed_human} elapsed"
    send_discord "A1 Retry Progress
> Attempt ${attempt}/${MAX_ATTEMPTS} — ${elapsed_human} elapsed
> Last tried: ${region} / ${ad_name}
> Still hunting..."
  fi

  sleep "${INTERVAL}"
done

# Exhausted all attempts
elapsed=$(( $(date +%s) - start_time ))
elapsed_human="$(( elapsed / 3600 ))h $(( (elapsed % 3600) / 60 ))m"

send_discord "A1.Flex Retry Exhausted
> Ran for ${elapsed_human} (${MAX_ATTEMPTS} attempts)
> Regions tried: ${NA_REGIONS[*]}
> No capacity found. Consider trying a different approach."

die "Exhausted ${MAX_ATTEMPTS} attempts over ${DURATION_HOURS} hours across ${num_regions} NA regions."
