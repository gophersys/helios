"""Live integration tests for ArtifactResolver against staging API.

Verifies ArtifactResolver works with real pipeline data from staging,
covering both old-schema builds (no manifest) and new-schema builds
(with build.json manifest).

Requires environment variables:
    CONCORD_API_URL  - Staging API base URL (e.g., https://staging.concord.local)
    CONCORD_API_KEY  - API key with read access

Usage:
    CONCORD_API_URL=https://staging.concord.local \
    CONCORD_API_KEY=ck_run_test_... \
    python3 -m pytest tests/integration/test_artifact_resolver_live.py -m integration -v
"""

import os

import pytest

from corekinect.test.artifact_resolver import ArtifactResolver, BuildManifest, ManifestTarget
from corekinect.utils import Logger

log = Logger(log_name="test.artifact_resolver_live")

# Pipeline IDs from staging
PIPELINE_OLD_SCHEMA = "cmn83nd3l0001pdbpj83itlx7"  # 4 builds, no build.json manifests
PIPELINE_NEW_SCHEMA = "cmn85e7ib"  # New schema with build.json manifests

integration = pytest.mark.integration


def _skip_if_no_creds():
    """Skip test if staging credentials are not configured."""
    if not os.environ.get("CONCORD_API_URL") or not os.environ.get("CONCORD_API_KEY"):
        pytest.skip("CONCORD_API_URL and CONCORD_API_KEY required for integration tests")


def _make_resolver(pipeline_id: str) -> ArtifactResolver:
    """Create an ArtifactResolver for a staging pipeline."""
    return ArtifactResolver(
        pipeline_id=pipeline_id,
        api_url=os.environ["CONCORD_API_URL"],
        api_key=os.environ["CONCORD_API_KEY"],
    )


# =============================================================================
# Old-schema pipeline (no manifests) — must error
# =============================================================================


@integration
class TestOldSchemaPipeline:
    """Old-schema pipeline builds have no build.json manifests.

    ArtifactResolver must raise ValueError for every manifest-dependent
    operation.
    """

    @pytest.fixture(autouse=True)
    def setup(self):
        _skip_if_no_creds()
        self.resolver = _make_resolver(PIPELINE_OLD_SCHEMA)
        yield
        self.resolver.cleanup()

    def test_pipeline_fetches_builds(self):
        """Resolver fetches builds from old-schema pipeline."""
        builds = self.resolver.builds
        assert len(builds) > 0, "Expected at least one build"
        log.info("Old-schema pipeline has %d builds: %s", len(builds), list(builds.keys()))

    def test_builds_have_no_manifest(self):
        """Old-schema builds should not have build.json manifests."""
        for label, build in self.resolver.builds.items():
            assert not build.has_manifest, (
                f"Build '{label}' unexpectedly has a manifest"
            )

    def test_get_manifest_raises(self):
        """get_manifest() raises ValueError on builds without manifests."""
        labels = list(self.resolver.builds.keys())
        assert len(labels) > 0
        with pytest.raises(ValueError, match="no build.json manifest"):
            self.resolver.get_manifest(labels[0])

    def test_get_artifact_raises(self):
        """get_artifact() raises ValueError on builds without manifests."""
        labels = list(self.resolver.builds.keys())
        assert len(labels) > 0
        with pytest.raises(ValueError, match="no build.json manifest"):
            self.resolver.get_artifact(labels[0], role="app", artifact_type="plaintextHex")

    def test_get_artifacts_raises(self):
        """get_artifacts() raises ValueError on builds without manifests."""
        labels = list(self.resolver.builds.keys())
        assert len(labels) > 0
        with pytest.raises(ValueError, match="no build.json manifest"):
            self.resolver.get_artifacts(labels[0], artifact_type="encryptedCfw")

    def test_summary_shows_no_manifest(self):
        """summary() should show [NO MANIFEST] for old builds."""
        text = self.resolver.summary()
        assert "[NO MANIFEST]" in text


# =============================================================================
# New-schema pipeline (with manifests) — must work
# =============================================================================


@integration
class TestNewSchemaPipeline:
    """New-schema pipeline builds include build.json manifests.

    ArtifactResolver should parse manifests and resolve artifacts.
    """

    @pytest.fixture(autouse=True)
    def setup(self):
        _skip_if_no_creds()
        self.resolver = _make_resolver(PIPELINE_NEW_SCHEMA)
        yield
        self.resolver.cleanup()

    def test_pipeline_fetches_builds(self):
        """Resolver fetches builds from new-schema pipeline."""
        builds = self.resolver.builds
        assert len(builds) > 0, "Expected at least one build"
        log.info("New-schema pipeline has %d builds: %s", len(builds), list(builds.keys()))

    def test_builds_have_manifest(self):
        """New-schema builds should have build.json manifests."""
        has_any = False
        for label, build in self.resolver.builds.items():
            if build.status in ("SUCCESS", "CACHED") and build.has_manifest:
                has_any = True
        assert has_any, "Expected at least one build with a manifest"

    def test_get_manifest_schema_version(self):
        """get_manifest() returns manifest with schemaVersion 1."""
        label = self._first_manifest_label()
        manifest = self.resolver.get_manifest(label)
        assert isinstance(manifest, BuildManifest)
        assert manifest.schema_version == 1

    def test_manifest_has_targets(self):
        """Manifest targets[] array is non-empty."""
        label = self._first_manifest_label()
        manifest = self.resolver.get_manifest(label)
        assert len(manifest.targets) > 0, "Expected at least one target"

    def test_manifest_target_fields(self):
        """Each target has required fields: role, processor, appId, hostType."""
        label = self._first_manifest_label()
        manifest = self.resolver.get_manifest(label)
        for target in manifest.targets:
            assert isinstance(target, ManifestTarget)
            assert target.role, f"Target missing role: {target}"
            assert target.processor, f"Target missing processor: {target}"
            assert isinstance(target.app_id, int), f"Target appId not int: {target}"
            assert target.app_id > 0, f"Target appId must be positive: {target}"
            assert target.host_type, f"Target missing hostType: {target}"
            assert target.jlink_family, f"Target missing jlinkFamily: {target}"
            log.info(
                "Target: role=%s processor=%s appId=%d hostType=%s",
                target.role, target.processor, target.app_id, target.host_type,
            )

    def test_manifest_all_app_ids(self):
        """all_app_ids returns a set of positive integers."""
        label = self._first_manifest_label()
        manifest = self.resolver.get_manifest(label)
        app_ids = manifest.all_app_ids
        assert len(app_ids) > 0
        for aid in app_ids:
            assert isinstance(aid, int) and aid > 0
        log.info("App IDs: %s", app_ids)

    def test_get_targets(self):
        """get_targets() returns list of ManifestTarget."""
        label = self._first_manifest_label()
        targets = self.resolver.get_targets(label)
        assert isinstance(targets, list)
        assert len(targets) > 0
        assert all(isinstance(t, ManifestTarget) for t in targets)

    def test_get_target_by_role(self):
        """get_target() finds a target by role."""
        label = self._first_manifest_label()
        targets = self.resolver.get_targets(label)
        role = targets[0].role
        target = self.resolver.get_target(label, role)
        assert target is not None
        assert target.role == role

    def test_get_target_unknown_role(self):
        """get_target() returns None for unknown role."""
        label = self._first_manifest_label()
        target = self.resolver.get_target(label, "nonexistent_role")
        assert target is None

    def test_get_artifact_hex_handles_null_path(self):
        """get_artifact() handles targets where plaintextHex is null.

        Some builds may have targets with null file paths (e.g., CFW-only
        builds that don't produce hex files). The resolver should raise
        ValueError with a clear message.
        """
        label = self._first_manifest_label()
        manifest = self.resolver.get_manifest(label)

        for target in manifest.targets:
            if target.plaintext_hex is None:
                with pytest.raises(ValueError, match="no 'plaintextHex' artifact"):
                    self.resolver.get_artifact(label, role=target.role, artifact_type="plaintextHex")
                log.info("Correctly rejected null plaintextHex for role=%s", target.role)
                return

        # All targets have hex paths — try downloading one
        target = manifest.targets[0]
        if target.plaintext_hex:
            path = self.resolver.get_artifact(label, role=target.role, artifact_type="plaintextHex")
            assert os.path.exists(path), f"Downloaded hex not found at {path}"
            assert os.path.getsize(path) > 0, "Downloaded hex is empty"
            log.info("Downloaded hex: %s (%d bytes)", path, os.path.getsize(path))

    def test_get_artifact_cfw_handles_null_path(self):
        """get_artifact() handles targets where encryptedCfw is null."""
        label = self._first_manifest_label()
        manifest = self.resolver.get_manifest(label)

        for target in manifest.targets:
            if target.encrypted_cfw is None:
                with pytest.raises(ValueError, match="no 'encryptedCfw' artifact"):
                    self.resolver.get_artifact(label, role=target.role, artifact_type="encryptedCfw")
                log.info("Correctly rejected null encryptedCfw for role=%s", target.role)
                return

        # All targets have CFW paths — try downloading one
        target = manifest.targets[0]
        if target.encrypted_cfw:
            path = self.resolver.get_artifact(label, role=target.role, artifact_type="encryptedCfw")
            assert os.path.exists(path), f"Downloaded CFW not found at {path}"
            assert os.path.getsize(path) > 0, "Downloaded CFW is empty"
            log.info("Downloaded CFW: %s (%d bytes)", path, os.path.getsize(path))

    def test_get_artifacts_encryptedCfw(self):
        """get_artifacts() returns CFW files for all targets that have them."""
        label = self._first_manifest_label()
        manifest = self.resolver.get_manifest(label)

        # Check if any targets have CFW paths
        has_cfw = any(t.encrypted_cfw for t in manifest.targets)
        if not has_cfw:
            pytest.skip("No targets have encryptedCfw paths")

        paths = self.resolver.get_artifacts(label, artifact_type="encryptedCfw")
        assert len(paths) > 0, "Expected at least one CFW file"
        for p in paths:
            assert os.path.exists(p)
            assert os.path.getsize(p) > 0
        log.info("Downloaded %d CFW files", len(paths))

    def test_get_version(self):
        """get_version() returns a non-empty version string."""
        label = self._first_manifest_label()
        version = self.resolver.get_version(label)
        assert version, "Expected non-empty version"
        log.info("Version: %s", version)

    def test_summary_shows_manifest(self):
        """summary() shows [manifest] for builds with manifests."""
        text = self.resolver.summary()
        assert "[manifest]" in text
        log.info("Summary:\n%s", text)

    def _first_manifest_label(self) -> str:
        """Find the first build with a manifest. Skip if none found."""
        for label, build in self.resolver.builds.items():
            if build.status in ("SUCCESS", "CACHED") and build.has_manifest:
                return label
        pytest.skip("No builds with manifests found in pipeline")
