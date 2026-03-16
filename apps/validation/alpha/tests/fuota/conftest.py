"""FUOTA stage fixtures and utilities.

Stage 5: Over-the-air firmware update verification — blocks merge.

Provides:
- parse_cfw_header: Parse CFW v2 binary header for metadata
- FUOTA cleanup registry: atexit handler to disable FUOTA on exit
- Shared pytest CLI options consumed by test_fuota.py / test_fuota_chain.py
"""

import atexit
import struct
from pathlib import Path
from typing import Any, Dict

from corekinect.utils import Logger

log = Logger(log_name="fuota")


# =============================================================================
# CFW PARSING
# =============================================================================


def parse_cfw_header(cfw_path: Path) -> Dict[str, Any]:
    """Parse CFW v2 header (23 bytes) and return metadata.

    Returns:
        Dict with: app_id, major, minor, build, flags, target_string, is_mfg, is_debug
    """
    with open(cfw_path, "rb") as f:
        header = f.read(23)

    if len(header) < 23:
        raise ValueError(f"CFW header too short: {len(header)} bytes")

    # Unpack: FileVersion(2) + TimeCreated(8) + AppId(2) + Flags(1) + Major(2) + Minor(2) + Build(2) + ImageLen(4)
    file_ver, _, app_id, flags, major, minor, build, image_len = struct.unpack(
        ">HQHBHHHi", header
    )

    # Parse flags
    release_track = (flags >> 1) & 0x03  # bits 2:1 (0=Bench, 1=Eng, 2=Prod)
    is_mfg = bool(flags & 0x01)
    is_debug = bool(flags & 0x08)

    tracks = {0: "B", 1: "E", 2: "P"}
    track_char = tracks.get(release_track, "?")

    # Build target string: {appId}.{major}.{minor}.{build}-{track}
    suffix = track_char
    if is_mfg:
        suffix += "M"
    if is_debug:
        suffix += "D"
    target_string = f"{app_id}.{major}.{minor}.{build}-{suffix}"

    return {
        "file_version": file_ver,
        "app_id": app_id,
        "flags": flags,
        "major": major,
        "minor": minor,
        "build": build,
        "image_len": image_len,
        "target_string": target_string,
        "track": track_char,
        "is_mfg": is_mfg,
        "is_debug": is_debug,
    }


# =============================================================================
# CLEANUP
# =============================================================================

_cleanup_registry: Dict[str, int] = {}  # device_id -> plan_id


def register_fuota_cleanup(device_id: str, plan_id: int) -> None:
    """Register device+plan for cleanup on exit."""
    _cleanup_registry[device_id] = plan_id
    log.info("Registered FUOTA cleanup: device=%s plan=%d", device_id, plan_id)


def _run_fuota_cleanup() -> None:
    """Clean up all registered FUOTA assignments on exit."""
    if not _cleanup_registry:
        return

    log.info("Running FUOTA cleanup for %d device(s)...", len(_cleanup_registry))

    try:
        from corekinect.test.fuota_client import FuotaClient

        client = FuotaClient(api_env="VAL_1_0")

        for device_id, plan_id in _cleanup_registry.items():
            try:
                client.disable_device(device_id, plan_id)
                log.info("Cleaned up: device=%s plan=%d", device_id, plan_id)
            except Exception as e:
                log.warning("Cleanup failed for %s: %s", device_id, e)
    except Exception as e:
        log.warning("Cleanup init failed: %s", e)


atexit.register(_run_fuota_cleanup)
