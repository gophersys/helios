"""Build manifest (build.json) generation.

Generates a self-describing manifest from Product.buildConfig and build outputs.
The manifest is the single source of truth for what a build contains — consumers
read it instead of pattern-matching filenames or hardcoding App IDs.
"""

import hashlib
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger("build-worker")

# Maps processor names to MTIB host types and J-Link families.
# Derived at build time so test code never needs to hardcode these.
PROCESSOR_MAP: Dict[str, Dict[str, str]] = {
    "nrf52840": {
        "hostType": "HOST_TYPE_NRF52840",
        "jlinkFamily": "NRF52",
    },
    "nrf9151": {
        "hostType": "HOST_TYPE_NRF9151",
        "jlinkFamily": "NRF91",
    },
    "nrf9160": {
        "hostType": "HOST_TYPE_NRF9160",
        "jlinkFamily": "NRF91",
    },
}


def classify_artifact(filename: str) -> Optional[Tuple[str, int]]:
    """Classify a build output file by type and app ID.

    Returns (artifact_type, app_id) or None if the file is not a build artifact.
    artifact_type is one of: "plaintextHex", "encryptedCfw"
    """
    # Match: {appId}.{version}[-{track}].{ext}
    # Examples: 109.0.8.3-BM.hex, 108.0.8.3.cfw, 109.0.8.3-BMD.hex
    match = re.match(r"^(\d+)\.\d+\.\d+\.\d+(?:-[A-Z]+)?\.(hex|cfw)$", filename)
    if not match:
        return None

    app_id = int(match.group(1))
    ext = match.group(2)

    if ext == "hex":
        return ("plaintextHex", app_id)
    elif ext == "cfw":
        return ("encryptedCfw", app_id)

    return None


def _compute_track(variant: str, release_track: str) -> str:
    """Compute CFW track string from variant and release track.

    Track flags per Device Firmware Versioning SS V1.0:
    - B = Bench, E = Engineering, P = Production
    - M = Manufacturing
    - D = Debug

    Rules:
    - production releaseTrack + release variant = "P"
    - bench/engineering + mfg variant = "BM" / "EM"
    - bench/engineering + debug variant = "BMD" / "EMD"
    - bench/engineering + release variant = "BM" / "EM"
    """
    if release_track == "production":
        if variant == "debug":
            return "PD"
        return "P"

    # Bench or engineering
    prefix = "B" if release_track == "bench" else "E"
    base = prefix + "M"

    if variant == "debug":
        return base + "D"

    return base


def _scan_artifacts(output_dir: Path) -> Dict[int, Dict[str, str]]:
    """Scan output directory for hex/cfw files grouped by app ID.

    Returns: {app_id: {"plaintextHex": "filename.hex", "encryptedCfw": "filename.cfw"}}
    """
    artifacts: Dict[int, Dict[str, str]] = {}

    for f in output_dir.iterdir():
        if not f.is_file():
            continue
        result = classify_artifact(f.name)
        if result is None:
            continue

        artifact_type, app_id = result
        if app_id not in artifacts:
            artifacts[app_id] = {}
        artifacts[app_id][artifact_type] = f.name

    return artifacts


def _compute_key_fingerprints(
    key_dir: Path, targets: List[Dict[str, Any]]
) -> Optional[Dict[str, str]]:
    """Compute SHA-256 fingerprints of signing key files.

    Returns {str(appId): "hex_digest"} or None if no keys found.
    """
    if not key_dir or not key_dir.is_dir():
        return None

    fingerprints: Dict[str, str] = {}

    # Key files: encryption_key.pem (app processor), comms_encryption_key.pem (comms)
    key_mapping = {
        "app": "encryption_key.pem",
        "comms": "comms_encryption_key.pem",
    }

    for target in targets:
        role = target.get("role", "")
        app_id = target.get("appId")
        key_file_name = key_mapping.get(role)
        if not key_file_name or not app_id:
            continue

        key_path = key_dir / key_file_name
        if key_path.is_file():
            sha = hashlib.sha256(key_path.read_bytes()).hexdigest()
            fingerprints[str(app_id)] = sha

    if not fingerprints:
        return None

    return fingerprints


def generate_build_manifest(
    build_config: Dict[str, Any],
    output_dir: Path,
    product: str,
    board: str,
    version: str,
    variant: str,
    commit_sha: str,
    branch: str,
    key_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Generate a build.json manifest from buildConfig and build outputs.

    Args:
        build_config: Product.buildConfig from the API (targets, cfw, releaseTrack, ncsVersion)
        output_dir: Directory containing hex/cfw build outputs
        product: Product name (e.g., "alpha")
        board: Board identifier (e.g., "alpha_b0")
        version: Semver build version (e.g., "0.8.3")
        variant: Build variant: "mfg", "debug", "release"
        commit_sha: Git commit hash
        branch: Source branch
        key_dir: Optional path to signing key files for fingerprinting

    Returns:
        Complete build.json manifest as a dict, ready for json.dumps().
    """
    config_targets = build_config.get("targets", [])
    cfw_config = build_config.get("cfw", {})
    release_track = build_config.get("releaseTrack", "bench")
    ncs_version = build_config.get("ncsVersion", "")

    # Scan output dir for artifacts keyed by app ID
    artifact_map = _scan_artifacts(output_dir)

    # Compute track string
    track = _compute_track(variant, release_track)

    # Build targets array
    targets = []
    for target_cfg in config_targets:
        app_id = target_cfg["appId"]
        processor = target_cfg["processor"]
        role = target_cfg["role"]

        # Look up processor-derived fields
        proc_info = PROCESSOR_MAP.get(processor, {})

        # Find artifacts for this app ID
        target_artifacts = artifact_map.get(app_id, {})

        targets.append({
            "role": role,
            "processor": processor,
            "appId": app_id,
            "hostType": proc_info.get("hostType", f"HOST_TYPE_{processor.upper()}"),
            "jlinkFamily": proc_info.get("jlinkFamily", "UNKNOWN"),
            "plaintextHex": target_artifacts.get("plaintextHex"),
            "encryptedCfw": target_artifacts.get("encryptedCfw"),
        })

    # Build manifest
    manifest: Dict[str, Any] = {
        "schemaVersion": 1,
        "product": product,
        "board": board,
        "version": version,
        "variant": variant,
        "track": track,
        "releaseTrack": release_track,
        "ncsVersion": ncs_version,
        "commitSha": commit_sha,
        "branch": branch,
        "builtAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "targets": targets,
        "corecloud": {
            "deviceTypeId": cfw_config.get("deviceTypeId"),
            "deviceVariantId": cfw_config.get("deviceVariantId"),
            "apiEnv": cfw_config.get("apiEnv", "val"),
        },
    }

    # Add signing fingerprints if key files are available
    fingerprints = _compute_key_fingerprints(key_dir, config_targets)
    if fingerprints:
        manifest["signing"] = {"keyFingerprints": fingerprints}

    log.info(
        "Generated build.json: product=%s version=%s variant=%s track=%s targets=%d",
        product, version, variant, track, len(targets),
    )

    return manifest
