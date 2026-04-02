"""Standardized firmware assets per validation stage.

Provides a typed layer on top of ArtifactResolver so tests access
build artifacts by label + role instead of ad-hoc string lookups.

Each validation stage defines which firmware builds it requires
(STAGE_REQUIRED_LABELS). StageAssets validates that all required
builds are present before tests run.

Usage:
    from corekinect.test.stage_assets import StageAssets

    assets = StageAssets.from_pipeline(
        pipeline_id="run-42",
        stage="fuota",
        api_url="https://concord.local",
        api_key="ck_run_...",
    )

    # Typed access by label
    mfg = assets.by_label("MFG_BASE")
    app_hex = mfg.hex("app")         # local path, downloaded lazily
    comms_hex = mfg.hex("comms")

    # Convenience shortcuts
    mfg = assets.mfg()               # same as by_label("MFG_BASE")
    modem = assets.modem_zip()        # modem firmware path

    # FUOTA transitions
    source = assets.by_label("FUT_VERBOSE_A")
    target = assets.by_label("FUT_VERBOSE_B")
    cfws = target.cfws()              # all CFW files for FUOTA delivery
    ver = target.version_string("app")  # "109.0.8.3-BM"

    # Stage validation
    missing = assets.missing_labels()  # [] if all present
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from corekinect.test.artifact_resolver import ArtifactResolver

from corekinect.errors import ConfigError
from corekinect.stages import Stage, get_required_labels as _get_required_labels
from corekinect.utils import Logger

log = Logger(log_name="stage_assets")


# Backward compat — derived from the shared source of truth.
# Prefer importing get_required_labels() from corekinect.validation.stage_defs directly.
STAGE_REQUIRED_LABELS: Dict[str, List[str]] = {
    stage.value: _get_required_labels(stage) for stage in Stage
}


# =============================================================================
# BuildAsset — typed wrapper around a single build label
# =============================================================================


class BuildAsset:
    """A single build's resolved artifacts.

    Wraps an ArtifactResolver label with typed accessors. Downloads
    are lazy — artifacts are fetched from MinIO on first access, then
    cached as local file paths.

    This class is not instantiated directly. Use StageAssets.by_label().
    """

    def __init__(self, label: str, resolver: "ArtifactResolver"):
        self._label = label
        self._resolver = resolver
        self._manifest_cache = None

    @property
    def label(self) -> str:
        """Build matrix label (e.g., 'MFG_BASE', 'FUT_VERBOSE_A')."""
        return self._label

    def hex(self, target: str) -> str:
        """Download and return local path to plaintext hex for a target role.

        Args:
            target: Target role — "app" or "comms".

        Returns:
            Local file path to the downloaded hex file.

        Raises:
            ConfigError: If no hex artifact exists for this target.
        """
        path = self._resolver.get_artifact(
            self._label, role=target, artifact_type="plaintextHex",
        )
        if not path:
            raise ConfigError(
                f"No plaintext hex for label={self._label}, target={target}"
            )
        return path

    def cfw(self, target: str) -> str:
        """Download and return local path to encrypted CFW for a target role.

        Args:
            target: Target role — "app" or "comms".

        Returns:
            Local file path to the downloaded CFW file.

        Raises:
            ConfigError: If no CFW artifact exists for this target.
        """
        path = self._resolver.get_artifact(
            self._label, role=target, artifact_type="encryptedCfw",
        )
        if not path:
            raise ConfigError(
                f"No encrypted CFW for label={self._label}, target={target}"
            )
        return path

    def cfws(self) -> List[str]:
        """Download and return all CFW paths for this build.

        Returns all encrypted CFW files across all targets (app + comms).
        Used for FUOTA upload where all processor CFWs are needed.

        Returns:
            List of local file paths.
        """
        return self._resolver.get_artifacts(
            self._label, artifact_type="encryptedCfw",
        )

    def version(self) -> str:
        """Build version string (e.g., '0.8.3').

        Returns:
            Semantic version string from the build manifest.
        """
        return self._resolver.get_version(self._label)

    def version_string(self, target: str) -> str:
        """Full CK version string for a target (e.g., '109.0.8.3-BM').

        Combines the target's app ID with the build version and track.

        Args:
            target: Target role — "app" or "comms".

        Returns:
            CoreKinect version string used in FUOTA plan targets.
        """
        build_manifest = self.manifest()
        target_info = build_manifest.get_target(target)
        if target_info is None:
            raise ConfigError(
                f"No target '{target}' in manifest for label={self._label}. "
                f"Available: {[mt.role for mt in build_manifest.targets]}"
            )

        return f"{target_info.app_id}.{build_manifest.version}-{build_manifest.track}"

    def target_strings(self) -> List[str]:
        """All CK version strings for all targets.

        Returns:
            List of version strings like ['108.0.8.3-BM', '109.0.8.3-BM'].
        """
        build_manifest = self.manifest()
        return [
            f"{target_info.app_id}.{build_manifest.version}-{build_manifest.track}"
            for target_info in build_manifest.targets
            if target_info.encrypted_cfw  # Only targets that produce CFWs
        ]

    def manifest(self):
        """Parsed build.json manifest (BuildManifest).

        Cached after first access.
        """
        if self._manifest_cache is None:
            self._manifest_cache = self._resolver.get_manifest(self._label)
        return self._manifest_cache

    def targets(self):
        """All build targets (List[ManifestTarget])."""
        return self.manifest().targets

    def target(self, role: str):
        """Single target by role. Raises if not found.

        Args:
            role: Target role — "app" or "comms".

        Returns:
            ManifestTarget for the given role.
        """
        target_info = self.manifest().get_target(role)
        if target_info is None:
            raise ConfigError(
                f"No target '{role}' in label={self._label}. "
                f"Available: {[mt.role for mt in self.manifest().targets]}"
            )
        return target_info

    def app_ids(self) -> Set[int]:
        """All app IDs in this build."""
        return self.manifest().all_app_ids

    def __repr__(self) -> str:
        return f"BuildAsset(label={self._label!r})"


# =============================================================================
# StageAssets — all builds for a validation stage
# =============================================================================


class StageAssets:
    """Resolved firmware assets for a validation stage.

    Wraps an ArtifactResolver with stage-aware validation and typed
    access. Checks that all required build labels are present and
    their builds succeeded.

    Args:
        resolver: Loaded ArtifactResolver with pipeline data.
        stage: Stage name ("smoke", "silicon", "integration", "nightly", "fuota").
        strict: If True, constructor raises if required labels are missing.
        required_labels: Override the default required labels for this stage.
            Use this for products with non-standard stage build requirements.
    """

    def __init__(
        self,
        resolver,
        stage: str,
        strict: bool = True,
        required_labels: Optional[List[str]] = None,
    ):
        self._resolver = resolver
        self._stage = stage
        self._required = required_labels or STAGE_REQUIRED_LABELS.get(stage, [])
        self._assets: Dict[str, BuildAsset] = {}

        # Index available builds by matrixLabel
        for label, build_info in resolver.builds.items():
            self._assets[label] = BuildAsset(label=label, resolver=resolver)

        if strict:
            self.validate()

    @property
    def stage(self) -> str:
        """Stage name."""
        return self._stage

    # ── Label access ──

    def by_label(self, label: str) -> BuildAsset:
        """Get build by matrix label.

        Args:
            label: Matrix label (e.g., "MFG_BASE", "FUT_VERBOSE_A").

        Returns:
            BuildAsset wrapper for the requested build.

        Raises:
            KeyError: If label not found in pipeline.
        """
        if label not in self._assets:
            available = sorted(self._assets.keys())
            raise KeyError(
                f"Build label '{label}' not found in pipeline. "
                f"Available: {available}"
            )
        return self._assets[label]

    # ── Convenience shortcuts ──

    def mfg(self) -> BuildAsset:
        """Shortcut for MFG_BASE — manufacturing firmware."""
        return self.by_label("MFG_BASE")

    def mfg_bump(self) -> BuildAsset:
        """Shortcut for MFG_BUMP — version-bumped manufacturing firmware."""
        return self.by_label("MFG_BUMP")

    def app_debug(self) -> BuildAsset:
        """Shortcut for APP_DEBUG — debug application firmware."""
        return self.by_label("APP_DEBUG")

    def app_release(self) -> BuildAsset:
        """Shortcut for APP_RELEASE — release application firmware."""
        return self.by_label("APP_RELEASE")

    def modem_zip(self) -> Optional[str]:
        """Modem firmware local path.

        Tries the MFG_BASE build manifest first, then falls back to
        pipeline trigger data.

        Returns:
            Local path to modem firmware zip, or None if unavailable.
        """
        # Try manifest-embedded modem firmware
        if "MFG_BASE" in self._assets:
            path = self._resolver.get_modem_firmware("MFG_BASE")
            if path:
                return path

        # Fall back to trigger data
        return self._resolver.get_modem_firmware_from_trigger()

    # ── Validation ──

    @property
    def labels(self) -> List[str]:
        """All available build labels in this pipeline."""
        return sorted(self._assets.keys())

    @property
    def required_labels(self) -> List[str]:
        """Labels required by the stage definition."""
        return list(self._required)

    def missing_labels(self) -> List[str]:
        """Labels required but not present in the pipeline.

        Returns:
            List of missing label names. Empty if all present.
        """
        return [l for l in self._required if l not in self._assets]

    def failed_labels(self) -> List[str]:
        """Labels present but with non-success build status.

        Returns:
            List of labels whose builds are not SUCCESS or CACHED.
        """
        failed = []
        for label in self._required:
            if label not in self._assets:
                continue
            build = self._resolver.builds.get(label)
            if build and hasattr(build, "status"):
                if build.status not in ("SUCCESS", "CACHED"):
                    failed.append(label)
        return failed

    def validate(self) -> None:
        """Validate that all required labels are present and builds succeeded.

        Raises:
            ConfigError: If any required labels are missing or builds failed.
        """
        missing = self.missing_labels()
        if missing:
            raise ConfigError(
                f"Stage '{self._stage}' is missing required builds: {missing}. "
                f"Available: {self.labels}. "
                f"The pipeline may not have been created with matrix_mode='{self._stage}'."
            )

        failed = self.failed_labels()
        if failed:
            statuses = {}
            for label in failed:
                build = self._resolver.builds.get(label)
                statuses[label] = getattr(build, "status", "UNKNOWN")
            raise ConfigError(
                f"Stage '{self._stage}' has failed builds: {statuses}. "
                f"All required builds must be SUCCESS or CACHED."
            )

    # ── Factory ──

    @classmethod
    def from_pipeline(
        cls,
        pipeline_id: str,
        stage: str,
        api_url: str,
        api_key: str,
        strict: bool = True,
        required_labels: Optional[List[str]] = None,
    ) -> "StageAssets":
        """Create StageAssets from a pipeline ID.

        Loads the ArtifactResolver, fetches pipeline data, and validates
        that all required builds for the stage are present.

        Args:
            pipeline_id: Concord pipeline run ID.
            stage: Validation stage name.
            api_url: Concord API base URL.
            api_key: API key for authentication.
            strict: If True, raises on missing/failed labels.
            required_labels: Override default required labels.

        Returns:
            Populated StageAssets instance.
        """
        from corekinect.test.artifact_resolver import ArtifactResolver

        resolver = ArtifactResolver(
            pipeline_id=pipeline_id,
            api_url=api_url,
            api_key=api_key,
        )

        log.info(
            "StageAssets loaded: pipeline=%s, stage=%s, builds=%d",
            pipeline_id, stage, len(resolver.builds),
        )

        return cls(
            resolver=resolver,
            stage=stage,
            strict=strict,
            required_labels=required_labels,
        )

    def cleanup(self) -> None:
        """Clean up downloaded artifacts."""
        self._resolver.cleanup()

    def __repr__(self) -> str:
        return (
            f"StageAssets(stage={self._stage!r}, "
            f"labels={self.labels}, "
            f"missing={self.missing_labels()})"
        )
