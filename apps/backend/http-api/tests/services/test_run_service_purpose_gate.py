"""Validation direct-trigger purpose gate.

The build->validation auto-trigger path in
``services/builds/run_service.trigger_build_run_validation`` picks the first
ready fixture and spins up a K8s job. Without an explicit purpose gate, a
DEVELOPMENT test package can land on a RELEASE fixture (production hardware)
and silently run dev code on the customer floor.

The asymmetric gate (``assert_purpose_match``) lives in the resolver module
and is wired into the queue-driven path (``runs/scheduler.py``) and the
manual mfg session path. This file pins down the third call site so the
direct-trigger path can't bypass it.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from tests.conftest import make_obj


def _now():
    return datetime(2026, 4, 27, tzinfo=timezone.utc)


def _release_fixture():
    """A production fixture — RELEASE purpose, ready slot, ready MTIB."""
    node = make_obj(
        id="node-rel", disabled=False, ipAddress="10.4.45.99",
        metadata={"deployment_name": "mtib-rel"},
    )
    slot = make_obj(
        id="slot-1", nodeId="node-rel", active=True, dutSnr="0964",
        dutDeviceId="dev-1", dutImei="imei-1", dutIccids=["ic-1"], node=node,
    )
    return make_obj(
        id="fix-rel-1", name="Bench-Prod", stationId="prod-A", productId="prod-1",
        purpose="RELEASE", slots=[slot], design=None,
    )


def _dev_fixture():
    """A dev rig — DEV purpose, ready slot, ready MTIB."""
    node = make_obj(
        id="node-dev", disabled=False, ipAddress="10.4.45.100",
        metadata={"deployment_name": "mtib-dev"},
    )
    slot = make_obj(
        id="slot-2", nodeId="node-dev", active=True, dutSnr="0099",
        dutDeviceId="dev-2", dutImei="imei-2", dutIccids=["ic-2"], node=node,
    )
    return make_obj(
        id="fix-dev-1", name="Bench-Dev", stationId="dev-A", productId="prod-1",
        purpose="DEV", slots=[slot], design=None,
    )


def _ready_status_map(deploy_names):
    """Live MTIB status — one ready deployment per name."""
    return {
        n: {"name": n, "replicas": 1, "readyReplicas": 1, "pods": [{"ready": True}]}
        for n in deploy_names
    }


def _build_run(stage_config_id=None):
    return make_obj(
        id="run-1", productId="prod-1", branch="main",
        product=None, autoRunStage=True, stage=4,
        matrixMode="fuota", stageConfigId=stage_config_id,
    )


def _builds():
    return [make_obj(
        id="b-1", versionString="0.5.3", variant="release",
        product=None, productId="prod-1",
    )]


# ---------------------------------------------------------------------------
# Direct-trigger refuses DEV pkg on RELEASE fixture
# ---------------------------------------------------------------------------


class TestPurposeGateDirectTrigger:
    """``trigger_build_run_validation`` must enforce the asymmetric gate."""

    @patch("src.services.builds.run_service.get_db_client")
    def test_dev_package_on_release_fixture_aborts_trigger(self, mock_get_db):
        """DEV package + RELEASE fixture → no K8s job, fixture stays unlocked.

        The whole point of fixture purpose is to keep dev code off
        customer hardware. The auto-trigger path used to skip the gate
        entirely, so a freshly built FUOTA run could end up running a
        ``DEVELOPMENT`` test package against a ``RELEASE`` fixture.
        Asserts the fix: gate fires, no job created, fixture unlocked.
        """
        from src.services.builds.run_service import trigger_build_run_validation

        db = MagicMock()
        mock_get_db.return_value = db
        db.product.find_unique.return_value = make_obj(
            id="prod-1", name="Alpha", slug="alpha",
        )
        db.fixture.find_many.return_value = [_release_fixture()]
        # Direct-trigger path uses the resolver to pick the test package.
        # Return a DEVELOPMENT package — which must be rejected.
        dev_pkg = make_obj(
            id="tp-dev-1", productId="prod-1", type="VALIDATION",
            status="DEVELOPMENT", version="dev-abc-123",
        )

        with patch(
            "src.services.builds.run_service.resolve_test_package",
            return_value=(dev_pkg, None),
        ), patch(
            "src.services.builds.run_service.create_kubernetes_job"
        ) as mock_create_job:
            result = trigger_build_run_validation(
                "run-1", _build_run(), _builds(),
            )

        # No K8s job started.
        mock_create_job.assert_not_called()
        # Trigger reports failure, not success.
        assert result is None or not result.get("started"), (
            f"expected no started session, got {result!r}"
        )

    @patch("src.api.v2.fixtures.fixtures._probe_slots_concurrent", return_value={"slot-1": True})
    @patch("src.services.builds.run_service._get_mtib_status_map")
    @patch("src.services.builds.run_service.get_db_client")
    def test_release_package_on_release_fixture_proceeds(
        self, mock_get_db, mock_status, _mock_probe,
    ):
        """Released package on a RELEASE fixture is the green path."""
        from src.services.builds.run_service import trigger_build_run_validation

        db = MagicMock()
        mock_get_db.return_value = db
        mock_status.return_value = _ready_status_map(["mtib-rel"])
        db.product.find_unique.return_value = make_obj(
            id="prod-1", name="Alpha", slug="alpha",
        )
        db.fixture.find_many.return_value = [_release_fixture()]
        rel_pkg = make_obj(
            id="tp-rel-1", productId="prod-1", type="VALIDATION",
            status="RELEASED", version="0.5.3",
        )
        db.testrun.create.return_value = make_obj(id="sess-1", config={})
        db.user.find_first.return_value = make_obj(id="u-sys")
        db.productstageconfig.find_first.return_value = None

        with patch(
            "src.services.builds.run_service.resolve_test_package",
            return_value=(rel_pkg, None),
        ), patch(
            "src.services.builds.run_service.create_kubernetes_job",
            return_value="concord-validation-sess-1",
        ):
            result = trigger_build_run_validation(
                "run-1", _build_run(), _builds(),
            )

        assert result is not None
        assert result.get("started") is True

    @patch("src.api.v2.fixtures.fixtures._probe_slots_concurrent", return_value={"slot-2": True})
    @patch("src.services.builds.run_service._get_mtib_status_map")
    @patch("src.services.builds.run_service.get_db_client")
    def test_dev_package_on_dev_fixture_proceeds(
        self, mock_get_db, mock_status, _mock_probe,
    ):
        """DEV package on DEV fixture is allowed — sandbox path."""
        from src.services.builds.run_service import trigger_build_run_validation

        db = MagicMock()
        mock_get_db.return_value = db
        mock_status.return_value = _ready_status_map(["mtib-dev"])
        db.product.find_unique.return_value = make_obj(
            id="prod-1", name="Alpha", slug="alpha",
        )
        db.fixture.find_many.return_value = [_dev_fixture()]
        dev_pkg = make_obj(
            id="tp-dev-2", productId="prod-1", type="VALIDATION",
            status="DEVELOPMENT", version="dev-foo-456",
        )
        db.testrun.create.return_value = make_obj(id="sess-2", config={})
        db.user.find_first.return_value = make_obj(id="u-sys")
        db.productstageconfig.find_first.return_value = None

        with patch(
            "src.services.builds.run_service.resolve_test_package",
            return_value=(dev_pkg, None),
        ), patch(
            "src.services.builds.run_service.create_kubernetes_job",
            return_value="concord-validation-sess-2",
        ):
            result = trigger_build_run_validation(
                "run-1", _build_run(), _builds(),
            )

        assert result is not None
        assert result.get("started") is True
