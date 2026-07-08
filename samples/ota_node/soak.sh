#!/usr/bin/env bash
# OTA soak: run N OTA cycles, each building a FRESH firmware (distinct version +
# banner + MCUboot sign-version), streaming it over cipher, and verifying via the
# UDP heartbeat that the node actually swapped to the new version. Records
# per-run metrics to JSONL for graphing. Proves the cipher OTA + MCUboot A/B swap
# is deterministic and repeatable (and degrades the flash in the process).
#
# DISK SAFETY (this once evicted the devbox pod via DiskPressure):
#   - a SINGLE build dir is reused every run (never accumulates)
#   - a hard guard aborts the soak if the devbox disk exceeds MAXDISK%
#   - an EXIT trap removes the build dir + staged files, even on interrupt
#
# Usage: soak.sh <count> [board] [node-dev] [node-ip]
set -u

N="${1:-100}"
BOARD="${2:-nucleo_h743zi}"
NODEDEV="${3:-0x000a}"
NODEIP="${4:-10.168.0.97}"

DEVBOX="dev@zephyr-zephyr-libs"
NODE="ubuntu@10.168.0.225"
SAMPLE="/workspace/ck-libs/cipher/samples/ota_node"
BUILD="/tmp/ota_soak_build"          # the ONE reused build dir
OVERLAY="/tmp/nuc_parts.overlay"
RESULTS="/tmp/ota_soak.jsonl"        # local, on this host
SIGNED="$BUILD/ota_node/zephyr/zephyr.signed.bin"
MAXDISK=83                           # abort if devbox / exceeds this %

ssh_dev()  { ssh -o BatchMode=yes -o ServerAliveInterval=10 -o ConnectTimeout=15 "$DEVBOX" "$@"; }
ssh_node() { ssh -o BatchMode=yes -o ConnectTimeout=15 "$NODE" "$@"; }
disk_pct() { ssh_dev "df --output=pcent / | tail -1 | tr -dc 0-9" 2>/dev/null; }

cleanup() {
  echo "cleanup: removing build dir + staged files"
  ssh_dev "rm -rf $BUILD /tmp/ota_soak_fw.bin" 2>/dev/null
  ssh_node "rm -f /tmp/ota_soak_fw.bin" 2>/dev/null
  rm -f /tmp/ota_soak_fw.bin 2>/dev/null
}
trap cleanup EXIT INT TERM

extra=""
[ "$BOARD" = "nucleo_h743zi" ] && extra="-Dmcuboot_EXTRA_DTC_OVERLAY_FILE=$OVERLAY"
# ESP32: large-app filler + its own device id (0x000C)
case "$BOARD" in esp32*) extra="-Dota_node_CONFIG_OTA_FILLER_KB=512 -Dota_node_CONFIG_CIPHER_DEVICE_ID=0xC";; esac

: > "$RESULTS"
# fresh ground truth: imgver history from prior soaks would false-positive verify
ssh_node "sudo -n truncate -s0 /tmp/ck-metrics.jsonl 2>/dev/null || true"
echo "soak: $N runs on $BOARD (dev $NODEDEV @ $NODEIP); disk guard @ ${MAXDISK}%"

ok_count=0; fail_count=0
for i in $(seq 2 $((N + 1))); do
  run=$((i - 1)); ver="v$i"; signver="$i.0.0"; ts=$(date +%s)

  # --- DISK GUARD: never push the devbox toward DiskPressure ---
  d=$(disk_pct); d=${d:-100}
  if [ "$d" -ge "$MAXDISK" ]; then
    echo "ABORT run $run: devbox disk at ${d}% >= ${MAXDISK}% — stopping to protect the cluster"
    echo "{\"run\":$run,\"stage\":\"disk_guard\",\"disk_pct\":$d,\"ok\":false}" >> "$RESULTS"
    break
  fi

  # 1. Fresh build in the reused dir (main.c recompiles for the new version).
  t0=$(date +%s.%N)
  ssh_dev "export ZEPHYR_BASE=/workspace/zephyr; cd $SAMPLE && \
    west build -b $BOARD --sysbuild -d $BUILD . -- \
    -Dota_node_OTA_VERSION=$ver $extra \
    -Dota_node_CONFIG_MCUBOOT_IMGTOOL_SIGN_VERSION='\"$signver\"' >/tmp/soak_build.log 2>&1"
  build_rc=$?
  build_s=$(awk "BEGIN{printf \"%.1f\", $(date +%s.%N)-$t0}")
  if [ $build_rc -ne 0 ]; then
    fail_count=$((fail_count+1))
    echo "{\"run\":$run,\"version\":\"$ver\",\"ts\":$ts,\"stage\":\"build\",\"ok\":false,\"build_s\":$build_s,\"disk_pct\":$d}" >> "$RESULTS"
    echo "run $run: BUILD FAILED (disk ${d}%)"; continue
  fi

  # 2. Stage the image on the node (via this host, which reaches both).
  scp -q "$DEVBOX:$SIGNED" /tmp/ota_soak_fw.bin 2>/dev/null
  fwsize=$(wc -c < /tmp/ota_soak_fw.bin 2>/dev/null || echo 0)
  scp -q /tmp/ota_soak_fw.bin "$NODE:/tmp/ota_soak_fw.bin" 2>/dev/null

  # 3. OTA it, with retries. Before each attempt, wait until the node is emitting
  #    FRESH heartbeats — streaming into a mid-swap-rebooting node races its
  #    teardown and can wedge it (found the hard way on run 3).
  t0=$(date +%s.%N); attempts=0
  for attempt in 1 2 3; do
    attempts=$attempt
    # event-driven gate: block until ONE fresh heartbeat arrives (node alive and
    # not mid-swap-reboot), returning the instant it lands — no polling.
    ssh_node "timeout 90 tail -n0 -F /tmp/ck-metrics.jsonl 2>/dev/null | grep --line-buffered -m1 ota_boot >/dev/null"
    out=$(ssh_node "timeout 90 /tmp/cipher-ota -host $NODEIP -node-dev $NODEDEV -firmware /tmp/ota_soak_fw.bin -chunk 1024 2>&1")
    echo "$out" | grep -q "OTA stream complete" && break
  done
  ota_s=$(awk "BEGIN{printf \"%.1f\", $(date +%s.%N)-$t0}")
  rate=$(echo "$out" | grep -oE "[0-9.]+ KiB/s" | head -1 | grep -oE "[0-9.]+")

  # 4. Verify the swap via the UDP heartbeat = ground-truth proof it booted.
  #    Check the MCUboot IMAGE VERSION (this run signs image i.0.0), which is the
  #    field the OTA actually bumps and MCUboot swaps on.
  want_ver="$i.0.0"
  # event-driven verify: returns the instant the new image heartbeats after the
  # swap + reboot + WiFi rejoin (covers history too, in case it already booted).
  swap_ok=false
  if ssh_node "grep -q '\"imgver\":\"$want_ver\"' /tmp/ck-metrics.jsonl 2>/dev/null || \
      timeout 150 tail -n0 -F /tmp/ck-metrics.jsonl 2>/dev/null | grep --line-buffered -m1 '\"imgver\":\"$want_ver\"' >/dev/null"; then
    swap_ok=true
  fi
  sink=$(ssh_node "grep '\"phase\":\"end\"' /tmp/ck-metrics.jsonl 2>/dev/null | tail -1")
  csum=$(echo "$sink" | grep -oE '"csum_ok":(true|false)' | cut -d: -f2)

  if [ "$swap_ok" = true ]; then ok_count=$((ok_count+1)); else fail_count=$((fail_count+1)); fi
  echo "{\"run\":$run,\"version\":\"$ver\",\"ts\":$ts,\"build_s\":$build_s,\"fw_bytes\":$fwsize,\"ota_s\":$ota_s,\"kib_s\":${rate:-0},\"ota_attempts\":$attempts,\"csum_ok\":${csum:-false},\"swap_ok\":$swap_ok,\"flash_writes\":$run,\"disk_pct\":$d}" >> "$RESULTS"
  echo "run $run/$N ver=$ver build=${build_s}s ota=${ota_s}s ${rate:-?}KiB/s csum=${csum:-?} swap=$swap_ok disk=${d}% [$ok_count ok/$fail_count fail]"
done

echo "SOAK DONE: $ok_count ok, $fail_count fail. results -> $RESULTS"
# cleanup() runs on EXIT
