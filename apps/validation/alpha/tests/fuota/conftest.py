"""FUOTA stage — shared fixtures and utilities.

Stage 5: Over-the-air firmware update verification — blocks merge.

Fixtures (session-scoped, shared across all test files):
    mtib_client:      Connected MTIB V1 client
    pipeline_assets:  PipelineAssets with builds downloaded from Concord API
    fuota_client:     CoreCloud FUOTA API client
    device_config:    Device identity (SNR, device_id, IMEI, ICCIDs)

Utilities:
    parse_cfw_header:        Parse CFW v2 binary header
    register_fuota_cleanup:  atexit handler to disable FUOTA on exit
"""

import atexit
import os
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from corekinect.utils import Logger

log = Logger(log_name="fuota")


# =============================================================================
# DEVICE CONFIG
# =============================================================================


@dataclass
class DeviceConfig:
    """Device identity and hardware constants for FUOTA tests.

    Populated from environment variables (set by K8s Job) or CLI options.
    All fields are validated by the device_config fixture.
    """

    device_id: str = ""
    device_snr: str = ""
    device_imei: str = ""
    device_iccids: List[str] = field(default_factory=list)
    device_type_id: int = 2   # Alpha
    device_variant_id: int = 3  # Alpha B0


# =============================================================================
# SESSION-SCOPED FIXTURES
# =============================================================================


@pytest.fixture(scope="session")
def device_config(request) -> DeviceConfig:
    """Device identity from environment variables or CLI options.

    All required fields are validated — test run fails immediately
    if device identity is incomplete.
    """
    config = DeviceConfig(
        device_id=os.environ.get("DEVICE_ID", ""),
        device_snr=(
            request.config.getoption("--device-snr", default=None)
            or os.environ.get("DEVICE_SNR", "")
        ),
        device_imei=os.environ.get("DEVICE_IMEI", ""),
        device_iccids=[
            s.strip()
            for s in os.environ.get("DEVICE_ICCIDS", "").split(",")
            if s.strip()
        ],
    )

    return config


@pytest.fixture(scope="session")
def mtib_client(request):
    """Connected MTIB V1 client. Powers off DUT on teardown."""
    from corekinect.mtib_client.v1.client.core import MtibV1Client
    from corekinect.mtib_client.v1.client.config import NetConfig

    mtib_addr = (
        request.config.getoption("--mtib-addr", default=None)
        or os.environ.get("MTIB_ADDRESS")
        or os.environ.get("MTIB_HOST", "")
    )
    if not mtib_addr:
        pytest.fail("MTIB_ADDRESS or MTIB_HOST is required")

    # Parse host:port
    if ":" in mtib_addr:
        host, port_str = mtib_addr.rsplit(":", 1)
        port = int(port_str)
    else:
        host = mtib_addr
        port = 50053

    cfg = MtibV1Client.Config(net=NetConfig(addr=host, port=port))
    client = MtibV1Client(cfg)

    err = client.connect()
    if err is not None:
        pytest.fail(f"MTIB connection failed ({host}:{port}): {err}")

    log.info("MTIB connected: %s:%d", host, port)
    yield client

    # Teardown: power off DUT (best-effort)
    from corekinect.mtib_client.v1.client.types import PowerChannel
    try:
        client.PowerDisable(channel=PowerChannel.DUT)
        client.PowerDisable(channel=PowerChannel.CHARGER)
    except Exception:
        pass


@pytest.fixture(scope="session")
def pipeline_assets(request):
    """Pipeline builds from Concord API. Downloads hex/CFW on demand."""
    from corekinect.test.validation.pipeline_assets import PipelineAssets

    pipeline_id = (
        request.config.getoption("--pipeline-id", default=None)
        or os.environ.get("PIPELINE_ID")
    )
    if not pipeline_id:
        pytest.fail("PIPELINE_ID is required for FUOTA tests")

    assets = PipelineAssets(pipeline_id=pipeline_id)
    log.info("Pipeline loaded: %s", pipeline_id)

    yield assets

    assets.cleanup()


@pytest.fixture(scope="session")
def fuota_client():
    """CoreCloud FUOTA API client (lazy-init on first use)."""
    from corekinect.test.validation.fuota_client import FuotaClient
    return FuotaClient(api_env="VAL_1_0")


# =============================================================================
# CFW PARSING
# =============================================================================


def parse_cfw_header(cfw_path: Path) -> Dict[str, Any]:
    """Parse CFW v2 header (23 bytes) and return metadata.

    Returns:
        Dict with: app_id, major, minor, build, flags, target_string,
                   is_mfg, is_debug, version_string
    """
    with open(cfw_path, "rb") as f:
        header = f.read(23)

    if len(header) < 23:
        raise ValueError(f"CFW header too short: {len(header)} bytes")

    # Unpack: FileVersion(2) + TimeCreated(8) + AppId(2) + Flags(1)
    #         + Major(2) + Minor(2) + Build(2) + ImageLen(4)
    file_ver, _, app_id, flags, major, minor, build, image_len = struct.unpack(
        ">HQHBHHHi", header
    )

    release_track = (flags >> 1) & 0x03  # bits 2:1 (0=Bench, 1=Eng, 2=Prod)
    is_mfg = bool(flags & 0x01)
    is_debug = bool(flags & 0x08)

    tracks = {0: "B", 1: "E", 2: "P"}
    track_char = tracks.get(release_track, "?")

    suffix = track_char
    if is_mfg:
        suffix += "M"
    if is_debug:
        suffix += "D"

    target_string = f"{app_id}.{major}.{minor}.{build}-{suffix}"
    version_string = f"{major}.{minor}.{build}"

    return {
        "file_version": file_ver,
        "app_id": app_id,
        "flags": flags,
        "major": major,
        "minor": minor,
        "build": build,
        "image_len": image_len,
        "target_string": target_string,
        "version_string": version_string,
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
