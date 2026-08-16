"""Stage-aware firmware asset resolution.

Typed layer on ArtifactResolver so tests access build artifacts by
label + role instead of ad-hoc string lookups.

    assets = StageAssets.from_build_run("run-42", "fuota", api_url, api_key)
    app_hex = assets.hex("app", "debug")           # downloads lazily from MinIO
    app, comms = assets.hex_pair("debug")           # both processors at once
    cfws = assets.by_label("fut_app_base_b").cfws() # escape hatch
    missing = assets.missing_labels()               # [] if all present
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from corekinect.errors import ConfigError
from corekinect.stages import Stage, get_required_labels as _get_required_labels
from corekinect.test.artifact_resolver import ArtifactResolver
from corekinect.utils import Logger

log = Logger(log_name="stage_assets")


# =============================================================================
# BuildAsset — typed wrapper around a single build label
# =============================================================================


class BuildAsset:
    """Typed access to a single build's artifacts (hex, CFW, manifest).

    Downloads are lazy -- fetched from MinIO on first access, then cached.
    Don't instantiate directly; use StageAssets.by_label().
    """

    def __init__(self, label: str, resolver: ArtifactResolver):
        self._label = label
        self._resolver = resolver
        self._manifest_cache = None

    @property
    def label(self) -> str:
        """Build matrix label (e.g., 'smoke_app_debug', 'fut_app_base_a')."""
        return self._label

    def hex(self, target: str) -> str:
        """Download and return local path to plaintext hex.

        Args:
            target: "app" or "comms".

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
        """Download and return local path to encrypted CFW.

        Args:
            target: "app" or "comms".

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
        """Download and return all CFW paths (app + comms) for FUOTA upload."""
        return self._resolver.get_artifacts(
            self._label, artifact_type="encryptedCfw",
        )

    def version(self) -> str:
        """Return build version string (e.g., '0.8.3')."""
        return self._resolver.get_version(self._label)

    def version_string(self, target: str) -> str:
        """Return full CK version string (e.g., '109.0.8.3-BM') for FUOTA plan targets.

        Args:
            target: "app" or "comms".
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
        """Return CK version strings for all CFW-producing targets."""
        build_manifest = self.manifest()
        return [
            f"{target_info.app_id}.{build_manifest.version}-{build_manifest.track}"
            for target_info in build_manifest.targets
            if target_info.encrypted_cfw  # Only targets that produce CFWs
        ]

    def manifest(self):
        """Return parsed build.json manifest. Cached after first access."""
        if self._manifest_cache is None:
            self._manifest_cache = self._resolver.get_manifest(self._label)
        return self._manifest_cache

    def targets(self):
        """Return all build targets."""
        return self.manifest().targets

    def target(self, role: str):
        """Return single ManifestTarget by role. Raises ConfigError if not found."""
        target_info = self.manifest().get_target(role)
        if target_info is None:
            raise ConfigError(
                f"No target '{role}' in label={self._label}. "
                f"Available: {[mt.role for mt in self.manifest().targets]}"
            )
        return target_info

    def app_ids(self) -> Set[int]:
        """Return all app IDs in this build."""
        return self.manifest().all_app_ids

    def __repr__(self) -> str:
        return f"BuildAsset(label={self._label!r})"


# =============================================================================
# StageAssets — all builds for a validation stage
# =============================================================================


class StageAssets:
    """All firmware builds for a validation stage, with validation.

    Checks that all required build labels are present and their builds
    succeeded. Access builds via the clean API: hex(), cfw(), hex_pair(),
    or the escape hatch by_label() for direct label access.

    Args:
        strict: If True, raises on missing or failed required labels.
        required_labels: Override defaults for non-standard products.
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
        # Derive required labels from the canonical stage definitions
        if required_labels is not None:
            self._required = required_labels
        else:
            try:
                self._required = _get_required_labels(Stage(stage))
            except (ValueError, KeyError):
                self._required = []
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
        """Return BuildAsset for a matrix label. Raises KeyError if not found."""
        if label not in self._assets:
            available = sorted(self._assets.keys())
            raise KeyError(
                f"Build label '{label}' not found in build run. "
                f"Available: {available}"
            )
        return self._assets[label]

    # ── Clean API ──

    @property
    def stage_prefix(self) -> str:
        """Auto-detect the stage prefix from available labels.

        All labels in a stage share a prefix: smoke_, driver_, int_, reg_, fut_, mfg_
        Detects by finding the common prefix of all non-modem labels.
        """
        non_modem = [k for k in self._assets.keys() if k != "modem_fw"]
        if not non_modem:
            return ""
        for prefix in ("smoke", "driver", "int", "reg", "fut", "mfg"):
            if any(k.startswith(prefix + "_") for k in non_modem):
                return prefix
        return ""

    @property
    def available_variants(self) -> List[str]:
        """Which variants are available in this stage: ['debug', 'release']."""
        variants: Set[str] = set()
        for label in self._assets:
            if label == "modem_fw":
                continue
            label_check = label.lower()
            if "debug" in label_check or "base" in label_check:
                variants.add("debug")
            elif "release" in label_check or "quiet" in label_check:
                variants.add("release")
        return sorted(variants)

    def hex(self, role: str, variant: str = "debug", suffix: str = "") -> str:
        """Get hex file path for a processor role and variant.

        Resolves label: {PREFIX}_{ROLE}_{VARIANT}{_SUFFIX}
        Then downloads the hex file.

        Args:
            role: "app" or "comms"
            variant: "debug" or "release"
            suffix: optional suffix like "A" or "B" (for FUOTA transitions)

        Examples:
            stage_assets.hex("app", "debug")      -> smoke_app_debug -> downloads hex
            stage_assets.hex("comms", "release")   -> mfg_comms_release -> downloads hex
            stage_assets.hex("app", "debug", "A")  -> fut_app_base_a -> downloads hex
        """
        label = self._resolve_label(role, variant, suffix)
        asset = self.by_label(label)
        return asset.hex(role)

    def cfw(self, role: str, variant: str = "debug", suffix: str = "") -> str:
        """Get CFW file path for a processor role and variant.

        Only available for stages that produce CFW (regression, FUOTA).
        """
        label = self._resolve_label(role, variant, suffix)
        asset = self.by_label(label)
        return asset.cfw(role)

    def hex_pair(self, variant: str = "debug") -> Tuple[str, str]:
        """Get (app_hex, comms_hex) for a variant.

        Convenience for flash tests that need both processors.

        Returns:
            (app_hex_path, comms_hex_path)
        """
        return self.hex("app", variant), self.hex("comms", variant)

    def _resolve_label(self, role: str, variant: str, suffix: str = "") -> str:
        """Construct the matrix label from role + variant + optional suffix.

        Pattern: {PREFIX}_{ROLE}_{VARIANT_KEY}{_SUFFIX}

        For FUOTA: debug maps to BASE, release maps to QUIET
        For others: debug maps to DEBUG, release maps to RELEASE
        """
        prefix = self.stage_prefix
        role_lower = role.lower()  # app, comms

        if prefix == "fut":
            # FUOTA uses base (debug/verbose) and quiet (release/no-logging)
            variant_key = "base" if variant == "debug" else "quiet"
        else:
            variant_key = variant.lower()  # debug, release

        if suffix:
            label = f"{prefix}_{role_lower}_{variant_key}_{suffix.lower()}"
        else:
            label = f"{prefix}_{role_lower}_{variant_key}"

        return label

    def modem_zip(self) -> Optional[str]:
        """Modem firmware local path.

        Resolution order:
        1. AssetSet.modemFirmware (new model — preferred)
        2. Build manifest modem firmware (legacy — from build run)
        3. Deprecated: trigger data modem firmware

        Returns:
            Local path to modem firmware zip, or None if unavailable.
        """
        # 1. Try from AssetSet modem firmware reference (new path)
        modem_path = self._resolver.get_modem_from_asset_set()
        if modem_path:
            return modem_path

        # 2. Try from build manifest (legacy — from build run) — use any available label
        for label in sorted(self._assets.keys()):
            if label == "modem_fw":
                continue
            path = self._resolver.get_modem_firmware(label)
            if path:
                return path

        # 3. Deprecated fallback
        return self._resolver.get_modem_firmware_from_trigger()

    # ── Validation ──

    @property
    def labels(self) -> List[str]:
        """All available build labels in this build run."""
        return sorted(self._assets.keys())

    @property
    def required_labels(self) -> List[str]:
        """Labels required by the stage definition."""
        return list(self._required)

    def missing_labels(self) -> List[str]:
        """Return labels required but not present. Empty if all present."""
        return [l for l in self._required if l not in self._assets]

    def failed_labels(self) -> List[str]:
        """Return labels whose builds are not SUCCESS or CACHED."""
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
        """Raise ConfigError if any required labels are missing or builds failed."""
        missing = self.missing_labels()
        if missing:
            raise ConfigError(
                f"Stage '{self._stage}' is missing required builds: {missing}. "
                f"Available: {self.labels}. "
                f"The build run may not have been created with matrix_mode='{self._stage}'."
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
    def from_build_run(
        cls,
        build_run_id: str,
        stage: str,
        api_url: str,
        api_key: str,
        strict: bool = True,
        required_labels: Optional[List[str]] = None,
    ) -> "StageAssets":
        """Create from a build run ID. Fetches builds and validates labels."""
        resolver = ArtifactResolver(
            build_run_id=build_run_id,
            api_url=api_url,
            api_key=api_key,
        )

        log.info(
            "StageAssets loaded: build_run=%s, stage=%s, builds=%d",
            build_run_id, stage, len(resolver.builds),
        )

        return cls(
            resolver=resolver,
            stage=stage,
            strict=strict,
            required_labels=required_labels,
        )

    def cleanup(self) -> None:
        """Remove downloaded temp files."""
        self._resolver.cleanup()

    def __repr__(self) -> str:
        return (
            f"StageAssets(stage={self._stage!r}, "
            f"labels={self.labels}, "
            f"missing={self.missing_labels()})"
        )
