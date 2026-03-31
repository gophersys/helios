"""Validation test framework — shared infrastructure for product test apps.

This library provides everything a product validation app needs:

**Core**:
- Stage enum and metadata (stages.py)
- Generic hardware assertions (assertions.py)
- Base timing utilities (timing.py)
- CFW binary header parsing (cfw.py)

**Hardware**:
- Capability/Feature system for test gating (profiles.py)
- Hardware abstraction via MTIB (fixture_controller.py)
- Programmable test stub (programmable_fixture.py)
- UART capture and demuxing (uart_demuxer.py)
- Power measurement (power_profiler.py)

**Artifacts & Storage**:
- Build manifest parsing (artifact_resolver.py)
- Stage-aware asset resolution (stage_assets.py)
- Firmware lifecycle management (firmware.py)
- MinIO artifact persistence (artifact_writer.py)

**FUOTA & Cloud**:
- High-level FUOTA workflow (fuota_orchestrator.py)
- UART boot version capture (version_detector.py)
- CoreCloud device polling (cloud_client.py)
- CoreCloud FUOTA API (fuota_client.py)
- Device provisioning (device_personalizer.py)

**Pytest Integration**:
- Concord API result reporting (reporter.py)
- Fail-fast sequential plugin (sequential.py)
- Capability-based test decorators (pytest_integration.py)

**Orchestration**:
- Unified test runner (runner.py)
- Test session context (context.py)
"""

# ── Core ──
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

# ── Hardware / Profiles ──
from .profiles import (
    ButtonConfig,
    Capability,
    ChargerRelayConfig,
    DEVICE_PROFILES,
    DeviceProfile,
    DutConfig,
    FEATURE_REQUIREMENTS,
    Feature,
    FixtureProfile,
    LedSensorConfig,
    MotionConfig,
    NfcReaderConfig,
    PeltierConfig,
    PowerConfig,
    PpgSimulatorConfig,
    ValidationConfig,
    get_device_profile,
)
from .fixture_controller import FixtureController
from .programmable_fixture import (
    CapabilityNotAvailable,
    FixtureBuilder,
    FixturePresets,
    ProgrammableFixture,
)

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

# ── Pytest Integration ──
from .pytest_integration import (
    get_required_capabilities,
    get_required_feature,
    requires_capability,
    requires_feature,
)

# Note: CapabilityNotAvailable is imported from profiles (defined there),
# re-exported from programmable_fixture for backward compat. Import once above.

__all__ = [
    # ── Core ──
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
    # ── Hardware / Profiles ──
    "ButtonConfig",
    "Capability",
    "CapabilityNotAvailable",
    "ChargerRelayConfig",
    "DEVICE_PROFILES",
    "DeviceProfile",
    "DutConfig",
    "FEATURE_REQUIREMENTS",
    "Feature",
    "FixtureBuilder",
    "FixtureController",
    "FixturePresets",
    "FixtureProfile",
    "LedSensorConfig",
    "MotionConfig",
    "NfcReaderConfig",
    "PeltierConfig",
    "PowerConfig",
    "PpgSimulatorConfig",
    "ProgrammableFixture",
    "ValidationConfig",
    "get_device_profile",
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
    # ── Pytest Integration ──
    "get_required_capabilities",
    "get_required_feature",
    "requires_capability",
    "requires_feature",
]
