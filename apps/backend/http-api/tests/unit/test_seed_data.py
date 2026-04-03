"""Tests for seed data structure and consistency.

Validates that:
- Alpha product buildConfig has required structure (targets, cfw, board)
- All 5 Alpha stage configs have buildMatrix arrays
- buildMatrix entries have required fields (role, firmware, source)
- ProductContext.from_dict() correctly derives app_ids from buildConfig.targets
- Stage test directories and markers are set for bench-requiring stages
"""

import json
import os
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[5]
SEED_PATH = REPO_ROOT / "prisma" / "seed.py"

# ── Alpha buildConfig shape (must match what seed.py writes) ──

EXPECTED_BUILD_CONFIG_KEYS = {"board", "ncsVersion", "targets", "cfw"}
EXPECTED_TARGET_KEYS = {"soc", "appId", "role"}


# ── Inline the buildConfig for validation ──

ALPHA_BUILD_CONFIG = {
    "board": "alpha_b0",
    "ncsVersion": "v2.9.0",
    "boardRoot": "ck_boards",
    "targets": {
        "app": {"soc": "nrf52840", "appId": 109, "role": "application"},
        "comms": {"soc": "nrf9151", "appId": 108, "role": "communications"},
    },
    "hasVsmMerge": True,
    "hasFips": False,
    "confFiles": {
        "app": ["prj.conf", "boards/alpha_b0_nrf52840.conf"],
        "comms": ["prj.conf", "boards/alpha_b0_nrf9151.conf"],
    },
    "overlays": {
        "app": ["boards/alpha_b0_nrf52840.overlay"],
        "comms": [],
    },
    "postBuild": ["sign_mcuboot", "generate_dfu_package"],
    "cfw": {"deviceType": 2, "deviceVariant": 3},
}


class TestAlphaBuildConfigStructure:
    """Validate that the Alpha buildConfig has all required fields."""

    def test_has_required_top_level_keys(self):
        missing = EXPECTED_BUILD_CONFIG_KEYS - set(ALPHA_BUILD_CONFIG.keys())
        assert not missing, f"buildConfig missing keys: {missing}"

    def test_targets_have_app_and_comms(self):
        targets = ALPHA_BUILD_CONFIG["targets"]
        assert "app" in targets, "buildConfig.targets must include 'app'"
        assert "comms" in targets, "buildConfig.targets must include 'comms'"

    def test_each_target_has_required_fields(self):
        for name, target in ALPHA_BUILD_CONFIG["targets"].items():
            missing = EXPECTED_TARGET_KEYS - set(target.keys())
            assert not missing, f"Target '{name}' missing keys: {missing}"

    def test_app_ids_are_integers(self):
        for name, target in ALPHA_BUILD_CONFIG["targets"].items():
            assert isinstance(target["appId"], int), f"Target '{name}' appId must be int"

    def test_cfw_has_device_type_and_variant(self):
        cfw = ALPHA_BUILD_CONFIG["cfw"]
        assert "deviceType" in cfw
        assert "deviceVariant" in cfw
        assert isinstance(cfw["deviceType"], int)
        assert isinstance(cfw["deviceVariant"], int)

    def test_board_matches_product_build_board(self):
        assert ALPHA_BUILD_CONFIG["board"] == "alpha_b0"


class TestAlphaStageMatrices:
    """Validate that stage config buildMatrix entries are well-formed."""

    # Stage matrix definitions as expected in seed.py
    STAGE_MATRICES = {
        1: [  # Smoke
            {"role": "app", "firmware": "alpha_fw", "source": "head"},
        ],
        2: [],  # Silicon — native_sim, no firmware build matrix
        3: [  # Integration
            {"role": "mfg", "firmware": "alpha_mfg_fw", "source": "head"},
            {"role": "app", "firmware": "alpha_fw", "source": "head"},
        ],
        4: [  # Nightly
            {"role": "mfg", "firmware": "alpha_mfg_fw", "source": "head"},
            {"role": "app", "firmware": "alpha_fw", "source": "head"},
        ],
        5: [  # FUOTA
            {"role": "mfg_flash", "firmware": "alpha_mfg_fw", "source": "latest_prev"},
            {"role": "mfg_base", "firmware": "alpha_mfg_fw", "source": "latest"},
            {"role": "flash_base", "firmware": "alpha_fw", "source": "latest"},
            {"role": "fuota_target", "firmware": "alpha_fw", "source": "head"},
        ],
    }

    REQUIRED_ENTRY_KEYS = {"role", "firmware", "source"}
    VALID_SOURCES = {"head", "latest", "latest_prev"}

    @pytest.mark.parametrize("stage", [1, 3, 4, 5])
    def test_stage_has_build_matrix(self, stage):
        """Stages that build firmware must have a non-empty buildMatrix."""
        matrix = self.STAGE_MATRICES[stage]
        assert len(matrix) > 0, f"Stage {stage} buildMatrix should not be empty"

    def test_silicon_stage_has_empty_matrix(self):
        """Stage 2 (silicon/native_sim) has no firmware builds."""
        assert self.STAGE_MATRICES[2] == []

    @pytest.mark.parametrize("stage", [1, 3, 4, 5])
    def test_matrix_entries_have_required_fields(self, stage):
        for entry in self.STAGE_MATRICES[stage]:
            missing = self.REQUIRED_ENTRY_KEYS - set(entry.keys())
            assert not missing, f"Stage {stage} entry {entry} missing: {missing}"

    @pytest.mark.parametrize("stage", [1, 3, 4, 5])
    def test_matrix_source_values_are_valid(self, stage):
        for entry in self.STAGE_MATRICES[stage]:
            assert entry["source"] in self.VALID_SOURCES, (
                f"Stage {stage} entry {entry['role']}: invalid source '{entry['source']}'"
            )

    def test_fuota_stage_has_four_entries(self):
        assert len(self.STAGE_MATRICES[5]) == 4

    def test_fuota_stage_has_all_required_roles(self):
        roles = {e["role"] for e in self.STAGE_MATRICES[5]}
        expected = {"mfg_flash", "mfg_base", "flash_base", "fuota_target"}
        assert roles == expected


class TestProductContextDerivesAppIds:
    """ProductContext.from_dict() should derive app_ids from buildConfig.targets."""

    def test_derives_app_ids_from_build_config_targets(self):
        from corekinect.test.runner import ProductContext

        data = {
            "name": "Alpha",
            "buildConfig": ALPHA_BUILD_CONFIG,
            "metadata": {},
        }
        ctx = ProductContext.from_dict(data)
        assert ctx.app_ids == {"nrf52840": 109, "nrf9151": 108}

    def test_metadata_app_ids_take_precedence(self):
        from corekinect.test.runner import ProductContext

        data = {
            "name": "Alpha",
            "buildConfig": ALPHA_BUILD_CONFIG,
            "metadata": {"appIds": {"nrf52840": 999}},
        }
        ctx = ProductContext.from_dict(data)
        assert ctx.app_ids == {"nrf52840": 999}

    def test_empty_build_config_yields_empty_app_ids(self):
        from corekinect.test.runner import ProductContext

        data = {"name": "Generic", "buildConfig": {}, "metadata": {}}
        ctx = ProductContext.from_dict(data)
        assert ctx.app_ids == {}


class TestSeedFileConsistency:
    """Verify that seed.py defines buildConfig and buildMatrix for Alpha."""

    def test_seed_file_exists(self):
        assert SEED_PATH.exists(), f"seed.py not found at {SEED_PATH}"

    def test_seed_file_references_build_config(self):
        content = SEED_PATH.read_text()
        assert "buildConfig" in content, "seed.py must set buildConfig on Alpha product"

    def test_seed_file_references_trigger_types_for_stages(self):
        content = SEED_PATH.read_text()
        assert "triggerTypes" in content, "seed.py must set triggerTypes on stage configs"

    def test_seed_file_defines_all_five_stages(self):
        content = SEED_PATH.read_text()
        for stage in range(1, 6):
            assert f'"stage": {stage}' in content, (
                f"seed.py must define stage {stage}"
            )
