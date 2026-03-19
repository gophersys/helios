#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# agent01-autoscaler.sh — Sleep/wake the paid x86 node (agent-01) on demand
#
# agent-01 is an OCI E4.Flex (~$14/mo) used exclusively for IB Gateway.
# When IB Gateway isn't deployed, agent-01 should sleep to save money.
#
# Usage:
#   agent01-autoscaler.sh wake       # Start agent-01, wait for K3s Ready
#   agent01-autoscaler.sh sleep      # Cordon, drain, stop agent-01
#   agent01-autoscaler.sh status     # Check current state
#   agent01-autoscaler.sh auto       # Wake if ibgateway needed, sleep if not
#
# This script can be called from a CronJob or manually.
#
# Prerequisites:
#   - OCI CLI configured (~/.oci/config)
#   - kubectl access to the cluster
#   - OCI_COMPARTMENT_OCID set (or sourced from .env / Bitwarden)
###############################################################################

INSTANCE_OCID="ocid1.instance.oc1.phx.anyhqljtslzce6actpj53hffsoo5o5vciq4h2eo3gnyqgs5ek5zomhd2wttq"
NODE_NAME="agent-01"
K3S_LABEL="node-role.kubernetes.io/ibgateway=true"

export SUPPRESS_LABEL_WARNING=True

# ── helpers ───────────────────────────────────────────────────────────────────
log()  { echo "[autoscaler] $(date +%H:%M:%S) $*"; }
err()  { echo "[autoscaler] $(date +%H:%M:%S) ERROR: $*" >&2; }

get_instance_state() {
  oci compute instance get --instance-id "${INSTANCE_OCID}" \
    --query 'data."lifecycle-state"' --raw-output 2>/dev/null
}

wait_for_state() {
  local target="$1" timeout="${2:-300}" elapsed=0
  while [ $elapsed -lt $timeout ]; do
    local state
    state=$(get_instance_state)
    [ "$state" = "$target" ] && return 0
    sleep 10
    elapsed=$((elapsed + 10))
    log "  waiting for ${target}... (${state}, ${elapsed}s)"
  done
  err "Timeout waiting for ${target} (current: $(get_instance_state))"
  return 1
}

wait_for_node_ready() {
  local timeout="${1:-180}" elapsed=0
  while [ $elapsed -lt $timeout ]; do
    local status
    status=$(kubectl get node "${NODE_NAME}" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || echo "NotFound")
    [ "$status" = "True" ] && return 0
    sleep 10
    elapsed=$((elapsed + 10))
    log "  waiting for node Ready... (${status}, ${elapsed}s)"
  done
  err "Timeout waiting for node Ready"
  return 1
}

# ── commands ──────────────────────────────────────────────────────────────────

cmd_status() {
  local state
  state=$(get_instance_state)
  log "agent-01 instance: ${state}"

  if [ "$state" = "RUNNING" ]; then
    local node_status
    node_status=$(kubectl get node "${NODE_NAME}" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || echo "not in cluster")
    log "agent-01 K3s node: Ready=${node_status}"
  fi

  # Check if IB Gateway is deployed
  local ibgw
  ibgw=$(kubectl get deployment ibgateway -n fintel-staging --no-headers 2>/dev/null || echo "")
  if [ -n "$ibgw" ]; then
    log "IB Gateway: deployed ($(echo "$ibgw" | awk '{print $2}') ready)"
  else
    log "IB Gateway: not deployed"
  fi
}

cmd_wake() {
  local state
  state=$(get_instance_state)

  if [ "$state" = "RUNNING" ]; then
    log "agent-01 already running"
    wait_for_node_ready 60 || true
    # Uncordon in case it was cordoned
    kubectl uncordon "${NODE_NAME}" 2>/dev/null || true
    return 0
  fi

  if [ "$state" != "STOPPED" ]; then
    err "agent-01 is in state ${state} — can only wake from STOPPED"
    return 1
  fi

  log "Starting agent-01..."
  oci compute instance action --instance-id "${INSTANCE_OCID}" --action START --query 'data."lifecycle-state"' --raw-output 2>/dev/null
  wait_for_state "RUNNING" 300

  log "Waiting for K3s node to rejoin..."
  wait_for_node_ready 180

  kubectl uncordon "${NODE_NAME}" 2>/dev/null || true
  log "agent-01 is awake and Ready"
}

cmd_sleep() {
  local state
  state=$(get_instance_state)

  if [ "$state" = "STOPPED" ]; then
    log "agent-01 already stopped"
    return 0
  fi

  if [ "$state" != "RUNNING" ]; then
    err "agent-01 is in state ${state} — can only sleep from RUNNING"
    return 1
  fi

  # Check if IB Gateway is running — refuse to sleep if so
  local ibgw
  ibgw=$(kubectl get deployment ibgateway -n fintel-staging --no-headers 2>/dev/null || echo "")
  if [ -n "$ibgw" ]; then
    local ready
    ready=$(echo "$ibgw" | awk '{print $2}')
    if [ "$ready" != "0/0" ]; then
      err "IB Gateway is still running (${ready}). Scale down first or use --force"
      if [ "${2:-}" != "--force" ]; then
        return 1
      fi
    fi
  fi

  log "Cordoning agent-01..."
  kubectl cordon "${NODE_NAME}" 2>/dev/null || true

  log "Draining agent-01..."
  kubectl drain "${NODE_NAME}" --ignore-daemonsets --delete-emptydir-data --force --timeout=60s 2>/dev/null || true

  log "Stopping agent-01..."
  oci compute instance action --instance-id "${INSTANCE_OCID}" --action STOP --query 'data."lifecycle-state"' --raw-output 2>/dev/null
  wait_for_state "STOPPED" 300

  log "agent-01 is asleep ($0/hr)"
}

cmd_auto() {
  # Auto-detect: if IB Gateway is deployed, wake. Otherwise, sleep.
  local ibgw
  ibgw=$(kubectl get deployment ibgateway -n fintel-staging --no-headers 2>/dev/null || echo "")

  if [ -n "$ibgw" ]; then
    local desired
    desired=$(echo "$ibgw" | awk '{print $2}' | cut -d/ -f2)
    if [ "${desired:-0}" -gt 0 ]; then
      log "IB Gateway wants ${desired} replicas — waking agent-01"
      cmd_wake
      return
    fi
  fi

  log "No IB Gateway demand — sleeping agent-01"
  cmd_sleep
}

# ── dispatch ──────────────────────────────────────────────────────────────────
case "${1:-}" in
  wake|start|up)     cmd_wake   ;;
  sleep|stop|down)   cmd_sleep  ;;
  status)            cmd_status ;;
  auto)              cmd_auto   ;;
  *)
    echo "Usage: $0 {wake|sleep|status|auto}"
    echo ""
    echo "  wake    Start agent-01 and wait for K3s Ready"
    echo "  sleep   Cordon, drain, and stop agent-01"
    echo "  status  Check current state"
    echo "  auto    Wake if IB Gateway deployed, sleep if not"
    exit 1
    ;;
esac
