"""Validation test framework — shared infrastructure for product test apps.

This library provides everything a product validation app needs:

- **Stages**: Stage enum and metadata (stages.py)
- **Assertions**: Generic hardware assertions (assertions.py)
- **Timing**: Base timing utilities and helpers (timing.py)
- **Sequential**: Fail-fast pytest plugin for ordered test classes (sequential.py)
- **CFW**: CFW binary header parsing (cfw.py)
- **FUOTA Orchestrator**: High-level FUOTA workflow operations (fuota_orchestrator.py)
- **Version Detector**: UART boot version capture and verification (version_detector.py)
- **Profiles**: Capability/Feature system for test gating (profiles.py)
- **Fixture Controller**: Hardware abstraction via MTIB (fixture_controller.py)
- **Reporter**: Concord API result reporting pytest plugin (reporter.py)
- **Test Context**: Unified session object (context.py)
- **Artifact Management**: Build manifest parsing, firmware lifecycle (artifact_resolver.py, firmware.py)
"""

from .stages import Stage, STAGE_NUMBERS, STAGE_NAMES
from .assertions import (
    assert_powered,
    assert_current_in_range,
    assert_cloud_message,
    assert_flash_success,
    assert_fuota_progress,
)
from .timing import CommonTiming, COMMON, timeout, wait_with_progress
from .cfw import parse_cfw_header
from .fuota_orchestrator import FuotaOrchestrator, personalize_with_retry
from .version_detector import BootVersionDetector, DEFAULT_VERSION_PATTERNS
from .artifact_writer import (
    ArtifactWriter,
    PowerSample,
    ArtifactInfo,
    POWER_FLAG_HAS_CH0,
    POWER_FLAG_HAS_CH1,
    POWER_FLAG_HAS_JOULESCOPE,
    POWER_HEADER_SIZE,
    POWER_MAGIC,
)
from .profiles import (
    Capability,
    Feature,
    FEATURE_REQUIREMENTS,
    FixtureProfile,
    DeviceProfile,
    ValidationConfig,
    PowerConfig,
    DutConfig,
    ButtonConfig,
    PpgSimulatorConfig,
    PeltierConfig,
    ChargerRelayConfig,
    LedSensorConfig,
    NfcReaderConfig,
    MotionConfig,
    DEVICE_PROFILES,
    get_device_profile,
)
from .programmable_fixture import (
    ProgrammableFixture,
    FixtureBuilder,
    FixturePresets,
    CapabilityNotAvailable,
)
from .fixture_controller import FixtureController
from .firmware import FirmwareAssetManager, FirmwareAsset, get_firmware_path_from_env
from .artifact_resolver import ArtifactResolver, BuildManifest, ManifestTarget
from .pytest_integration import (
    requires_capability,
    requires_feature,
    get_required_capabilities,
    get_required_feature,
)

__all__ = [
    # Stages
    "Stage",
    "STAGE_NUMBERS",
    "STAGE_NAMES",
    # Assertions
    "assert_powered",
    "assert_current_in_range",
    "assert_cloud_message",
    "assert_flash_success",
    "assert_fuota_progress",
    # Timing
    "CommonTiming",
    "COMMON",
    "timeout",
    "wait_with_progress",
    # CFW parsing
    "parse_cfw_header",
    # FUOTA orchestration
    "FuotaOrchestrator",
    "personalize_with_retry",
    # Version detection
    "BootVersionDetector",
    "DEFAULT_VERSION_PATTERNS",
    # Artifact writer
    "ArtifactWriter",
    "PowerSample",
    "ArtifactInfo",
    "POWER_FLAG_HAS_CH0",
    "POWER_FLAG_HAS_CH1",
    "POWER_FLAG_HAS_JOULESCOPE",
    "POWER_HEADER_SIZE",
    "POWER_MAGIC",
    # Profiles
    "Capability",
    "Feature",
    "FEATURE_REQUIREMENTS",
    "FixtureProfile",
    "DeviceProfile",
    "ValidationConfig",
    "PowerConfig",
    "DutConfig",
    "ButtonConfig",
    "PpgSimulatorConfig",
    "PeltierConfig",
    "ChargerRelayConfig",
    "LedSensorConfig",
    "NfcReaderConfig",
    "MotionConfig",
    "DEVICE_PROFILES",
    "get_device_profile",
    # Programmable fixture
    "ProgrammableFixture",
    "FixtureBuilder",
    "FixturePresets",
    "CapabilityNotAvailable",
    # Real hardware controller
    "FixtureController",
    # Firmware asset management
    "FirmwareAssetManager",
    "FirmwareAsset",
    "get_firmware_path_from_env",
    # Artifact resolver
    "ArtifactResolver",
    "BuildManifest",
    "ManifestTarget",
    # Pytest integration
    "requires_capability",
    "requires_feature",
    "get_required_capabilities",
    "get_required_feature",
]
