"""Validation test framework for product test apps.

Shared infrastructure for hardware validation: MTIB control, UART capture,
power profiling, artifact resolution, FUOTA orchestration, and pytest
integration. Product apps (e.g., Alpha B0) build on top of this.

    from corekinect.test.context import TestContext
    from corekinect.test.stage_assets import StageAssets
    from corekinect.test.pytest_integration import requires_capability
"""

__version__ = "0.1.0"

# ── Core ──
from .errors import (
    CloudError,
    ConfigError,
    FirmwareError,
    HardwareError,
    ValidationError,
)
from .errors import TimeoutError as ValidationTimeoutError
from .stages import Stage, STAGE_NUMBERS, STAGE_NAMES
from .assertions import (
    assert_cloud_message,
    assert_current_in_range,
    assert_flash_success,
    assert_fuota_progress,
    assert_powered,
)
from .timing import COMMON, CommonTiming, timeout, wait_with_progress
from .cfw import parse_cfw_header

# ── Hardware / Profiles (deprecated — use product-specific fixtures) ──
# Legacy imports kept for backward compatibility with existing code.
# New product test apps should NOT import FixtureController or FixtureProfile
# from corekinect.test. Instead, each product defines its own fixture module.

# ── Artifacts & Storage ──
from .artifact_resolver import ArtifactResolver, BuildManifest, ManifestTarget
from .stage_assets import STAGE_REQUIRED_LABELS, BuildAsset, StageAssets
from .firmware import FirmwareAsset, FirmwareAssetManager, get_firmware_path_from_env
from .artifact_writer import (
    POWER_FLAG_HAS_CH0,
    POWER_FLAG_HAS_CH1,
    POWER_FLAG_HAS_JOULESCOPE,
    POWER_HEADER_SIZE,
    POWER_MAGIC,
    ArtifactInfo,
    ArtifactWriter,
    PowerSample,
)

# ── FUOTA & Cloud ──
from .fuota_orchestrator import FuotaOrchestrator, personalize_with_retry
from .version_detector import DEFAULT_VERSION_PATTERNS, BootVersionDetector

# ── Multi-Slot ──
from .slot import FixtureContext, SlotContext

# ── Pytest Integration ──
from .pytest_integration import (
    get_required_capabilities,
    get_required_feature,
    requires_capability,
)

# Note: CapabilityNotAvailable is imported from profiles (defined there),
# re-exported from programmable_fixture for backward compat. Import once above.

__all__ = [
    # ── Core ──
    "CloudError",
    "ConfigError",
    "FirmwareError",
    "HardwareError",
    "ValidationError",
    "ValidationTimeoutError",
    "Stage",
    "STAGE_NUMBERS",
    "STAGE_NAMES",
    "assert_cloud_message",
    "assert_current_in_range",
    "assert_flash_success",
    "assert_fuota_progress",
    "assert_powered",
    "COMMON",
    "CommonTiming",
    "timeout",
    "wait_with_progress",
    "parse_cfw_header",
    # ── Artifacts & Storage ──
    "ArtifactInfo",
    "ArtifactResolver",
    "ArtifactWriter",
    "BuildAsset",
    "BuildManifest",
    "FirmwareAsset",
    "FirmwareAssetManager",
    "ManifestTarget",
    "POWER_FLAG_HAS_CH0",
    "POWER_FLAG_HAS_CH1",
    "POWER_FLAG_HAS_JOULESCOPE",
    "POWER_HEADER_SIZE",
    "POWER_MAGIC",
    "PowerSample",
    "STAGE_REQUIRED_LABELS",
    "StageAssets",
    "get_firmware_path_from_env",
    # ── FUOTA & Cloud ──
    "BootVersionDetector",
    "DEFAULT_VERSION_PATTERNS",
    "FuotaOrchestrator",
    "personalize_with_retry",
    # ── Multi-Slot ──
    "FixtureContext",
    "SlotContext",
    # ── Pytest Integration ──
    "get_required_capabilities",
    "get_required_feature",
    "requires_capability",
]
