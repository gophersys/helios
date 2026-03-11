"""Gate-specific pytest fixtures and configuration.

Provides:
- GateConfig: All configuration for Gate tests
- gate_config: pytest fixture with validated config
- Cleanup handlers for FUOTA state

Mock mode (MOCK_CLOUD=1 or --mock-cloud):
    Tests requiring real MTIB hardware or FUOTA API are automatically
    skipped. Only boot-verification tests (03, 10) run with mocks.
"""

import atexit
import os
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from corekinect.utils import EnvConfig, Logger

log = Logger(log_name="gate")

# Modem firmware paths (checked in order)
MODEM_FIRMWARE_PATHS = [
    Path("/app/firmware/modem/mfw_nrf91x1_2.0.2.zip"),  # K8s container
    Path("/workspaces/concord/apps/manufacturing/alpha/assets/mfw_nrf91x1_2.0.2.zip"),  # Local dev
    Path("apps/manufacturing/alpha/assets/mfw_nrf91x1_2.0.2.zip"),  # Relative
]


def _find_modem_firmware() -> Path:
    """Find modem firmware in known locations."""
    for path in MODEM_FIRMWARE_PATHS:
        if path.exists():
            return path
    return MODEM_FIRMWARE_PATHS[0]  # Return container path as default


# =============================================================================
# CONFIGURATION
# =============================================================================


class _GateEnvConfig(EnvConfig):
    """Environment variables for Gate tests."""

    ENV_PREFIX = ""

    # Device identity
    DEVICE_ID: Optional[str] = None
    DEVICE_SNR: Optional[str] = None
    DEVICE_IMEI: Optional[str] = None
    DEVICE_ICCIDS: Optional[str] = None  # Comma-separated

    # FUOTA source/target builds
    FUOTA_SOURCE_BUILD: str = "MFG_BASE"
    FUOTA_TARGET_BUILD: str = "MFG_BUMP"

    # Device type (Alpha = 2, B0 variant = 3)
    DEVICE_TYPE_ID: int = 2
    DEVICE_VARIANT_ID: int = 3


@dataclass
class GateConfig:
    """Gate test configuration.

    Populated from environment variables and fixture profile.
    All fields are validated during fixture setup.
    """

    # Device identity
    device_id: str = ""
    device_snr: str = ""
    device_imei: str = ""  # Pre-known IMEI (skips modem read in personalization)
    device_iccids: List[str] = field(default_factory=list)  # Pre-known ICCIDs
    device_type_id: int = 2
    device_variant_id: int = 3

    # FUOTA builds
    source_build: str = "MFG_BASE"
    target_build: str = "MFG_BUMP"

    # CFW metadata (populated during test_01)
    source_cfw_paths: List[Path] = field(default_factory=list)
    target_cfw_paths: List[Path] = field(default_factory=list)
    source_cfw_targets: List[str] = field(default_factory=list)
    target_cfw_targets: List[str] = field(default_factory=list)

    # Hex paths (populated during test_01)
    app_hex_path: Optional[Path] = None
    comms_hex_path: Optional[Path] = None
    modem_fw_path: Optional[Path] = None  # Set in fixture

    # FUOTA state (populated during tests)
    plan_id: Optional[int] = None


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
        from corekinect.test.validation.fuota_client import FuotaClient

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


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture(scope="module")
def is_mock_mode(ctx) -> bool:
    """Detect mock mode from ctx (mtib is None in mock mode)."""
    return ctx.mtib is None


@pytest.fixture(scope="module")
def gate_config(ctx, is_mock_mode) -> GateConfig:
    """Gate test configuration, validated from env and fixture profile.

    Validates:
    - Device ID and SNR are present
    - Modem firmware exists (skipped in mock mode)
    """
    env = _GateEnvConfig()

    # Parse ICCIDs from comma-separated string
    iccids = []
    if env.DEVICE_ICCIDS:
        iccids = [s.strip() for s in env.DEVICE_ICCIDS.split(",") if s.strip()]

    config = GateConfig(
        device_id=env.DEVICE_ID or "",
        device_snr=env.DEVICE_SNR or "",
        device_imei=env.DEVICE_IMEI or "",
        device_iccids=iccids,
        device_type_id=env.DEVICE_TYPE_ID,
        device_variant_id=env.DEVICE_VARIANT_ID,
        source_build=env.FUOTA_SOURCE_BUILD,
        target_build=env.FUOTA_TARGET_BUILD,
        modem_fw_path=_find_modem_firmware(),
    )

    # Get device info from fixture profile if not in env
    if ctx.fixture.profile and ctx.fixture.profile.dut:
        dut = ctx.fixture.profile.dut
        config.device_id = config.device_id or dut.device_id
        config.device_snr = config.device_snr or dut.snr
        config.device_imei = config.device_imei or getattr(dut, "imei", "") or ""
        if not config.device_iccids:
            profile_iccids = getattr(dut, "iccids", []) or []
            config.device_iccids = profile_iccids if isinstance(profile_iccids, list) else []

    # Validate required fields
    assert config.device_id, (
        "DEVICE_ID required (env var or fixture profile dut.device_id)"
    )
    assert config.device_snr, (
        "DEVICE_SNR required (env var or fixture profile dut.snr)"
    )

    # Modem firmware is only required in hardware mode
    if not is_mock_mode:
        assert config.modem_fw_path and config.modem_fw_path.exists(), (
            f"Modem firmware not found in any of: {MODEM_FIRMWARE_PATHS}"
        )

    log.info(
        "Gate config: device=%s snr=%s source=%s target=%s mock=%s",
        config.device_id,
        config.device_snr,
        config.source_build,
        config.target_build,
        is_mock_mode,
    )

    return config


@pytest.fixture(scope="module")
def fuota(ctx, is_mock_mode):
    """FuotaClient for CoreCloud FUOTA API.

    Returns None in mock mode (tests that need FUOTA skip themselves).
    Skips all Gate tests if FUOTA client can't be initialized in hardware mode.
    """
    if is_mock_mode:
        return None

    try:
        from corekinect.test.validation.fuota_client import FuotaClient

        return FuotaClient(api_env="VAL_1_0")
    except Exception as e:
        pytest.skip(f"FuotaClient init failed (missing VAL_1_0_API_* env vars?): {e}")
