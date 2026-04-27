"""Tests for the unified test-package resolver + scheduling gates."""

import types
from datetime import datetime, timezone

import pytest


@pytest.fixture
def svc_mock_db():
    """Fresh mock DB for service-level tests (not patched into module global)."""
    from tests.conftest import MockPrismaClient
    return MockPrismaClient()


def _make_pkg(**kwargs):
    defaults = {
        "id": "pkg-1",
        "productId": "prod-1",
        "type": "VALIDATION",
        "status": "RELEASED",
        "version": "1.0.0",
        "createdAt": datetime(2026, 4, 1, tzinfo=timezone.utc),
    }
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


def _make_fixture(**kwargs):
    defaults = {
        "id": "fix-1",
        "purpose": "RELEASE",
        "status": "AVAILABLE",
    }
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


def _make_stage_config(**kwargs):
    defaults = {
        "id": "stage-1",
        "productId": "prod-1",
        "type": "VALIDATION",
        "stage": 1,
        "releasedTestPackageId": "pkg-1",
    }
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


# ---------------------------------------------------------------------------
# resolve_test_package
# ---------------------------------------------------------------------------


class TestResolveExplicitId:
    """Explicit id lookup — exact match, product check, type check."""

    def test_explicit_id_returns_package(self, svc_mock_db):
        from src.api.v2.products.test_package_resolver import resolve_test_package

        pkg = _make_pkg(id="pkg-explicit")
        svc_mock_db.testpackage.find_unique.return_value = pkg

        tp, err = resolve_test_package(
            svc_mock_db, "prod-1", "VALIDATION", explicit_id="pkg-explicit",
        )

        assert err is None
        assert tp is pkg
        svc_mock_db.testpackage.find_unique.assert_called_once_with(
            where={"id": "pkg-explicit"}
        )

    def test_explicit_id_not_found_returns_404(self, svc_mock_db):
        from src.api.v2.products.test_package_resolver import resolve_test_package

        svc_mock_db.testpackage.find_unique.return_value = None

        tp, err = resolve_test_package(
            svc_mock_db, "prod-1", "VALIDATION", explicit_id="missing",
        )

        assert tp is None
        assert err is not None
        # err is a Flask error tuple — (response, status)
        body, status = err
        assert status == 404

    def test_explicit_id_wrong_product_rejects(self, svc_mock_db):
        from src.api.v2.products.test_package_resolver import resolve_test_package

        pkg = _make_pkg(productId="other-product")
        svc_mock_db.testpackage.find_unique.return_value = pkg

        tp, err = resolve_test_package(
            svc_mock_db, "prod-1", "VALIDATION", explicit_id="pkg-1",
        )

        assert tp is None
        _, status = err
        assert status == 400

    def test_explicit_id_wrong_type_rejects(self, svc_mock_db):
        from src.api.v2.products.test_package_resolver import resolve_test_package

        pkg = _make_pkg(type="MANUFACTURING")
        svc_mock_db.testpackage.find_unique.return_value = pkg

        tp, err = resolve_test_package(
            svc_mock_db, "prod-1", "VALIDATION", explicit_id="pkg-1",
        )

        assert tp is None
        _, status = err
        assert status == 400


class TestResolveExplicitVersion:
    def test_explicit_version_returns_match(self, svc_mock_db):
        from src.api.v2.products.test_package_resolver import resolve_test_package

        pkg = _make_pkg(version="2.1.0")
        svc_mock_db.testpackage.find_first.return_value = pkg

        tp, err = resolve_test_package(
            svc_mock_db, "prod-1", "VALIDATION", explicit_version="2.1.0",
        )

        assert err is None
        assert tp is pkg
        svc_mock_db.testpackage.find_first.assert_called_once_with(
            where={"productId": "prod-1", "type": "VALIDATION", "version": "2.1.0"}
        )

    def test_explicit_version_not_found_returns_404(self, svc_mock_db):
        from src.api.v2.products.test_package_resolver import resolve_test_package

        svc_mock_db.testpackage.find_first.return_value = None

        tp, err = resolve_test_package(
            svc_mock_db, "prod-1", "VALIDATION", explicit_version="9.9.9",
        )

        assert tp is None
        _, status = err
        assert status == 404


class TestResolveByMode:
    def test_released_mode_filters_status(self, svc_mock_db):
        from src.api.v2.products.test_package_resolver import resolve_test_package

        pkg = _make_pkg(status="RELEASED")
        svc_mock_db.testpackage.find_first.return_value = pkg

        tp, err = resolve_test_package(svc_mock_db, "prod-1", "VALIDATION", mode="RELEASED")

        assert err is None
        assert tp is pkg
        call = svc_mock_db.testpackage.find_first.call_args
        assert call.kwargs["where"]["status"] == "RELEASED"

    def test_dev_mode_filters_status(self, svc_mock_db):
        from src.api.v2.products.test_package_resolver import resolve_test_package

        pkg = _make_pkg(status="DEVELOPMENT")
        svc_mock_db.testpackage.find_first.return_value = pkg

        tp, err = resolve_test_package(svc_mock_db, "prod-1", "VALIDATION", mode="DEV")

        assert err is None
        assert tp is pkg
        call = svc_mock_db.testpackage.find_first.call_args
        assert call.kwargs["where"]["status"] == "DEVELOPMENT"

    def test_any_mode_does_not_filter_status(self, svc_mock_db):
        from src.api.v2.products.test_package_resolver import resolve_test_package

        pkg = _make_pkg(status="DEVELOPMENT")
        svc_mock_db.testpackage.find_first.return_value = pkg

        tp, err = resolve_test_package(svc_mock_db, "prod-1", "VALIDATION", mode="ANY")

        assert err is None
        assert tp is pkg
        call = svc_mock_db.testpackage.find_first.call_args
        assert "status" not in call.kwargs["where"]

    def test_mode_returns_none_when_no_candidate(self, svc_mock_db):
        from src.api.v2.products.test_package_resolver import resolve_test_package

        svc_mock_db.testpackage.find_first.return_value = None

        tp, err = resolve_test_package(svc_mock_db, "prod-1", "VALIDATION", mode="RELEASED")

        # Mode-driven path: returning None is not an error — caller decides.
        assert tp is None
        assert err is None


# ---------------------------------------------------------------------------
# assert_validation_stage_runnable
# ---------------------------------------------------------------------------


class TestAssertValidationStageRunnable:
    def test_no_stage_config_blocks(self):
        from src.api.v2.products.test_package_resolver import assert_validation_stage_runnable

        err = assert_validation_stage_runnable(None)

        assert err is not None
        _, status = err
        assert status == 409

    def test_no_released_package_blocks(self):
        from src.api.v2.products.test_package_resolver import assert_validation_stage_runnable

        stage = _make_stage_config(releasedTestPackageId=None)

        err = assert_validation_stage_runnable(stage)

        assert err is not None
        _, status = err
        assert status == 409

    def test_bound_package_passes(self):
        from src.api.v2.products.test_package_resolver import assert_validation_stage_runnable

        stage = _make_stage_config(releasedTestPackageId="pkg-1")

        err = assert_validation_stage_runnable(stage)

        assert err is None


# ---------------------------------------------------------------------------
# assert_purpose_match
# ---------------------------------------------------------------------------


class TestAssertPurposeMatch:
    """Asymmetric gate: RELEASE fixtures are production-locked, DEV rigs are sandboxes.

    Matrix:
      DEV pkg     + DEV  fixture → ALLOW (dev iteration)
      DEV pkg     + RELEASE fixture → BLOCK (production protection)
      RELEASED pkg + DEV  fixture → ALLOW (verify a release on the same rig)
      RELEASED pkg + RELEASE fixture → ALLOW (the floor)
    """

    def test_dev_package_on_dev_fixture_passes(self):
        from src.api.v2.products.test_package_resolver import assert_purpose_match

        pkg = _make_pkg(status="DEVELOPMENT")
        fix = _make_fixture(purpose="DEV")

        assert assert_purpose_match(pkg, fix) is None

    def test_released_package_on_release_fixture_passes(self):
        from src.api.v2.products.test_package_resolver import assert_purpose_match

        pkg = _make_pkg(status="RELEASED")
        fix = _make_fixture(purpose="RELEASE")

        assert assert_purpose_match(pkg, fix) is None

    def test_released_package_on_dev_fixture_passes(self):
        """Dev rigs accept released code — common 'verify the release' workflow."""
        from src.api.v2.products.test_package_resolver import assert_purpose_match

        pkg = _make_pkg(status="RELEASED")
        fix = _make_fixture(purpose="DEV")

        assert assert_purpose_match(pkg, fix) is None

    def test_dev_package_on_release_fixture_blocks(self):
        """The one direction that's still locked — keeps dev code off the floor."""
        from src.api.v2.products.test_package_resolver import assert_purpose_match

        pkg = _make_pkg(status="DEVELOPMENT")
        fix = _make_fixture(purpose="RELEASE")

        err = assert_purpose_match(pkg, fix)

        assert err is not None
        _, status = err
        assert status == 409
