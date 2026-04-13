"""Additional unit tests for ArtifactResolver — logic paths not covered by test_artifact_resolver.py.

Focuses on:
- ManifestTarget.from_dict() camelCase mapping
- ManifestTarget.get_file_for_type() edge cases
- BuildManifest.from_dict() schema v0 legacy inference
- BuildManifest properties: all_app_ids, device_type_id, device_variant_id, api_env
- _BuildInfo helper methods
- _infer_targets_from_artifacts edge cases
"""

import os
from unittest.mock import patch

import pytest

from corekinect.test.artifact_resolver import (
    BuildManifest,
    ManifestTarget,
    _ArtifactInfo,
    _BuildInfo,
)


# =============================================================================
# ManifestTarget.from_dict
# =============================================================================


class TestManifestTargetFromDict:
    """Test camelCase -> snake_case mapping in ManifestTarget.from_dict()."""

    def test_valid_dict_all_fields(self):
        """Test valid dict all fields."""
        data = {
            "role": "app",
            "processor": "nrf52840",
            "appId": 109,
            "hostType": "HOST_TYPE_NRF52840",
            "jlinkFamily": "NRF52",
            "plaintextHex": "hex/109.0.8.3-BM.hex",
            "encryptedCfw": "cfw/109.0.8.3-BM.cfw",
        }
        target = ManifestTarget.from_dict(data)
        assert target.role == "app"
        assert target.processor == "nrf52840"
        assert target.app_id == 109
        assert target.host_type == "HOST_TYPE_NRF52840"
        assert target.jlink_family == "NRF52"
        assert target.plaintext_hex == "hex/109.0.8.3-BM.hex"
        assert target.encrypted_cfw == "cfw/109.0.8.3-BM.cfw"

    def test_optional_fields_absent(self):
        """plaintextHex and encryptedCfw are optional (may be missing)."""
        data = {
            "role": "app",
            "processor": "nrf52840",
            "appId": 109,
            "hostType": "HOST_TYPE_NRF52840",
            "jlinkFamily": "NRF52",
        }
        target = ManifestTarget.from_dict(data)
        assert target.plaintext_hex is None
        assert target.encrypted_cfw is None

    def test_only_hex_present(self):
        """Test only hex present."""
        data = {
            "role": "comms",
            "processor": "nrf9151",
            "appId": 108,
            "hostType": "HOST_TYPE_NRF9151",
            "jlinkFamily": "NRF91",
            "plaintextHex": "hex/108.0.8.3-BM.hex",
        }
        target = ManifestTarget.from_dict(data)
        assert target.plaintext_hex == "hex/108.0.8.3-BM.hex"
        assert target.encrypted_cfw is None

    def test_only_cfw_present(self):
        """Test only cfw present."""
        data = {
            "role": "comms",
            "processor": "nrf9151",
            "appId": 108,
            "hostType": "HOST_TYPE_NRF9151",
            "jlinkFamily": "NRF91",
            "encryptedCfw": "cfw/108.0.8.3-BM.cfw",
        }
        target = ManifestTarget.from_dict(data)
        assert target.plaintext_hex is None
        assert target.encrypted_cfw == "cfw/108.0.8.3-BM.cfw"

    def test_missing_required_key_raises(self):
        """Missing 'role' key should raise KeyError."""
        data = {
            "processor": "nrf52840",
            "appId": 109,
            "hostType": "HOST_TYPE_NRF52840",
            "jlinkFamily": "NRF52",
        }
        with pytest.raises(KeyError, match="role"):
            ManifestTarget.from_dict(data)

    def test_missing_appid_raises(self):
        """Test missing appid raises."""
        data = {
            "role": "app",
            "processor": "nrf52840",
            "hostType": "HOST_TYPE_NRF52840",
            "jlinkFamily": "NRF52",
        }
        with pytest.raises(KeyError, match="appId"):
            ManifestTarget.from_dict(data)


# =============================================================================
# ManifestTarget.get_file_for_type
# =============================================================================


class TestManifestTargetGetFileForType:
    """Test artifact type -> filename resolution."""

    def _make_target(self, hex_file="app.hex", cfw_file="app.cfw"):
        """ make target."""
        return ManifestTarget(
            role="app",
            processor="nrf52840",
            app_id=109,
            host_type="HOST_TYPE_NRF52840",
            jlink_family="NRF52",
            plaintext_hex=hex_file,
            encrypted_cfw=cfw_file,
        )

    def test_plaintext_hex(self):
        """Test plaintext hex."""
        target = self._make_target()
        assert target.get_file_for_type("plaintextHex") == "app.hex"

    def test_encrypted_cfw(self):
        """Test encrypted cfw."""
        target = self._make_target()
        assert target.get_file_for_type("encryptedCfw") == "app.cfw"

    def test_unknown_type_returns_none(self):
        """Test unknown type returns none."""
        target = self._make_target()
        assert target.get_file_for_type("signedBin") is None

    def test_empty_string_type_returns_none(self):
        """Test empty string type returns none."""
        target = self._make_target()
        assert target.get_file_for_type("") is None

    def test_hex_none_returns_none(self):
        """Test hex none returns none."""
        target = self._make_target(hex_file=None)
        assert target.get_file_for_type("plaintextHex") is None

    def test_cfw_none_returns_none(self):
        """Test cfw none returns none."""
        target = self._make_target(cfw_file=None)
        assert target.get_file_for_type("encryptedCfw") is None


# =============================================================================
# BuildManifest.from_dict — schema v0 (legacy)
# =============================================================================


class TestBuildManifestLegacy:
    """Test legacy schema v0 parsing with artifact name inference."""

    def test_schema_v0_infers_targets_from_artifact_names(self):
        """Schema 0 should infer targets from filenames like 109.0.5.0-BM.hex."""
        data = {
            "schemaVersion": 0,
            "product": "alpha",
            "board": "alpha_b0",
            "version": "0.5.0",
            "variant": "mfg",
            "cfw_track": "BM",
            "built_at": "2026-01-15T10:00:00Z",
        }
        artifact_names = [
            "109.0.5.0-BM.hex",
            "109.0.5.0-BM.cfw",
            "108.0.5.0-BM.hex",
            "108.0.5.0-BM.cfw",
            "build.json",
        ]
        manifest = BuildManifest.from_dict(data, artifact_names=artifact_names)

        assert manifest.schema_version == 0
        assert len(manifest.targets) == 2

        # Targets should be sorted by app_id
        assert manifest.targets[0].app_id == 108  # comms
        assert manifest.targets[1].app_id == 109  # app

        comms = manifest.get_target("comms")
        assert comms is not None
        assert comms.app_id == 108
        assert comms.processor == "nrf9151"
        assert comms.plaintext_hex == "108.0.5.0-BM.hex"
        assert comms.encrypted_cfw == "108.0.5.0-BM.cfw"

        app = manifest.get_target("app")
        assert app is not None
        assert app.app_id == 109
        assert app.processor == "nrf52840"

    def test_schema_v0_hex_only(self):
        """Schema 0 with only hex files, no CFWs."""
        data = {"schemaVersion": 0, "product": "alpha", "version": "0.5.0"}
        artifact_names = ["109.0.5.0-BM.hex", "108.0.5.0-BM.hex"]
        manifest = BuildManifest.from_dict(data, artifact_names=artifact_names)

        assert len(manifest.targets) == 2
        app = manifest.get_target("app")
        assert app.plaintext_hex == "109.0.5.0-BM.hex"
        assert app.encrypted_cfw is None

    def test_schema_v0_unknown_app_id(self):
        """Schema 0 with unknown app ID should still parse with generic role."""
        data = {"schemaVersion": 0, "product": "sigma", "version": "1.0.0"}
        artifact_names = ["201.1.0.0-P.hex", "201.1.0.0-P.cfw"]
        manifest = BuildManifest.from_dict(data, artifact_names=artifact_names)

        assert len(manifest.targets) == 1
        target = manifest.targets[0]
        assert target.app_id == 201
        assert target.role == "target_201"
        assert target.processor == "unknown"
        assert target.host_type == "unknown"
        assert target.jlink_family == "unknown"

    def test_schema_v0_no_artifacts(self):
        """Schema 0 with no artifact names produces empty targets list."""
        data = {"schemaVersion": 0, "product": "alpha", "version": "0.5.0"}
        manifest = BuildManifest.from_dict(data, artifact_names=[])

        assert manifest.schema_version == 0
        assert len(manifest.targets) == 0

    def test_schema_v0_ignores_non_firmware_files(self):
        """Schema 0 should skip build.json, readme, etc."""
        data = {"schemaVersion": 0, "product": "alpha", "version": "0.5.0"}
        artifact_names = [
            "build.json",
            "README.md",
            "109.0.5.0-BM.hex",
            "notes.txt",
        ]
        manifest = BuildManifest.from_dict(data, artifact_names=artifact_names)

        assert len(manifest.targets) == 1
        assert manifest.targets[0].app_id == 109

    def test_schema_v0_cfw_track_fallback(self):
        """Schema 0 uses cfw_track for track field."""
        data = {
            "schemaVersion": 0,
            "product": "alpha",
            "version": "0.5.0",
            "cfw_track": "BM",
        }
        manifest = BuildManifest.from_dict(data, artifact_names=[])
        assert manifest.track == "BM"

    def test_schema_v0_built_at_fallback(self):
        """Schema 0 uses built_at (snake_case) instead of builtAt."""
        data = {
            "schemaVersion": 0,
            "product": "alpha",
            "version": "0.5.0",
            "built_at": "2026-01-15T10:00:00Z",
        }
        manifest = BuildManifest.from_dict(data, artifact_names=[])
        assert manifest.built_at == "2026-01-15T10:00:00Z"

    def test_schema_v0_empty_corecloud(self):
        """Schema 0 manifests have no corecloud section."""
        data = {"schemaVersion": 0, "product": "alpha", "version": "0.5.0"}
        manifest = BuildManifest.from_dict(data, artifact_names=[])
        assert manifest.corecloud == {}
        assert manifest.device_type_id == 0
        assert manifest.device_variant_id == 0
        assert manifest.api_env == ""

    def test_missing_schema_version_treated_as_v0(self):
        """Missing schemaVersion defaults to 0 which requires artifact_names."""
        data = {"product": "alpha", "version": "0.5.0"}
        # Schema 0 without artifact_names returns empty targets
        manifest = BuildManifest.from_dict(data, artifact_names=[])
        assert manifest.schema_version == 0


# =============================================================================
# BuildManifest — unsupported schema
# =============================================================================


class TestBuildManifestUnsupportedSchema:
    """Test error on unsupported schema version."""

    def test_schema_v2_raises(self):
        """Test schema v2 raises."""
        data = {"schemaVersion": 2, "product": "alpha"}
        with pytest.raises(ValueError, match="Unsupported.*schema.*2"):
            BuildManifest.from_dict(data)

    def test_schema_v99_raises(self):
        """Test schema v99 raises."""
        data = {"schemaVersion": 99}
        with pytest.raises(ValueError, match="Unsupported.*schema.*99"):
            BuildManifest.from_dict(data)

    def test_negative_schema_raises(self):
        """Test negative schema raises."""
        data = {"schemaVersion": -1}
        with pytest.raises(ValueError, match="Unsupported.*schema.*-1"):
            BuildManifest.from_dict(data)


# =============================================================================
# BuildManifest.get_target
# =============================================================================


class TestBuildManifestGetTarget:
    """Test get_target() role lookup."""

    @pytest.fixture
    def manifest(self):
        """Manifest."""
        data = {
            "schemaVersion": 1,
            "product": "alpha",
            "version": "0.8.3",
            "targets": [
                {
                    "role": "app",
                    "processor": "nrf52840",
                    "appId": 109,
                    "hostType": "HOST_TYPE_NRF52840",
                    "jlinkFamily": "NRF52",
                    "plaintextHex": "hex/109.hex",
                },
                {
                    "role": "comms",
                    "processor": "nrf9151",
                    "appId": 108,
                    "hostType": "HOST_TYPE_NRF9151",
                    "jlinkFamily": "NRF91",
                    "plaintextHex": "hex/108.hex",
                },
            ],
        }
        return BuildManifest.from_dict(data)

    def test_get_existing_role(self, manifest):
        """Test get existing role."""
        target = manifest.get_target("app")
        assert target is not None
        assert target.app_id == 109

    def test_get_comms_role(self, manifest):
        """Test get comms role."""
        target = manifest.get_target("comms")
        assert target is not None
        assert target.app_id == 108

    def test_missing_role_returns_none(self, manifest):
        """Test missing role returns none."""
        assert manifest.get_target("modem") is None

    def test_empty_role_returns_none(self, manifest):
        """Test empty role returns none."""
        assert manifest.get_target("") is None

    def test_case_sensitive_lookup(self, manifest):
        """Role lookup is case-sensitive."""
        assert manifest.get_target("App") is None
        assert manifest.get_target("APP") is None


# =============================================================================
# BuildManifest properties
# =============================================================================


class TestBuildManifestProperties:
    """Test all_app_ids, device_type_id, device_variant_id, api_env."""

    def test_all_app_ids_dual_target(self):
        """Test all app ids dual target."""
        data = {
            "schemaVersion": 1,
            "targets": [
                {"role": "app", "processor": "nrf52840", "appId": 109,
                 "hostType": "X", "jlinkFamily": "X"},
                {"role": "comms", "processor": "nrf9151", "appId": 108,
                 "hostType": "X", "jlinkFamily": "X"},
            ],
        }
        manifest = BuildManifest.from_dict(data)
        assert manifest.all_app_ids == {108, 109}

    def test_all_app_ids_single_target(self):
        """Test all app ids single target."""
        data = {
            "schemaVersion": 1,
            "targets": [
                {"role": "app", "processor": "nrf52840", "appId": 201,
                 "hostType": "X", "jlinkFamily": "X"},
            ],
        }
        manifest = BuildManifest.from_dict(data)
        assert manifest.all_app_ids == {201}

    def test_all_app_ids_empty(self):
        """Test all app ids empty."""
        data = {"schemaVersion": 1, "targets": []}
        manifest = BuildManifest.from_dict(data)
        assert manifest.all_app_ids == set()

    def test_device_type_id(self):
        """Test device type id."""
        data = {
            "schemaVersion": 1,
            "targets": [],
            "corecloud": {"deviceTypeId": 5, "deviceVariantId": 2, "apiEnv": "prod"},
        }
        manifest = BuildManifest.from_dict(data)
        assert manifest.device_type_id == 5

    def test_device_variant_id(self):
        """Test device variant id."""
        data = {
            "schemaVersion": 1,
            "targets": [],
            "corecloud": {"deviceTypeId": 5, "deviceVariantId": 2, "apiEnv": "prod"},
        }
        manifest = BuildManifest.from_dict(data)
        assert manifest.device_variant_id == 2

    def test_api_env(self):
        """Test api env."""
        data = {
            "schemaVersion": 1,
            "targets": [],
            "corecloud": {"deviceTypeId": 5, "deviceVariantId": 2, "apiEnv": "prod"},
        }
        manifest = BuildManifest.from_dict(data)
        assert manifest.api_env == "prod"

    def test_corecloud_missing_returns_defaults(self):
        """Missing corecloud section should return zero/empty defaults."""
        data = {"schemaVersion": 1, "targets": []}
        manifest = BuildManifest.from_dict(data)
        assert manifest.device_type_id == 0
        assert manifest.device_variant_id == 0
        assert manifest.api_env == ""

    def test_corecloud_partial_fields(self):
        """Partial corecloud dict returns defaults for missing keys."""
        data = {
            "schemaVersion": 1,
            "targets": [],
            "corecloud": {"deviceTypeId": 3},
        }
        manifest = BuildManifest.from_dict(data)
        assert manifest.device_type_id == 3
        assert manifest.device_variant_id == 0
        assert manifest.api_env == ""

    def test_raw_dict_preserved(self):
        """The original dict should be preserved in _raw."""
        data = {
            "schemaVersion": 1,
            "product": "alpha",
            "version": "0.8.3",
            "targets": [],
            "customField": "hello",
        }
        manifest = BuildManifest.from_dict(data)
        assert manifest._raw is data
        assert manifest._raw["customField"] == "hello"


# =============================================================================
# _BuildInfo helpers
# =============================================================================


class TestBuildInfoHelpers:
    """Test _BuildInfo dataclass helper methods."""

    def _make_build_info(self, artifacts=None):
        """ make build info."""
        return _BuildInfo(
            id="build-123",
            product="alpha",
            variant="mfg",
            status="SUCCESS",
            matrix_label="mfg_base",
            matrix_index=0,
            version_string="0.8.3",
            artifacts=artifacts or [],
        )

    def test_has_manifest_true(self):
        """Test has manifest true."""
        artifacts = [
            _ArtifactInfo(id="1", name="build.json", storage_key="k", size_bytes=100, checksum="x"),
            _ArtifactInfo(id="2", name="app.hex", storage_key="k2", size_bytes=200, checksum="y"),
        ]
        build = self._make_build_info(artifacts)
        assert build.has_manifest is True

    def test_has_manifest_false(self):
        """Test has manifest false."""
        artifacts = [
            _ArtifactInfo(id="2", name="app.hex", storage_key="k2", size_bytes=200, checksum="y"),
        ]
        build = self._make_build_info(artifacts)
        assert build.has_manifest is False

    def test_has_manifest_empty(self):
        """Test has manifest empty."""
        build = self._make_build_info([])
        assert build.has_manifest is False

    def test_get_manifest_artifact(self):
        """Test get manifest artifact."""
        manifest_art = _ArtifactInfo(id="1", name="build.json", storage_key="k", size_bytes=100, checksum="x")
        build = self._make_build_info([manifest_art])
        result = build.get_manifest_artifact()
        assert result is manifest_art

    def test_get_manifest_artifact_missing(self):
        """Test get manifest artifact missing."""
        build = self._make_build_info([
            _ArtifactInfo(id="2", name="app.hex", storage_key="k2", size_bytes=200, checksum="y"),
        ])
        assert build.get_manifest_artifact() is None

    def test_find_artifact_by_name(self):
        """Test find artifact by name."""
        art = _ArtifactInfo(id="1", name="109.hex", storage_key="k", size_bytes=100, checksum="x")
        build = self._make_build_info([art])
        assert build.find_artifact_by_name("109.hex") is art

    def test_find_artifact_by_name_not_found(self):
        """Test find artifact by name not found."""
        build = self._make_build_info([
            _ArtifactInfo(id="1", name="109.hex", storage_key="k", size_bytes=100, checksum="x"),
        ])
        assert build.find_artifact_by_name("999.hex") is None

    def test_find_artifacts_by_extension(self):
        """Test find artifacts by extension."""
        arts = [
            _ArtifactInfo(id="1", name="109.hex", storage_key="k", size_bytes=100, checksum="x"),
            _ArtifactInfo(id="2", name="108.hex", storage_key="k2", size_bytes=200, checksum="y"),
            _ArtifactInfo(id="3", name="109.cfw", storage_key="k3", size_bytes=300, checksum="z"),
            _ArtifactInfo(id="4", name="build.json", storage_key="k4", size_bytes=50, checksum="w"),
        ]
        build = self._make_build_info(arts)

        hexes = build.find_artifacts_by_extension(".hex")
        assert len(hexes) == 2
        assert all(a.name.endswith(".hex") for a in hexes)

        cfws = build.find_artifacts_by_extension(".cfw")
        assert len(cfws) == 1
        assert cfws[0].name == "109.cfw"

        jsons = build.find_artifacts_by_extension(".json")
        assert len(jsons) == 1

        zips = build.find_artifacts_by_extension(".zip")
        assert len(zips) == 0


# =============================================================================
# BuildManifest.from_dict — schema v1 edge cases
# =============================================================================


class TestBuildManifestSchemaV1EdgeCases:
    """Edge cases specific to schema v1 parsing."""

    def test_no_targets_key(self):
        """Schema v1 with missing targets key returns empty list."""
        data = {"schemaVersion": 1, "product": "alpha", "version": "0.5.0"}
        manifest = BuildManifest.from_dict(data)
        assert manifest.targets == []

    def test_empty_targets_list(self):
        """Test empty targets list."""
        data = {"schemaVersion": 1, "product": "alpha", "targets": []}
        manifest = BuildManifest.from_dict(data)
        assert manifest.targets == []
        assert manifest.all_app_ids == set()

    def test_signing_field(self):
        """Signing info should be preserved."""
        data = {
            "schemaVersion": 1,
            "targets": [],
            "signing": {"algorithm": "ed25519", "keyId": "prod-key-1"},
        }
        manifest = BuildManifest.from_dict(data)
        assert manifest.signing is not None
        assert manifest.signing["algorithm"] == "ed25519"

    def test_signing_absent(self):
        """Test signing absent."""
        data = {"schemaVersion": 1, "targets": []}
        manifest = BuildManifest.from_dict(data)
        assert manifest.signing is None

    def test_release_track_field(self):
        """Test release track field."""
        data = {
            "schemaVersion": 1,
            "targets": [],
            "releaseTrack": "production",
        }
        manifest = BuildManifest.from_dict(data)
        assert manifest.release_track == "production"

    def test_all_string_fields_default_empty(self):
        """All optional string fields default to empty string."""
        data = {"schemaVersion": 1, "targets": []}
        manifest = BuildManifest.from_dict(data)
        assert manifest.product == ""
        assert manifest.board == ""
        assert manifest.version == ""
        assert manifest.variant == ""
        assert manifest.track == ""
        assert manifest.release_track == ""
        assert manifest.ncs_version == ""
        assert manifest.commit_sha == ""
        assert manifest.branch == ""
        assert manifest.built_at == ""
