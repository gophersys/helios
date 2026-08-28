#!/usr/bin/env bash
# scripts/clone_pilots.sh — Clone the 10 pilot KiCad projects
#
# Usage: bash scripts/clone_pilots.sh [data_dir]
#   data_dir defaults to ./data/raw

set -euo pipefail

DATA_DIR="${1:-./data/raw}"
mkdir -p "${DATA_DIR}"

info()  { echo "  [clone] $*"; }
ok()    { echo "  [clone] ✓ $*"; }
fail()  { echo "  [clone] ✗ $*" >&2; }

# Sparse-checkout patterns: only the KiCad artefacts the parser corpus needs.
sparse_patterns() {
  git sparse-checkout set --no-cone \
    '*.kicad_pro' '*.kicad_sch' '*.kicad_pcb' \
    '*.kicad_sym' '*.kicad_mod' \
    'sym-lib-table' 'fp-lib-table' \
    '*BOM*' '*bom*' '*.csv' \
    'README*' 'LICENSE*'
}

# clone_sparse <url> <name> <pinned-sha>
#
# Pinned by commit so the corpus — and therefore every parser assertion built on
# it — is reproducible. An unpinned `--depth 1` clone tracks upstream HEAD, which
# means an unrelated commit in someone else's repo can turn CI red overnight.
#
# Not every host serves an arbitrary SHA to `git fetch` (needs
# uploadpack.allowReachableSHA1InWant). GitHub does; if a host refuses we fall
# back to the default branch and say so loudly rather than failing the run.
clone_sparse() {
  local url="$1"
  local name="$2"
  local sha="${3:-}"
  local target="${DATA_DIR}/${name}"

  if [ -d "${target}" ]; then
    ok "${name} (already exists)"
    return
  fi

  info "Cloning ${name} @ ${sha:0:8} ..."
  mkdir -p "${target}"
  if (
    cd "${target}"
    git init -q
    git remote add origin "${url}"
    sparse_patterns
    git fetch -q --depth 1 --filter=blob:none origin "${sha}"
    git checkout -q FETCH_HEAD
  ) 2>/dev/null; then
    ok "${name} @ ${sha:0:8}"
    return
  fi

  fail "${name} — pinned fetch of ${sha:0:8} failed; falling back to default branch"
  rm -rf "${target}"
  if git clone --depth 1 --filter=blob:none --sparse "${url}" "${target}" 2>/dev/null; then
    ( cd "${target}" && sparse_patterns )
    ok "${name} (UNPINNED — corpus may drift)"
  else
    fail "${name} — clone failed"
    rm -rf "${target}"
  fi
}

# ── Pilot project list (10 designs) ──────────────────────────────────────────

# 1. Antmicro Jetson Nano baseboard — professional hierarchical design
clone_sparse "https://github.com/antmicro/jetson-nano-baseboard.git" \
  "antmicro__jetson-nano-baseboard" \
  "d8d0b2d71ab4cc4bcdb204a09f78be40d4c8cda3"

# 2. MNT Reform — full laptop, DDR routing, multi-board
clone_sparse "https://source.mnt.re/reform/reform.git" \
  "mnt__reform" \
  "2351811461980588eaa514b5c62d37dd120c10fa"

# 3. HackRF One — RF design, controlled impedance, NXP LPC4320
clone_sparse "https://github.com/greatscottgadgets/hackrf.git" \
  "greatscottgadgets__hackrf" \
  "7593b15dbd13bbabe2b70da3c0be6ecc5569f6bd"

# 4. VESC — STM32F4 + gate drivers, current sense, CAN
clone_sparse "https://github.com/vedderb/bldc-hardware.git" \
  "vedderb__bldc-hardware" \
  "f1c65014d0caab5d99d888fc3025377861ac6ae2"

# 5. Crazyflie — STM32F4 + nRF51 + BMI088 IMU + barometer
# (bitcraze/crazyflie2-pcb was removed upstream; crazyflie-electronics is the successor)
clone_sparse "https://github.com/bitcraze/crazyflie-electronics.git" \
  "bitcraze__crazyflie-electronics" \
  "5e8d0fcf343c9e1517c617a8fbd9576d63f45370"

# 6. Cicada-GSM-HW — STM32 + SIM7600 4G modem, production-ready
clone_sparse "https://github.com/EnAccess/Cicada-GSM-HW.git" \
  "enaccess__cicada-gsm-hw" \
  "0f1ba68ba68e41f9a1977870098035bdc323c194"

# 7. STM32F7 Flight Controller — ICM-42688-P IMU
clone_sparse "https://github.com/rishikesh2715/STM32F7_FC.git" \
  "rishikesh2715__stm32f7-fc" \
  "d4ca97b1bf5fdc8d47a9a60de4fc64e82bc521a9"

# 8. tokay-lite-pcb — ESP32-S3 + OV2640 camera
clone_sparse "https://github.com/maxlab-io/tokay-lite-pcb.git" \
  "maxlab-io__tokay-lite-pcb" \
  "fd04d94a332d745ad4c09e4e2da0fbb61fde3218"

# 9. LibreSolar MPPT-2420 — STM32G4 + DCDC, CAN, current sensing
clone_sparse "https://github.com/LibreSolar/mppt-2420-lc.git" \
  "libresolar__mppt-2420-lc" \
  "c2211beb366b2b2f91e949e676a9cac4f9a408d9"

# 10. nrfmicro — nRF52840 BLE, USB-C, LiPo
clone_sparse "https://github.com/joric/nrfmicro.git" \
  "joric__nrfmicro" \
  "5ac390d9d133e781a46a9c9fe43880f4826422e0"

# ── Extra projects referenced directly by the test suite ─────────────────────

# dumbpad — KiCad 9 format round-trip + 3D export tests
clone_sparse "https://github.com/imchipwood/dumbpad.git" \
  "imchipwood__dumbpad" \
  "6960351c3e9f74059a59c25cd0ddd309a0c939c0"

# VESC-controller — discovery/triage coverage (NOTE: its 20170922-format board
# does not load in kicad-cli 10; 3D-export tests use dumbpad instead)
clone_sparse "https://github.com/paltatech/VESC-controller.git" \
  "paltatech__VESC-controller" \
  "76e440e347b0bf61c334bc368dab6b8a2b2445ab"

# ── Summary ──────────────────────────────────────────────────────────────────
echo ""
info "Pilot projects cloned to ${DATA_DIR}/"
ls -1 "${DATA_DIR}/" | while read -r dir; do
  count=$(find "${DATA_DIR}/${dir}" -name "*.kicad_sch" -o -name "*.kicad_pcb" 2>/dev/null | wc -l)
  echo "  ${dir}: ${count} KiCad files"
done
