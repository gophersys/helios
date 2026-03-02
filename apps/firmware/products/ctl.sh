#!/usr/bin/env bash
set -euo pipefail

# ───────────────────────────────────────────────────────────────
# Firmware Build Controller
# ───────────────────────────────────────────────────────────────
# Docker-based firmware build orchestrator. Uses each firmware
# submodule's own .devcontainer Docker image to guarantee the
# correct NCS toolchain version.
#
# Usage:
#   ./apps/firmware/products/ctl.sh <command> <product> [options]
#
# Commands:
#   build <product>       Build firmware in Docker
#   build-all <product>   Build all variant/revision combinations
#   collect <product>     Copy artifacts to validation assets dir
#   clean <product>       Remove build dirs + artifacts
#   artifacts <product>   List built artifacts
#   help                  Show usage
# ───────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

log()  { echo -e "${GREEN}[firmware]${NC} $*"; }
warn() { echo -e "${YELLOW}[firmware]${NC} $*"; }
err()  { echo -e "${RED}[firmware]${NC} $*" >&2; }
info() { echo -e "${CYAN}[firmware]${NC} $*"; }

# ─── Registry CA Certs ───────────────────────────────────────
# Firmware Docker images are hosted on the CoreKinect internal
# registry (HTTPS with internal CA). Ensure the CA is trusted
# before any docker pull/run operations.

ensure_registry_certs() {
  local registry="containers.ad.corekinect.com"

  # Quick check: can we reach the registry?
  if curl -sf --connect-timeout 3 "https://${registry}/v2/" >/dev/null 2>&1; then
    return 0
  fi

  # Check if the devcontainer ctl.sh already installed them
  if [[ -d "/usr/local/share/ca-certificates/corekinect" ]] && \
     [[ -n "$(ls -A /usr/local/share/ca-certificates/corekinect 2>/dev/null)" ]]; then
    update-ca-certificates >/dev/null 2>&1 || true
    return 0
  fi

  # Fall back to extracting from the live TLS handshake
  if ! command -v openssl &>/dev/null; then
    warn "openssl not available — cannot auto-install registry CA certs"
    warn "Docker pulls from ${registry} may fail"
    return 0
  fi

  if ! openssl s_client -connect "${registry}:443" </dev/null >/dev/null 2>&1; then
    warn "Cannot reach ${registry}:443 — skipping CA install"
    return 0
  fi

  log "Installing CoreKinect registry CA certificates..."

  local cert_dir="/usr/local/share/ca-certificates/corekinect"
  mkdir -p "$cert_dir"

  local chain_pem
  chain_pem="$(openssl s_client -showcerts -connect "${registry}:443" \
    -servername "${registry}" </dev/null 2>/dev/null)"

  local cert_index=0
  local in_cert=false
  local current_cert=""

  while IFS= read -r line; do
    if [[ "$line" == "-----BEGIN CERTIFICATE-----" ]]; then
      in_cert=true
      current_cert="$line"$'\n'
    elif [[ "$line" == "-----END CERTIFICATE-----" ]]; then
      current_cert+="$line"$'\n'
      in_cert=false
      cert_index=$((cert_index + 1))
      if [[ $cert_index -gt 1 ]]; then
        local subject
        subject="$(echo "$current_cert" | openssl x509 -noout -subject 2>/dev/null | sed 's/.*CN = //')"
        echo "$current_cert" > "${cert_dir}/${subject// /_}.crt"
      fi
    elif [[ "$in_cert" == "true" ]]; then
      current_cert+="$line"$'\n'
    fi
  done <<< "$chain_pem"

  update-ca-certificates >/dev/null 2>&1 || true
  log "Registry CA certificates installed"
}

# ─── Helpers ─────────────────────────────────────────────────

resolve_product_dir() {
  local product="$1"
  local product_dir="${SCRIPT_DIR}/${product}"

  if [[ ! -d "$product_dir" ]]; then
    err "Product not found: ${product}"
    err "Available products:"
    for d in "${SCRIPT_DIR}"/*/; do
      if [[ -f "${d}project.json" ]]; then
        echo "  $(basename "$d")"
      fi
    done
    exit 1
  fi

  if [[ ! -f "${product_dir}/project.json" ]]; then
    err "Not a valid product directory (missing project.json): ${product_dir}"
    exit 1
  fi

  echo "$product_dir"
}

# Extract Docker image from a firmware submodule's devcontainer.json.
# Handles JSONC (JSON with comments) by stripping // comments before jq.
resolve_docker_image() {
  local fw_dir="$1"
  local devcontainer="${fw_dir}/.devcontainer/devcontainer.json"

  if [[ ! -f "$devcontainer" ]]; then
    err "No .devcontainer/devcontainer.json found in: ${fw_dir}"
    err "Cannot determine Docker image for build."
    exit 1
  fi

  # Strip JSONC comments, then extract image field
  local image
  image=$(sed 's|//.*$||' "$devcontainer" | jq -r '.image')

  if [[ -z "$image" || "$image" == "null" ]]; then
    err "No 'image' field found in: ${devcontainer}"
    exit 1
  fi

  echo "$image"
}

# Map target (app/mfg) to the firmware submodule directory name
resolve_fw_submodule() {
  local product="$1"
  local target="$2"

  case "$target" in
    app) echo "${product}_fw" ;;
    mfg) echo "${product}_mfg_fw" ;;
    *)
      err "Invalid target: ${target} (expected: app or mfg)"
      exit 1
      ;;
  esac
}

# ─── Encryption Key Helpers ───────────────────────────────────
#
# MCUboot firmware images require ECDSA-P256 encryption keys. The submodule
# repos .gitignore these (correctly — secrets), so they must be generated
# once per developer/CI environment.
#
# The submodule sysbuild.conf files also hardcode paths from standalone
# development (/workspaces/<submodule>/). In the monorepo, the mount layout
# is /workspaces/<product>/<submodule>/, so the paths must be fixed at build
# time. build.sh already fixes the comms processor path; ctl.sh fixes the
# app processor path since that fix can't go in the submodule's build.sh.

_ensure_encryption_keys() {
  local product_dir="$1"
  local fw_submodule="$2"
  local docker_image="${3:-}"
  local host_fw_dir="${4:-}"

  local fw_dir="${product_dir}/${fw_submodule}"
  local keys=("encryption_key.pem" "comms_encryption_key.pem")
  local missing=()

  for key in "${keys[@]}"; do
    [[ -f "${fw_dir}/${key}" ]] || missing+=("$key")
  done

  [[ ${#missing[@]} -eq 0 ]] && return 0

  log "Generating ${#missing[@]} missing encryption key(s) in ${fw_submodule}/..."

  if [[ -n "$docker_image" && -n "$host_fw_dir" ]]; then
    # Docker mode: use imgtool.py from the NCS container
    for key in "${missing[@]}"; do
      info "  ${key} (ecdsa-p256 via imgtool in Docker)..."
      docker run --rm \
        -v "${host_fw_dir}:/workspaces/fw" \
        -w "/workspaces/fw" \
        "${docker_image}" \
        python3 /workdir/bootloader/mcuboot/scripts/imgtool.py \
          keygen -k "/workspaces/fw/${key}" -t ecdsa-p256
    done
  else
    # Local mode: try imgtool.py directly (available inside NCS devcontainers)
    local imgtool="/workdir/bootloader/mcuboot/scripts/imgtool.py"
    if [[ -f "$imgtool" ]]; then
      for key in "${missing[@]}"; do
        info "  ${key} (ecdsa-p256 via local imgtool)..."
        python3 "$imgtool" keygen -k "${fw_dir}/${key}" -t ecdsa-p256
      done
    else
      err "Missing encryption keys in ${fw_submodule}/ and imgtool.py not found."
      err "Keys needed: ${missing[*]}"
      err "Generate inside the NCS Docker container:"
      for key in "${missing[@]}"; do
        err "  /workdir/bootloader/mcuboot/scripts/imgtool.py keygen -k <fw_dir>/${key} -t ecdsa-p256"
      done
      err "Or run the build in Docker mode (without --no-docker) to auto-generate."
      exit 1
    fi
  fi

  log "Encryption keys generated. These persist across builds (in .gitignore)."
}

_fix_app_sysbuild_key_path() {
  local product_dir="$1"
  local fw_submodule="$2"
  local build_fw_path="$3"   # path as the build environment sees it

  local sysbuild="${product_dir}/${fw_submodule}/sysbuild.conf"
  [[ -f "$sysbuild" ]] || return 0

  local expected="SB_CONFIG_BOOT_ENCRYPTION_KEY_FILE=\"${build_fw_path}/encryption_key.pem\""

  # Skip if already correct
  if grep -qF "$expected" "$sysbuild" 2>/dev/null; then
    return 0
  fi

  info "Fixing ${fw_submodule}/sysbuild.conf key path → ${build_fw_path}/encryption_key.pem"
  sed -i \
    "s|SB_CONFIG_BOOT_ENCRYPTION_KEY_FILE=\"[^\"]*\"|SB_CONFIG_BOOT_ENCRYPTION_KEY_FILE=\"${build_fw_path}/encryption_key.pem\"|g" \
    "$sysbuild"
}

# ─── Build ───────────────────────────────────────────────────

cmd_build() {
  local product="${1:?Usage: ctl.sh build <product> [options]}"
  shift
  local product_dir
  product_dir="$(resolve_product_dir "$product")"

  # Parse options
  local target="all"
  local mtib_rev=""
  local variant=""
  local pristine=""
  local no_docker=false
  local extra_args=()

  while [[ $# -gt 0 ]]; do
    case $1 in
      --target)     target="$2"; shift 2 ;;
      --mtib-rev)   mtib_rev="$2"; shift 2 ;;
      --variant)    variant="$2"; shift 2 ;;
      --pristine)   pristine="yes"; shift ;;
      --no-docker)  no_docker=true; shift ;;
      *)            extra_args+=("$1"); shift ;;
    esac
  done

  # Build list of targets to process
  local targets=()
  case "$target" in
    app) targets=(app) ;;
    mfg) targets=(mfg) ;;
    all) targets=(app mfg) ;;
    *)
      err "Invalid --target: ${target} (expected: app, mfg, or all)"
      exit 1
      ;;
  esac

  for t in "${targets[@]}"; do
    _build_one "$product" "$product_dir" "$t" "$mtib_rev" "$variant" "$pristine" "$no_docker" "${extra_args[@]+"${extra_args[@]}"}"
  done

  echo ""
  log "Build complete. Artifacts:"
  _list_artifacts "$product_dir"
}

_build_one() {
  local product="$1"
  local product_dir="$2"
  local target="$3"
  local mtib_rev="$4"
  local variant="$5"
  local pristine="$6"
  local no_docker="$7"
  shift 7
  local extra_args=("$@")

  local fw_submodule
  fw_submodule="$(resolve_fw_submodule "$product" "$target")"

  echo ""
  info "═══════════════════════════════════════════════"
  info "  Building ${fw_submodule}"
  info "  target=${target}  mtib_rev=${mtib_rev:-default}  variant=${variant:-release}"
  info "═══════════════════════════════════════════════"

  # Assemble build.sh arguments
  local build_args=("$target")
  [[ -n "$mtib_rev" ]]  && build_args+=(--mtib-rev "$mtib_rev")
  [[ -n "$variant" ]]   && build_args+=(--variant "$variant")
  [[ -n "$pristine" ]]  && build_args+=(--pristine)
  build_args+=("${extra_args[@]+"${extra_args[@]}"}")

  # Firmware submodule CMakeLists.txt is missing -lm (math library).
  # Patch on the host before building, restore after. The volume mount
  # makes this visible inside Docker too.
  local cmake_file="${product_dir}/${fw_submodule}/CMakeLists.txt"
  if [[ -f "$cmake_file" ]] && ! grep -q 'target_link_libraries(app PRIVATE m)' "$cmake_file"; then
    sed -i '/zephyr_include_directories(src)/a target_link_libraries(app PRIVATE m)' "$cmake_file"
  fi

  if [[ "$no_docker" == "true" ]]; then
    # Local mode: fix paths for the local filesystem
    local build_fw_path="${product_dir}/${fw_submodule}"
    _ensure_encryption_keys "$product_dir" "$fw_submodule" "" ""
    _fix_app_sysbuild_key_path "$product_dir" "$fw_submodule" "$build_fw_path"

    log "Building locally (--no-docker)..."
    (cd "$product_dir" && bash scripts/build.sh "${build_args[@]}")
  else
    # Ensure registry CA certs are installed before pulling images
    ensure_registry_certs

    local docker_image
    docker_image="$(resolve_docker_image "${product_dir}/${fw_submodule}")"
    log "Docker image: ${BOLD}${docker_image}${NC}"

    # When running inside a devcontainer, Docker sees host paths, not
    # container paths. Detect the host mount point and translate.
    local host_product_dir="$product_dir"
    if [[ "$product_dir" == /workspaces/concord/* ]]; then
      local host_root=""
      # Extract host path from mount info (findmnt shows SOURCE[SUBPATH])
      host_root="$(findmnt -n -o SOURCE /workspaces/concord 2>/dev/null \
        | sed -n 's|.*\[\(.*\)\]|\1|p')"
      if [[ -n "$host_root" ]]; then
        host_product_dir="${host_root}${product_dir#/workspaces/concord}"
      elif [[ -n "${CONCORD_MONOREPO_ROOT:-}" ]]; then
        host_product_dir="${CONCORD_MONOREPO_ROOT}${product_dir#/workspaces/concord}"
      fi
      log "Host path: ${host_product_dir}"
    fi

    # Pre-build: generate encryption keys + fix sysbuild.conf paths
    # Keys are generated inside Docker (imgtool.py lives there).
    # Sysbuild paths are fixed on the host (file is in the mounted volume).
    local build_fw_path="/workspaces/${product}/${fw_submodule}"
    _ensure_encryption_keys "$product_dir" "$fw_submodule" "$docker_image" "${host_product_dir}/${fw_submodule}"
    _fix_app_sysbuild_key_path "$product_dir" "$fw_submodule" "$build_fw_path"

    log "Running build inside container..."
    docker run --rm \
      -v "${host_product_dir}:/workspaces/${product}" \
      -w "/workspaces/${product}" \
      -u "$(id -u):$(id -g)" \
      "${docker_image}" \
      bash scripts/build.sh "${build_args[@]}"
  fi

  # Restore patched CMakeLists.txt to keep submodule clean
  git -C "${product_dir}/${fw_submodule}" checkout -- CMakeLists.txt 2>/dev/null || true

  log "${fw_submodule} build finished."
}

# ─── Build All ───────────────────────────────────────────────

cmd_build_all() {
  local product="${1:?Usage: ctl.sh build-all <product>}"
  shift
  local product_dir
  product_dir="$(resolve_product_dir "$product")"

  local no_docker=false
  local parallel=false
  while [[ $# -gt 0 ]]; do
    case $1 in
      --no-docker) no_docker=true; shift ;;
      --parallel|-j) parallel=true; shift ;;
      *)           shift ;;
    esac
  done

  local docker_flag=""
  [[ "$no_docker" == "true" ]] && docker_flag="--no-docker"

  # Determine build matrix — grouped by target (mfg vs app).
  # Builds within a group MUST be sequential (shared build dir).
  # Groups CAN run in parallel (different submodule dirs).
  local mfg_matrix=()
  local app_matrix=()
  case "$product" in
    alpha)
      # Alpha: 3 variants (mfg/debug/release) × 2 MTIB revisions = 6 invocations
      # Each invocation produces 2 MCU hex files = 12 total
      mfg_matrix=(
        "mfg    --mtib-rev 1.1"
        "mfg    --mtib-rev 1.2"
      )
      app_matrix=(
        "app    --mtib-rev 1.1 --variant debug"
        "app    --mtib-rev 1.2 --variant debug"
        "app    --mtib-rev 1.1"
        "app    --mtib-rev 1.2"
      )
      ;;
    sigma5)
      # Sigma5: app (cmake, no MTIB variants) + mfg
      app_matrix=("app")
      mfg_matrix=("mfg")
      ;;
    *)
      # Generic: build app + mfg
      app_matrix=("app")
      mfg_matrix=("mfg")
      ;;
  esac

  local total=$(( ${#mfg_matrix[@]} + ${#app_matrix[@]} ))

  echo ""
  if [[ "$parallel" == "true" ]]; then
    log "Building all variants for ${BOLD}${product}${NC} (${total} builds, ${BOLD}parallel${NC}: mfg + app concurrently)"
  else
    log "Building all variants for ${BOLD}${product}${NC} (${total} build invocations)"
  fi
  echo ""

  if [[ "$parallel" == "true" ]]; then
    # Run mfg group and app group in parallel.
    # Each group runs its entries sequentially (shared build dir within group).
    local mfg_log app_log
    mfg_log="$(mktemp /tmp/fw-build-mfg-XXXXXX.log)"
    app_log="$(mktemp /tmp/fw-build-app-XXXXXX.log)"

    _run_build_group() {
      local group_name="$1"; shift
      local entries=("$@")
      local idx=0
      for entry in "${entries[@]}"; do
        idx=$((idx + 1))
        local args
        read -ra args <<< "$entry"
        local target="${args[0]}"
        local remaining=("${args[@]:1}")
        echo -e "${CYAN}━━━ [${group_name} ${idx}/${#entries[@]}] target=${target} ${remaining[*]+"${remaining[*]}"} ━━━${NC}"
        cmd_build "$product" --target "$target" ${docker_flag:+"$docker_flag"} "${remaining[@]+"${remaining[@]}"}"
      done
    }

    log "Starting ${BOLD}mfg${NC} group (${#mfg_matrix[@]} builds) in background..."
    _run_build_group "mfg" "${mfg_matrix[@]}" > "$mfg_log" 2>&1 &
    local mfg_pid=$!

    log "Starting ${BOLD}app${NC} group (${#app_matrix[@]} builds) in background..."
    _run_build_group "app" "${app_matrix[@]}" > "$app_log" 2>&1 &
    local app_pid=$!

    log "Waiting for both groups to finish..."
    local failed=false

    if wait "$mfg_pid"; then
      log "${GREEN}mfg group completed successfully${NC}"
    else
      err "mfg group FAILED (see ${mfg_log})"
      failed=true
    fi

    if wait "$app_pid"; then
      log "${GREEN}app group completed successfully${NC}"
    else
      err "app group FAILED (see ${app_log})"
      failed=true
    fi

    # Dump logs
    echo ""
    echo -e "${CYAN}═══ mfg group output ═══${NC}"
    cat "$mfg_log"
    echo ""
    echo -e "${CYAN}═══ app group output ═══${NC}"
    cat "$app_log"

    rm -f "$mfg_log" "$app_log"

    if [[ "$failed" == "true" ]]; then
      err "One or more build groups failed."
      exit 1
    fi
  else
    # Sequential mode (default)
    local all_entries=("${mfg_matrix[@]}" "${app_matrix[@]}")
    local current=0

    for entry in "${all_entries[@]}"; do
      current=$((current + 1))
      local args
      read -ra args <<< "$entry"
      local target="${args[0]}"
      local remaining=("${args[@]:1}")

      echo ""
      echo -e "${CYAN}━━━ [${current}/${total}] target=${target} ${remaining[*]+"${remaining[*]}"} ━━━${NC}"

      cmd_build "$product" --target "$target" ${docker_flag:+"$docker_flag"} "${remaining[@]+"${remaining[@]}"}"
    done
  fi

  echo ""
  log "All ${total} builds complete for ${product}."
  echo ""
  cmd_artifacts "$product"
}

# ─── Collect ─────────────────────────────────────────────────

cmd_collect() {
  local product="${1:?Usage: ctl.sh collect <product>}"
  shift
  local product_dir
  product_dir="$(resolve_product_dir "$product")"

  local dest_dir="${REPO_ROOT}/libs/corekinect/test/validation/assets/firmware"
  mkdir -p "$dest_dir"

  log "Collecting ${product} artifacts → ${dest_dir}/"
  echo ""

  local count=0

  case "$product" in
    alpha)
      # Collect alpha artifacts with naming: alpha_<variant>_<mcu>_rev<mtib_rev>.hex
      _collect_alpha_variant "$product_dir" "$dest_dir" "alpha_fw"  "release" && true
      _collect_alpha_variant "$product_dir" "$dest_dir" "alpha_fw"  "debug"   && true
      _collect_alpha_variant "$product_dir" "$dest_dir" "alpha_mfg_fw" "mfg"  && true
      ;;
    sigma5)
      _collect_sigma5 "$product_dir" "$dest_dir" && true
      ;;
    *)
      warn "No collect rules defined for product: ${product}"
      warn "Artifacts remain in: ${product_dir}/artifacts/"
      return 0
      ;;
  esac

  echo ""

  # Generate manifest
  _generate_manifest "$dest_dir" "$product"

  log "Collection complete."
}

_collect_alpha_variant() {
  local product_dir="$1"
  local dest_dir="$2"
  local fw_name="$3"   # alpha_fw or alpha_mfg_fw
  local variant="$4"   # mfg, debug, or release

  local src_dir="${product_dir}/artifacts/${fw_name}/alpha_b0"

  if [[ ! -d "$src_dir" ]]; then
    warn "No artifacts for ${fw_name} (expected: ${src_dir})"
    return 0
  fi

  # Determine MTIB revisions by checking what overlays were used
  # Artifacts are at artifacts/<fw_name>/<board>/ — the build.sh collects them there
  # We need to look at what was actually built
  for hex in "${src_dir}"/*.hex; do
    [[ -f "$hex" ]] || continue
    local basename
    basename="$(basename "$hex")"

    # Map hex name to MCU
    local mcu=""
    case "$basename" in
      app_nrf52840.hex)  mcu="nrf52840" ;;
      comms_nrf9151.hex) mcu="nrf9151" ;;
      comms_nrf9160.hex) mcu="nrf9160" ;;
      *) continue ;;
    esac

    local dest_name="alpha_${variant}_${mcu}.hex"
    cp "$hex" "${dest_dir}/${dest_name}"
    info "  ${dest_name}"
  done
}

_collect_sigma5() {
  local product_dir="$1"
  local dest_dir="$2"

  # sigma5_fw artifacts (cmake build)
  for target_dir in "${product_dir}/artifacts/sigma5_fw"/*/; do
    [[ -d "$target_dir" ]] || continue
    local target
    target="$(basename "$target_dir")"

    for hex in "${target_dir}"/*.hex; do
      [[ -f "$hex" ]] || continue
      local basename
      basename="$(basename "$hex")"
      local mcu=""
      case "$basename" in
        app_nrf52840.hex)   mcu="nrf52840" ;;
        comms_nrf9160.hex)  mcu="nrf9160" ;;
        *) continue ;;
      esac
      local dest_name="sigma5_release_${mcu}.hex"
      cp "$hex" "${dest_dir}/${dest_name}"
      info "  ${dest_name}"
    done
  done

  # sigma5_mfg_fw artifacts
  local mfg_dir="${product_dir}/artifacts/sigma5_mfg_fw"
  if [[ -d "$mfg_dir" ]]; then
    for board_dir in "${mfg_dir}"/*/; do
      [[ -d "$board_dir" ]] || continue
      for hex in "${board_dir}"/*.hex; do
        [[ -f "$hex" ]] || continue
        local basename
        basename="$(basename "$hex")"
        local mcu=""
        case "$basename" in
          app_nrf52840.hex)   mcu="nrf52840" ;;
          comms_nrf9160.hex)  mcu="nrf9160" ;;
          *) continue ;;
        esac
        local dest_name="sigma5_mfg_${mcu}.hex"
        cp "$hex" "${dest_dir}/${dest_name}"
        info "  ${dest_name}"
      done
    done
  fi
}

_generate_manifest() {
  local dest_dir="$1"
  local product="$2"
  local manifest="${dest_dir}/manifest.json"

  log "Generating manifest.json..."

  echo "{" > "$manifest"
  echo "  \"product\": \"${product}\"," >> "$manifest"
  echo "  \"generated\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"," >> "$manifest"
  echo "  \"files\": {" >> "$manifest"

  local first=true
  for hex in "${dest_dir}"/${product}_*.hex; do
    [[ -f "$hex" ]] || continue
    local basename
    basename="$(basename "$hex")"
    local sha256
    sha256="$(sha256sum "$hex" | cut -d' ' -f1)"
    local size
    size="$(stat -c%s "$hex")"

    if [[ "$first" == "true" ]]; then
      first=false
    else
      echo "," >> "$manifest"
    fi

    printf '    "%s": {"sha256": "%s", "size": %s}' "$basename" "$sha256" "$size" >> "$manifest"
  done

  echo "" >> "$manifest"
  echo "  }" >> "$manifest"
  echo "}" >> "$manifest"

  info "  manifest.json"
}

# ─── Clean ───────────────────────────────────────────────────

cmd_clean() {
  local product="${1:?Usage: ctl.sh clean <product>}"
  shift
  local product_dir
  product_dir="$(resolve_product_dir "$product")"

  warn "Cleaning ${product} build artifacts..."

  # Clean artifacts directory
  rm -rf "${product_dir}/artifacts"

  # Delegate to product build.sh clean if it exists
  if [[ -f "${product_dir}/scripts/build.sh" ]]; then
    (cd "$product_dir" && bash scripts/build.sh clean)
  fi

  log "Clean complete."
}

# ─── Artifacts ───────────────────────────────────────────────

cmd_artifacts() {
  local product="${1:?Usage: ctl.sh artifacts <product>}"
  shift
  local product_dir
  product_dir="$(resolve_product_dir "$product")"

  local artifacts_dir="${product_dir}/artifacts"

  if [[ ! -d "$artifacts_dir" ]]; then
    warn "No artifacts directory found for ${product}."
    warn "Run: ./apps/firmware/products/ctl.sh build ${product}"
    return 0
  fi

  echo ""
  echo -e "${BOLD}Firmware artifacts for ${product}:${NC}"
  echo ""

  # List hex files with sizes
  local count=0
  while IFS= read -r -d '' hex; do
    local rel_path="${hex#"${product_dir}/"}"
    local size
    size="$(stat -c%s "$hex" 2>/dev/null || echo "?")"
    local human_size
    human_size="$(numfmt --to=iec-i --suffix=B "$size" 2>/dev/null || echo "${size}B")"
    printf "  ${GREEN}%-60s${NC} %s\n" "$rel_path" "$human_size"
    count=$((count + 1))
  done < <(find "$artifacts_dir" -name "*.hex" -print0 | sort -z)

  if [[ $count -eq 0 ]]; then
    warn "  No .hex files found in ${artifacts_dir}/"
  else
    echo ""
    log "${count} artifact(s) found."
  fi
}

_list_artifacts() {
  local product_dir="$1"
  local artifacts_dir="${product_dir}/artifacts"

  if [[ ! -d "$artifacts_dir" ]]; then
    warn "  (no artifacts directory)"
    return 0
  fi

  find "$artifacts_dir" -name "*.hex" -printf "  %p\n" | sort || true
}

# ─── Help ────────────────────────────────────────────────────

usage() {
  cat <<EOF

${BOLD}Firmware Build Controller${NC}

${BOLD}Usage:${NC}
  ./apps/firmware/products/ctl.sh <command> <product> [options]

${BOLD}Commands:${NC}
  ${GREEN}build <product>${NC}          Build firmware in Docker container
  ${GREEN}build-all <product>${NC}      Build all variant/revision combinations
  ${GREEN}collect <product>${NC}        Copy artifacts to validation assets directory
  ${GREEN}clean <product>${NC}          Remove build directories and artifacts
  ${GREEN}artifacts <product>${NC}      List built artifacts
  ${GREEN}help${NC}                     Show this help

${BOLD}Products:${NC}
$(for d in "${SCRIPT_DIR}"/*/; do
    if [[ -f "${d}project.json" ]]; then
      echo "  $(basename "$d")"
    fi
  done)

${BOLD}Build Options:${NC}
  ${CYAN}--target app|mfg|all${NC}     Which firmware to build (default: all)
  ${CYAN}--mtib-rev 1.1|1.2${NC}       MTIB hardware revision (alpha only)
  ${CYAN}--variant debug|release${NC}   Build variant (default: release)
  ${CYAN}--pristine${NC}               Force clean rebuild
  ${CYAN}--no-docker${NC}              Build locally instead of in Docker
  ${CYAN}--parallel, -j${NC}           Run mfg + app groups concurrently (build-all only)

${BOLD}Docker Image Resolution:${NC}
  Each firmware submodule has a .devcontainer/devcontainer.json that specifies
  the NCS Docker image. ctl.sh reads this dynamically per build target:
    app → <product>_fw/.devcontainer/devcontainer.json
    mfg → <product>_mfg_fw/.devcontainer/devcontainer.json

${BOLD}Examples:${NC}
  # Single build
  ./apps/firmware/products/ctl.sh build alpha --target mfg --mtib-rev 1.2

  # All alpha variants (6 builds → 12 hex files)
  ./apps/firmware/products/ctl.sh build-all alpha

  # Parallel: mfg + app groups run concurrently (~2x faster)
  ./apps/firmware/products/ctl.sh build-all alpha --parallel

  # Sigma5 production firmware only
  ./apps/firmware/products/ctl.sh build sigma5 --target app

  # Build locally (already inside NCS container)
  ./apps/firmware/products/ctl.sh build alpha --target mfg --no-docker

  # Collect to validation assets
  ./apps/firmware/products/ctl.sh collect alpha

  # List what's been built
  ./apps/firmware/products/ctl.sh artifacts alpha

EOF
}

# ─── Main ────────────────────────────────────────────────────

if [[ $# -eq 0 ]]; then
  usage
  exit 0
fi

COMMAND="$1"
shift

case "${COMMAND}" in
  build)      cmd_build "$@" ;;
  build-all)  cmd_build_all "$@" ;;
  collect)    cmd_collect "$@" ;;
  clean)      cmd_clean "$@" ;;
  artifacts)  cmd_artifacts "$@" ;;
  help|-h|--help) usage ;;
  *)
    err "Unknown command: ${COMMAND}"
    usage
    exit 1
    ;;
esac
