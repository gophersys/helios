"""Validation test framework — shared infrastructure for product test apps."""

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
from .firmware import FirmwareAssetManager, FirmwareAsset, get_firmware_path_from_env, PipelineAssets, BuildArtifact, PipelineBuild
from .pytest_integration import (
    requires_capability,
    requires_feature,
    get_required_capabilities,
    get_required_feature,
)

__all__ = [
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
    "PipelineAssets",
    "BuildArtifact",
    "PipelineBuild",
    # Pytest integration
    "requires_capability",
    "requires_feature",
    "get_required_capabilities",
    "get_required_feature",
]
