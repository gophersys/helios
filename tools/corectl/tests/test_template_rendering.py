"""Template substitution + tree copy — the scaffolding engine ``init`` uses.

We don't boot a backend here; we unit-test ``_render_template_tree`` and
``_substitute`` with a tmp dir so a broken template or a missing token is
caught before it ever ships in a user's project.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from corectl.commands import test as test_cmd


def test_substitute_replaces_known_tokens():
    raw = "hello {{product}} on {{board}}"
    out = test_cmd._substitute(raw, {"product": "alpha", "board": "alpha_b0"})
    assert out == "hello alpha on alpha_b0"


def test_substitute_leaves_unknown_tokens_intact():
    """Better to leave ``{{oops}}`` visible in the output than silently
    erase it — typos would otherwise vanish."""
    raw = "{{product}} — {{oops}}"
    out = test_cmd._substitute(raw, {"product": "alpha"})
    assert out == "alpha — {{oops}}"


def test_substitute_coerces_non_str_values():
    raw = "type_id: {{device_type_id}}"
    out = test_cmd._substitute(raw, {"device_type_id": 7})
    assert out == "type_id: 7"


def test_render_validation_tree_produces_all_five_stages(tmp_path: Path):
    test_cmd._render_template_tree(
        "validation",
        tmp_path,
        {
            "product": "alpha",
            "board": "alpha_b0",
            "board_class": "AlphaB0",
            "fixture_controller": "fixtures.alpha_b0.controller.AlphaB0Fixture",
            "fixture_profile": "fixtures/alpha_b0/fixture.yaml",
            "device_type_id": 2,
            "device_variant_id": 3,
            "pkg_type": "validation",
        },
    )

    assert (tmp_path / "concord.yaml").is_file()
    assert (tmp_path / "conftest.py").is_file()
    assert (tmp_path / "pytest.ini").is_file()
    assert (tmp_path / "pyproject.toml").is_file()

    # Stage dirs land under tests/ to match stages.<name>.directory in concord.yaml.
    assert (tmp_path / "tests" / "__init__.py").is_file()
    for stage in ("smoke", "driver", "integration", "regression", "fuota"):
        stage_dir = tmp_path / "tests" / stage
        assert stage_dir.is_dir(), f"missing stage dir: tests/{stage}"
        assert (stage_dir / "__init__.py").is_file()
        # Every stage ships at least one test_*.py so validate sees a
        # collectable suite immediately.
        assert any(f.name.startswith("test_") for f in stage_dir.iterdir()), \
            f"tests/{stage} has no test_*.py file"

    # Spot-check substitution — the manifest must carry the real slug.
    manifest = (tmp_path / "concord.yaml").read_text()
    assert "slug: alpha" in manifest
    assert "board: alpha_b0" in manifest
    assert "{{" not in manifest, "unsubstituted token leaked into manifest"


def test_render_manufacturing_tree_has_single_stage(tmp_path: Path):
    test_cmd._render_template_tree(
        "manufacturing",
        tmp_path,
        {
            "product": "alpha", "board": "alpha_b0", "board_class": "AlphaB0",
            "fixture_controller": "fixtures.alpha_b0.controller.AlphaB0MfgFixture",
            "fixture_profile": "fixtures/alpha_b0/fixture.yaml",
            "device_type_id": 0, "device_variant_id": 0,
            "pkg_type": "manufacturing",
        },
    )

    stage = tmp_path / "tests" / "stage_01"
    assert stage.is_dir()
    # Three demo tests per the template plan: ADC, flash, POST.
    demo_files = sorted(f.name for f in stage.iterdir() if f.name.startswith("test_"))
    assert len(demo_files) == 3, f"expected 3 demo tests, got {demo_files}"


def test_diff_manifest_flags_board_drift():
    """Changing ``product.board`` must show up as a single drift entry.

    This pins the behaviour of the drift detector against the
    authoritative-fields allowlist — if someone adds a new field in the
    future, they have to decide whether it belongs in sync scope."""
    local = {
        "package": {"type": "validation"},
        "product": {"slug": "alpha", "board": "alpha_b0",
                    "device": {"type_id": 2, "variant_id": 3}},
        "fixture": {
            "controller": "fixtures.alpha_b0.controller.AlphaB0Fixture",
            "profile": "fixtures/alpha_b0/fixture.yaml",
        },
    }
    product = {"slug": "alpha", "id": "p1"}
    # The backend now reports the active revision is b1, not b0.
    revision = {
        "version": "b1", "ckBoardsName": "alpha_b1",
        "deviceType": 2, "deviceVariant": 3,
    }

    diff = test_cmd._diff_manifest(local, product, revision)
    paths = {p for p, _b, _a in diff}
    # Board slug changed → everything derived from it is drifted.
    assert "product.board" in paths
    assert "fixture.controller" in paths
    assert "fixture.profile" in paths
    # Device IDs are unchanged → must NOT appear in drift.
    assert "product.device.type_id" not in paths


def test_diff_manifest_empty_when_in_sync():
    local = {
        "package": {"type": "validation"},
        "product": {"slug": "alpha", "board": "alpha_b0",
                    "device": {"type_id": 2, "variant_id": 3}},
        "fixture": {
            "controller": "fixtures.alpha_b0.controller.AlphaB0Fixture",
            "profile": "fixtures/alpha_b0/fixture.yaml",
        },
    }
    product = {"slug": "alpha", "id": "p1"}
    revision = {"version": "b0", "ckBoardsName": "alpha_b0",
                "deviceType": 2, "deviceVariant": 3}
    assert test_cmd._diff_manifest(local, product, revision) == []
