#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# Concord Build SDK — universal firmware build toolkit
#
# Sourced by every product build recipe. Provides:
#   concord_init            Setup workspace, parse targets, extract version
#   concord_collect_hex     Register a hex artifact for a target role
#   concord_collect_cfw     Generate CFW from signed encrypted bin
#   concord_finalize        Validate artifacts, generate build.json manifest
#
# The recipe author writes ONLY the build commands (west build, etc.).
# All artifact naming, CFW generation, version handling, and manifest
# creation is handled by this SDK.
#
# Required env vars (injected by Concord build service):
#   CONCORD_TARGETS        JSON: [{"role":"app","appId":109,"processor":"nrf52840"}, ...]
#   CONCORD_BOARD          Board name, e.g., "alpha_b0"
#   CONCORD_VARIANT        Build variant: "debug", "release", "mfg"
#   CONCORD_FW_TYPE        Firmware type: "app", "mfg"
#   CONCORD_CONFIG_LOG     UART logging: "y" or "n"
#   CONCORD_PRODUCES_HEX   "true" or "false"
#   CONCORD_PRODUCES_CFW   "true" or "false"
#   CONCORD_REPO_DIR       Path to cloned primary firmware repo
#   CONCORD_OUTPUT_DIR     Path for final artifacts
#   CONCORD_VERSION_OVERRIDE  Optional: override build number
#   CONCORD_COMMIT_SHA     Git commit hash
#   CONCORD_BRANCH         Git branch name
#   CONCORD_MATRIX_LABEL   Build matrix label (e.g., "MFG_BASE", "FUT_VERBOSE_A")
# ─────────────────────────────────────────────────────────────────────────────

set -eo pipefail

CYAN='\033[0;36m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Internal state
_CONCORD_VERSION_MAJOR=""
_CONCORD_VERSION_MINOR=""
_CONCORD_VERSION_BUILD=""
_CONCORD_VERSION_STRING=""
_CONCORD_TRACK_STR=""
_CONCORD_CFW_TRACK=0
_CONCORD_CFW_MFG=0
_CONCORD_CFW_DEBUG=0
_CONCORD_COLLECTED_HEX=()
_CONCORD_COLLECTED_CFW=()

# ─────────────────────────────────────────────────────────────────────────────
# concord_init — setup workspace and extract version
# ─────────────────────────────────────────────────────────────────────────────
concord_init() {
    echo -e "${CYAN}╔══════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║  Concord Build SDK                       ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════╝${NC}"
    echo -e "${CYAN}Board:    ${CONCORD_BOARD:-?}${NC}"
    echo -e "${CYAN}Variant:  ${CONCORD_VARIANT:-?}${NC}"
    echo -e "${CYAN}FW Type:  ${CONCORD_FW_TYPE:-?}${NC}"
    echo -e "${CYAN}Label:    ${CONCORD_MATRIX_LABEL:-?}${NC}"
    echo -e "${CYAN}Repo:     ${CONCORD_REPO_DIR:-?}${NC}"

    # Create output directory
    CONCORD_OUTPUT_DIR="${CONCORD_OUTPUT_DIR:-/workspace/artifacts}"
    CONCORD_BUILD_DIR="${CONCORD_BUILD_DIR:-${CONCORD_REPO_DIR}/build}"
    mkdir -p "$CONCORD_OUTPUT_DIR"

    # Derive CONCORD_COMMS_SOC from targets JSON (always lowercase for west build)
    if [ -n "$CONCORD_TARGETS" ]; then
        CONCORD_COMMS_SOC=$(echo "$CONCORD_TARGETS" | python3 -c "
import sys, json
targets = json.load(sys.stdin)
for t in targets:
    if t.get('role') == 'comms':
        print(t.get('processor', '').lower())
        break
" 2>/dev/null || true)
        export CONCORD_COMMS_SOC
    fi

    # Fix hardcoded paths in sysbuild.conf files
    _concord_fix_sysbuild_paths

    # Extract version
    _concord_extract_version

    # Compute CFW track flags
    _concord_compute_track

    # Ensure west can find the NCS workspace
    # The NCS container has west initialized at /workdir.
    # Without this, west build fails with "workspace not found".
    if [ -d "/workdir/.west" ]; then
        export WEST_TOPDIR="/workdir"
    fi

    echo -e "${GREEN}Version:  ${_CONCORD_VERSION_STRING}${NC}"
    echo -e "${GREEN}Track:    ${_CONCORD_TRACK_STR}${NC}"
    echo ""
}

# ─────────────────────────────────────────────────────────────────────────────
# Fix hardcoded paths in sysbuild.conf and related config files
#
# Firmware repos often hardcode paths like /workspaces/alpha_fw/ for local
# development. In CI mode, the repo is cloned to CONCORD_REPO_DIR.
# This function rewrites those paths AND creates placeholder signing keys
# if none are provided (so cmake configure doesn't fail).
# ─────────────────────────────────────────────────────────────────────────────
_concord_fix_sysbuild_paths() {
    local repo_dir="${CONCORD_REPO_DIR}"
    if [ -z "$repo_dir" ] || [ ! -d "$repo_dir" ]; then
        return 0
    fi

    # Temporarily disable pipefail for this function — grep exit codes in pipes
    # cause false failures with set -eo pipefail
    set +eo pipefail

    echo -e "${CYAN}Fixing build configuration paths...${NC}"

    # Fix ALL sysbuild.conf files — replace any /workspaces/* paths with actual repo path
    find "$repo_dir" -name "sysbuild.conf" -type f 2>/dev/null | while read conf; do
        if grep -q "/workspaces/" "$conf" 2>/dev/null; then
            # Get the repo basename (e.g., alpha_fw, alpha_mfg_fw)
            local repo_basename
            repo_basename=$(basename "$repo_dir")

            # Replace /workspaces/{repo_name}/ with actual path
            sed -i "s|/workspaces/${repo_basename}/|${repo_dir}/|g" "$conf"
            # Also replace any /workspaces/comm_coproc_mfg/ (submodule paths)
            sed -i "s|/workspaces/comm_coproc_mfg/|${repo_dir}/comm_coproc_mfg/|g" "$conf"
            # Generic catch-all for any remaining /workspaces/ paths
            sed -i "s|/workspaces/[a-z_]*/|${repo_dir}/|g" "$conf"
            echo -e "  ${GREEN}Fixed paths in $(basename $(dirname $conf))/$(basename $conf)${NC}"
        fi
    done

    # Ensure encryption key files exist
    # MCUboot sysbuild requires encryption_key.pem for signed+encrypted builds.
    # If keys are mounted at /keys/{product}/, use those.
    # Otherwise create a dev-only placeholder key (builds will work but CFW won't be FUOTA-valid).
    local product_base
    product_base=$(echo "$CONCORD_PRODUCT" | tr '[:upper:]' '[:lower:]')
    local keys_source="/keys/${product_base}"

    # Find all encryption key references in sysbuild configs
    # NOTE: "|| true" guards prevent set -eo pipefail from killing the script
    # when grep returns no matches (exit code 1)
    local _conf_files
    _conf_files=$(find "$repo_dir" -name "sysbuild.conf" -type f 2>/dev/null || true)
    for conf in $_conf_files; do
        local _key_refs
        _key_refs=$(grep -oP 'SB_CONFIG_BOOT_ENCRYPTION_KEY_FILE="([^"]+)"' "$conf" 2>/dev/null || true)
        [ -z "$_key_refs" ] && continue
        echo "$_key_refs" | while read line; do
            local key_path
            key_path=$(echo "$line" | sed 's/.*"\(.*\)".*/\1/')
            local key_name
            key_name=$(basename "$key_path")

            if [ ! -f "$key_path" ]; then
                # Try to find key from mounted secrets
                if [ -d "$keys_source" ] && [ -f "${keys_source}/${key_name}" ]; then
                    cp "${keys_source}/${key_name}" "$key_path"
                    echo -e "  ${GREEN}Signing key: ${key_name} (from secrets)${NC}"
                elif [ -d "$keys_source" ]; then
                    # Copy first available key as fallback
                    local any_key
                    any_key=$(find "$keys_source" -name "*.pem" -type f 2>/dev/null | head -1)
                    if [ -n "$any_key" ]; then
                        cp "$any_key" "$key_path"
                        echo -e "  ${YELLOW}Signing key: ${key_name} (fallback from ${any_key})${NC}"
                    fi
                fi

                # If still missing, the orchestrator should have deployed it
                # from Concord Secrets. If not, the build will fail at CMake
                # configure time with a clear error about the missing key.
                if [ ! -f "$key_path" ]; then
                    echo -e "  ${RED}MISSING: ${key_name} at ${key_path}${NC}"
                    echo -e "  ${RED}Configure a signing key in Products → Stage Config → Signing Key${NC}"
                fi
            else
                echo -e "  ${GREEN}Signing key: ${key_name} (already present)${NC}"
            fi
        done
    done

    # Re-enable strict mode
    set -eo pipefail
}

# ─────────────────────────────────────────────────────────────────────────────
# Version extraction — reads version.conf + VersionDevice.h, applies overrides
# ─────────────────────────────────────────────────────────────────────────────
_concord_extract_version() {
    local repo_dir="${CONCORD_REPO_DIR:-.}"

    # Read from version.conf (supports both legacy and current formats)
    local version_conf="${repo_dir}/version.conf"
    if [ -f "$version_conf" ]; then
        # Current format: CONFIG_APP_FW_MAJOR_VERSION / CONFIG_APP_FW_MINOR_VERSION
        _CONCORD_VERSION_MAJOR=$(grep -E "^CONFIG_APP_FW_MAJOR_VERSION=" "$version_conf" 2>/dev/null | cut -d'=' -f2 || true)
        _CONCORD_VERSION_MINOR=$(grep -E "^CONFIG_APP_FW_MINOR_VERSION=" "$version_conf" 2>/dev/null | cut -d'=' -f2 || true)
        _CONCORD_VERSION_BUILD=$(grep -E "^CONFIG_APP_FW_BUILD_VERSION=" "$version_conf" 2>/dev/null | cut -d'=' -f2 || true)

        # Legacy format fallback
        [ -z "$_CONCORD_VERSION_MAJOR" ] && _CONCORD_VERSION_MAJOR=$(grep -E "^CONFIG_FW_INFO_VERSION_MAJOR=" "$version_conf" 2>/dev/null | cut -d'=' -f2 || true)
        [ -z "$_CONCORD_VERSION_MINOR" ] && _CONCORD_VERSION_MINOR=$(grep -E "^CONFIG_FW_INFO_VERSION_MINOR=" "$version_conf" 2>/dev/null | cut -d'=' -f2 || true)
        [ -z "$_CONCORD_VERSION_BUILD" ] && _CONCORD_VERSION_BUILD=$(grep -E "^CONFIG_FW_INFO_VERSION_BUILD=" "$version_conf" 2>/dev/null | cut -d'=' -f2 || true)
    fi

    # If build number still empty, try VersionDevice.h
    if [ -z "$_CONCORD_VERSION_BUILD" ]; then
        local version_h
        version_h=$(find "${repo_dir}" -name "VersionDevice.h" -type f 2>/dev/null | head -1)
        if [ -n "$version_h" ] && [ -f "$version_h" ]; then
            _CONCORD_VERSION_BUILD=$(grep -E "^#define BUILD_NUM" "$version_h" 2>/dev/null | awk '{print $3}' || true)
        fi
    fi

    # Defaults
    _CONCORD_VERSION_MAJOR="${_CONCORD_VERSION_MAJOR:-0}"
    _CONCORD_VERSION_MINOR="${_CONCORD_VERSION_MINOR:-0}"
    _CONCORD_VERSION_BUILD="${_CONCORD_VERSION_BUILD:-0}"

    # Apply override (FUOTA N+1 builds)
    if [ -n "$CONCORD_VERSION_OVERRIDE" ]; then
        _CONCORD_VERSION_BUILD="$CONCORD_VERSION_OVERRIDE"
        echo -e "${CYAN}Version override: build=${CONCORD_VERSION_OVERRIDE}${NC}"

        # Patch VersionDevice.h so the compiled binary has the right version
        local version_files
        version_files=$(find "${repo_dir}" -name "VersionDevice.h" -type f 2>/dev/null)
        for vf in $version_files; do
            if grep -q "^#define BUILD_NUM" "$vf"; then
                sed -i "s/^#define BUILD_NUM.*/#define BUILD_NUM         ${CONCORD_VERSION_OVERRIDE}/" "$vf"
                echo -e "${GREEN}Patched BUILD_NUM in ${vf}${NC}"
            fi
        done
    fi

    # Patch git metadata into VersionDevice.h
    local git_sha="${CONCORD_COMMIT_SHA:0:7}"
    [ -z "$git_sha" ] && git_sha="unknown"
    local version_files
    version_files=$(find "${repo_dir}" -name "VersionDevice.h" -type f 2>/dev/null)
    for vf in $version_files; do
        if grep -q "^#define BUILD_GIT_SHA" "$vf"; then
            sed -i "s/^#define BUILD_GIT_SHA.*/#define BUILD_GIT_SHA     \"${git_sha}\"/" "$vf"
            sed -i "s/^#define BUILD_VARIANT.*/#define BUILD_VARIANT     \"${CONCORD_VARIANT:-release}\"/" "$vf"
        fi
    done

    _CONCORD_VERSION_STRING="${_CONCORD_VERSION_MAJOR}.${_CONCORD_VERSION_MINOR}.${_CONCORD_VERSION_BUILD}"
    echo -e "${CYAN}Resolved version: ${_CONCORD_VERSION_STRING}${NC}"
}

# ─────────────────────────────────────────────────────────────────────────────
# CFW track flag computation
#
# Track encodes: B=Bench, E=Engineering, P=Production, M=Manufacturing, D=Debug
# CRITICAL: CoreCloud strips D flag. NEVER use D for FUOTA builds.
# ─────────────────────────────────────────────────────────────────────────────
_concord_compute_track() {
    _CONCORD_CFW_TRACK=0  # 0=Bench, 1=Engineering, 2=Production
    _CONCORD_CFW_MFG=0
    _CONCORD_CFW_DEBUG=0

    # Manufacturing flag
    if [ "$CONCORD_FW_TYPE" = "mfg" ] || [ "$CONCORD_VARIANT" = "mfg" ]; then
        _CONCORD_CFW_MFG=1
    fi

    # Debug flag — ONLY for non-FUOTA builds
    # For FUOTA stages, config_log controls UART output without setting D flag
    if [ "$CONCORD_VARIANT" = "debug" ] && [ "$CONCORD_PRODUCES_CFW" != "true" ]; then
        _CONCORD_CFW_DEBUG=1
    fi

    # Build track string (use if/then to avoid set -e failures on false tests)
    _CONCORD_TRACK_STR="B"
    if [ $_CONCORD_CFW_MFG -eq 1 ]; then _CONCORD_TRACK_STR="${_CONCORD_TRACK_STR}M"; fi
    if [ $_CONCORD_CFW_DEBUG -eq 1 ]; then _CONCORD_TRACK_STR="${_CONCORD_TRACK_STR}D"; fi
}

# ─────────────────────────────────────────────────────────────────────────────
# concord_collect_hex — register a hex artifact for a target role
#
# Usage: concord_collect_hex <role> <path_to_merged_hex>
#   role: "app" or "comms" (must match a target in CONCORD_TARGETS)
#   path: path to the merged.hex output from west build
# ─────────────────────────────────────────────────────────────────────────────
concord_collect_hex() {
    local role="$1"
    local hex_path="$2"

    if [ ! -f "$hex_path" ]; then
        echo -e "${YELLOW}Warning: hex not found for ${role}: ${hex_path}${NC}"
        return 1
    fi

    # Look up appId from targets
    local app_id
    app_id=$(_concord_get_appid "$role")
    if [ -z "$app_id" ]; then
        echo -e "${RED}Error: no appId for role '${role}' in CONCORD_TARGETS${NC}"
        return 1
    fi

    local hex_name="${app_id}.${_CONCORD_VERSION_STRING}.hex"
    cp "$hex_path" "${CONCORD_OUTPUT_DIR}/${hex_name}"
    echo -e "  ${GREEN}${hex_name}${NC} (${role})"
    _CONCORD_COLLECTED_HEX+=("${role}:${hex_name}")
}

# ─────────────────────────────────────────────────────────────────────────────
# concord_collect_cfw — generate CFW from signed encrypted bin
#
# Usage: concord_collect_cfw <role> <path_to_signed_encrypted_bin>
# ─────────────────────────────────────────────────────────────────────────────
concord_collect_cfw() {
    local role="$1"
    local bin_path="$2"

    if [ "$CONCORD_PRODUCES_CFW" != "true" ]; then
        return 0  # This build doesn't produce CFW
    fi

    if [ ! -f "$bin_path" ]; then
        echo -e "${YELLOW}Warning: signed bin not found for ${role}: ${bin_path}${NC}"
        return 1
    fi

    local app_id
    app_id=$(_concord_get_appid "$role")
    if [ -z "$app_id" ]; then
        echo -e "${RED}Error: no appId for role '${role}'${NC}"
        return 1
    fi

    local cfw_name="${app_id}.${_CONCORD_VERSION_STRING}-${_CONCORD_TRACK_STR}.cfw"
    local cfw_path="${CONCORD_OUTPUT_DIR}/${cfw_name}"

    _concord_generate_cfw_file "$bin_path" "$app_id" \
        "$_CONCORD_VERSION_MAJOR" "$_CONCORD_VERSION_MINOR" "$_CONCORD_VERSION_BUILD" \
        "$_CONCORD_CFW_TRACK" "$_CONCORD_CFW_MFG" "$_CONCORD_CFW_DEBUG" \
        "$cfw_path"

    _CONCORD_COLLECTED_CFW+=("${role}:${cfw_name}")
}

# ─────────────────────────────────────────────────────────────────────────────
# concord_finalize — validate artifacts and generate build.json manifest
# ─────────────────────────────────────────────────────────────────────────────
concord_finalize() {
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════${NC}"
    echo -e "${CYAN}  Finalizing build artifacts${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════${NC}"

    echo -e "  Collected hex: ${#_CONCORD_COLLECTED_HEX[@]}"
    echo -e "  Collected cfw: ${#_CONCORD_COLLECTED_CFW[@]}"

    # Write collected artifacts to temp file for Python to read
    local _hex_list="${CONCORD_OUTPUT_DIR}/.hex_list"
    local _cfw_list="${CONCORD_OUTPUT_DIR}/.cfw_list"
    printf '%s\n' "${_CONCORD_COLLECTED_HEX[@]}" > "$_hex_list"
    printf '%s\n' "${_CONCORD_COLLECTED_CFW[@]}" > "$_cfw_list"

    # Generate build.json manifest
    CONCORD_VERSION_STRING="${_CONCORD_VERSION_STRING}" \
    CONCORD_TRACK_STR="${_CONCORD_TRACK_STR}" \
    python3 << 'MANIFEST_EOF'
import json, os, time

targets_json = os.environ.get("CONCORD_TARGETS", "[]")
targets = json.loads(targets_json) if targets_json else []
output_dir = os.environ.get("CONCORD_OUTPUT_DIR", ".")

# Read collected artifacts from temp files
hex_map = {}
hex_list_path = os.path.join(output_dir, ".hex_list")
if os.path.exists(hex_list_path):
    for line in open(hex_list_path).read().strip().split("\n"):
        if ":" in line:
            role, name = line.split(":", 1)
            hex_map[role] = name

cfw_map = {}
cfw_list_path = os.path.join(output_dir, ".cfw_list")
if os.path.exists(cfw_list_path):
    for line in open(cfw_list_path).read().strip().split("\n"):
        if ":" in line:
            role, name = line.split(":", 1)
            cfw_map[role] = name

manifest_targets = []
for t in targets:
    role = t.get("role", "")
    entry = {
        "role": role,
        "processor": t.get("processor", ""),
        "appId": t.get("appId", 0),
        "plaintextHex": hex_map.get(role, ""),
        "encryptedCfw": cfw_map.get(role, ""),
    }
    manifest_targets.append(entry)

manifest = {
    "schemaVersion": 1,
    "product": os.environ.get("CONCORD_PRODUCT", ""),
    "board": os.environ.get("CONCORD_BOARD", ""),
    "version": os.environ.get("CONCORD_VERSION_STRING", "0.0.0"),
    "variant": os.environ.get("CONCORD_VARIANT", "release"),
    "track": os.environ.get("CONCORD_TRACK_STR", "B"),
    "matrixLabel": os.environ.get("CONCORD_MATRIX_LABEL", ""),
    "commitSha": os.environ.get("CONCORD_COMMIT_SHA", ""),
    "branch": os.environ.get("CONCORD_BRANCH", ""),
    "builtAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "targets": manifest_targets,
}

path = os.path.join(output_dir, "build.json")
with open(path, "w") as f:
    json.dump(manifest, f, indent=2)
print(f"  build.json written to {path}")

# Clean up temp files
os.remove(hex_list_path)
os.remove(cfw_list_path)
MANIFEST_EOF

    echo ""
    echo -e "${GREEN}Build artifacts:${NC}"
    ls -la "${CONCORD_OUTPUT_DIR}/"
    echo ""
    echo -e "${GREEN}Resolved version: ${_CONCORD_VERSION_STRING}${NC}"
}

# ─────────────────────────────────────────────────────────────────────────────
# Internal: look up appId from CONCORD_TARGETS by role
# ─────────────────────────────────────────────────────────────────────────────
_concord_get_appid() {
    local role="$1"
    echo "$CONCORD_TARGETS" | python3 -c "
import sys, json
targets = json.load(sys.stdin)
for t in targets:
    if t.get('role') == '${role}':
        print(t.get('appId', ''))
        break
" 2>/dev/null
}

# ─────────────────────────────────────────────────────────────────────────────
# Internal: generate a CFW v2 file from a signed encrypted bin
# ─────────────────────────────────────────────────────────────────────────────
_concord_generate_cfw_file() {
    local bin_path="$1"
    local app_id="$2"
    local major="$3"
    local minor="$4"
    local build="$5"
    local track="$6"
    local mfg="$7"
    local debug="$8"
    local output="$9"

    python3 << PYCFW
import struct, time, os

bin_path = "${bin_path}"
app_id = ${app_id}
major = ${major}
minor = ${minor}
build = ${build}
track = ${track}
mfg = ${mfg}
debug = ${debug}
output = "${output}"

with open(bin_path, "rb") as f:
    image_data = f.read()

img_len = len(image_data)
timestamp = int(time.time())
flags = (track & 0x03) | ((mfg & 0x01) << 0) | ((debug & 0x01) << 3)

# CFW v2 header: 23 bytes
# Version(2) + Timestamp(8) + AppID(2) + Flags(1) + Major(2) + Minor(2) + Build(4) + ImgLen(4)
header = struct.pack(">HQHBHHHI",
    2,            # schema version
    timestamp,
    app_id,
    flags,
    major,
    minor,
    build,
    img_len,
)

with open(output, "wb") as f:
    f.write(header)
    f.write(image_data)

track_str = {0: "B", 1: "E", 2: "P"}.get(track, "?")
if mfg: track_str += "M"
if debug: track_str += "D"
print(f"  {os.path.basename(output)} (flags=0x{flags:02x}, {track_str}, {img_len} bytes)")
PYCFW
}
