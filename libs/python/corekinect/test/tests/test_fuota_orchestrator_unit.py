"""Unit tests for FuotaOrchestrator.

Tests orchestration logic using StubFuotaClient — no network calls,
no CoreCloud, no hardware.
"""

import inspect

import pytest

from corekinect.errors import ConfigError
from corekinect.errors import TimeoutError as ValidationTimeoutError
from corekinect.test.fuota_orchestrator import FuotaOrchestrator, personalize_with_retry
from corekinect.test.stage_assets import BuildAsset
from corekinect.test.tests.stubs import StubArtifactResolver, StubFuotaClient


@pytest.fixture
def stub_client():
    return StubFuotaClient()


@pytest.fixture
def orchestrator(stub_client):
    return FuotaOrchestrator(fuota_client=stub_client, fixture_controller=None)


@pytest.fixture
def resolver():
    r = StubArtifactResolver()
    yield r
    r.cleanup()


# =============================================================================
# upload_cfw_files
# =============================================================================


class TestUploadCfwFiles:
    """Tests for FuotaOrchestrator.upload_cfw_files()."""

    def test_records_upload_event_for_each_path(self, orchestrator, stub_client):
        """Each CFW path should produce an upload_cfw event."""
        paths = ["/tmp/108.0.5.2-BM.cfw", "/tmp/109.0.5.2-BM.cfw"]
        orchestrator.upload_cfw_files(paths)

        upload_events = [e for e in stub_client.events if e["action"] == "upload_cfw"]
        assert len(upload_events) == 2
        assert upload_events[0]["path"] == paths[0]
        assert upload_events[1]["path"] == paths[1]

    def test_single_file_upload(self, orchestrator, stub_client):
        """A single CFW file should produce exactly one upload event."""
        orchestrator.upload_cfw_files(["/tmp/108.0.8.3-BM.cfw"])

        upload_events = [e for e in stub_client.events if e["action"] == "upload_cfw"]
        assert len(upload_events) == 1

    def test_empty_list_produces_no_events(self, orchestrator, stub_client):
        """An empty list should not produce any upload events."""
        orchestrator.upload_cfw_files([])

        upload_events = [e for e in stub_client.events if e["action"] == "upload_cfw"]
        assert len(upload_events) == 0


# =============================================================================
# create_and_assign_plan
# =============================================================================


class TestCreateAndAssignPlan:
    """Tests for FuotaOrchestrator.create_and_assign_plan()."""

    DEVICE_ID = "70B3D584C01E1FCC"
    DEVICE_TYPE = 2
    DEVICE_VARIANT = 3

    def _create_plan(self, orchestrator, target_strings=None):
        """Helper to call create_and_assign_plan with defaults."""
        return orchestrator.create_and_assign_plan(
            device_id=self.DEVICE_ID,
            target_strings=target_strings or ["108.0.5.2-BM", "109.0.5.2-BM"],
            description="test plan",
            device_type_id=self.DEVICE_TYPE,
            device_variant_id=self.DEVICE_VARIANT,
        )

    def test_calls_ensure_device_registered(self, orchestrator, stub_client):
        """Should register the device before creating the plan."""
        self._create_plan(orchestrator)

        reg_events = [
            e for e in stub_client.events
            if e["action"] == "ensure_device_registered"
        ]
        assert len(reg_events) == 1
        assert reg_events[0]["device_id"] == self.DEVICE_ID
        assert reg_events[0]["device_type_id"] == self.DEVICE_TYPE
        assert reg_events[0]["device_variant_id"] == self.DEVICE_VARIANT

    def test_checks_existing_assignments(self, orchestrator, stub_client):
        """Should query settings/devices to check for existing plan assignments."""
        self._create_plan(orchestrator)

        settings_requests = [
            e for e in stub_client.events
            if e["action"] == "_singleton_request"
            and "settings/devices" in e.get("path", "")
        ]
        assert len(settings_requests) >= 1

    def test_removes_existing_assignment_before_creating(self, orchestrator, stub_client):
        """If device is already assigned, should disable before reassigning."""
        # Pre-assign the device to an old plan
        stub_client._assigned_devices[self.DEVICE_ID] = 99

        self._create_plan(orchestrator)

        disable_events = [
            e for e in stub_client.events if e["action"] == "disable_device"
        ]
        assert len(disable_events) == 1
        assert disable_events[0]["device_id"] == self.DEVICE_ID
        assert disable_events[0]["plan_id"] == 99

    def test_creates_plan_with_stages(self, orchestrator, stub_client):
        """Should call create_plan with the correct stages structure."""
        targets = ["108.0.5.2-BM", "109.0.5.2-BM"]
        self._create_plan(orchestrator, target_strings=targets)

        plan_events = [
            e for e in stub_client.events if e["action"] == "create_plan"
        ]
        assert len(plan_events) == 1
        stage = plan_events[0]["stages"][0]
        assert sorted(stage["targets"]) == sorted(targets)

    def test_assigns_device_to_plan(self, orchestrator, stub_client):
        """Should assign the device to the newly created plan."""
        stub_client.set_plan_id(42)
        self._create_plan(orchestrator)

        assign_events = [
            e for e in stub_client.events if e["action"] == "assign_device"
        ]
        assert len(assign_events) == 1
        assert assign_events[0]["plan_id"] == 42
        assert assign_events[0]["device_ids"] == [self.DEVICE_ID]
        assert assign_events[0]["enable"] is True

    def test_verifies_assignment_after_assign(self, orchestrator, stub_client):
        """Should query settings/devices after assignment to verify."""
        stub_client.set_plan_id(42)
        self._create_plan(orchestrator)

        # After assign_device, there should be another settings/devices query
        assign_idx = next(
            i for i, e in enumerate(stub_client.events)
            if e["action"] == "assign_device"
        )
        post_assign_settings = [
            e for e in stub_client.events[assign_idx + 1:]
            if e["action"] == "_singleton_request"
            and "settings/devices" in e.get("path", "")
        ]
        assert len(post_assign_settings) >= 1

    def test_returns_plan_id(self, orchestrator, stub_client):
        """Should return the plan_id from the client."""
        stub_client.set_plan_id(77)
        plan_id = self._create_plan(orchestrator)
        assert plan_id == 77

    def test_target_strings_passed_through(self, orchestrator, stub_client):
        """The exact target_strings should appear in the plan stages."""
        custom_targets = ["108.0.8.3-BMD", "109.0.8.3-BMD"]
        self._create_plan(orchestrator, target_strings=custom_targets)

        plan_events = [
            e for e in stub_client.events if e["action"] == "create_plan"
        ]
        stage = plan_events[0]["stages"][0]
        assert sorted(stage["targets"]) == sorted(custom_targets)


# =============================================================================
# wait_for_cloud_checkin
# =============================================================================


class TestWaitForCloudCheckin:
    """Tests for FuotaOrchestrator.wait_for_cloud_checkin()."""

    DEVICE_ID = "70B3D584C01E1FCC"

    def test_returns_immediately_when_record_id_increases(self, orchestrator, stub_client):
        """Should return the new recordId when it increases from baseline."""
        # First call returns recordId=0 (baseline), second returns recordId=5
        stub_client.set_device_record_id(self.DEVICE_ID, 0)

        # We need the recordId to change between the baseline read and poll.
        # Override _api_request to increment on the second call.
        call_count = {"n": 0}
        original = stub_client._api_request

        def advancing_api_request(method, path, **kwargs):
            call_count["n"] += 1
            if call_count["n"] >= 2:
                stub_client.set_device_record_id(self.DEVICE_ID, 5)
            return original(method, path, **kwargs)

        stub_client._api_request = advancing_api_request

        result = orchestrator.wait_for_cloud_checkin(
            self.DEVICE_ID, timeout_s=5, poll_interval_s=0.1,
        )
        assert result == 5

    def test_raises_timeout_when_record_id_never_changes(self, orchestrator, stub_client):
        """Should raise TimeoutError when recordId stays at 0."""
        stub_client.set_device_record_id(self.DEVICE_ID, 0)

        with pytest.raises(ValidationTimeoutError, match="did not check into CoreCloud"):
            orchestrator.wait_for_cloud_checkin(
                self.DEVICE_ID, timeout_s=1, poll_interval_s=0.1,
            )


# =============================================================================
# _all_completed (static method)
# =============================================================================


class TestAllCompleted:
    """Tests for FuotaOrchestrator._all_completed() static method."""

    def test_empty_completed_returns_false(self):
        """Empty completed set should return False when there are expected IDs."""
        assert FuotaOrchestrator._all_completed(set(), {"108", "109"}) is False

    def test_partial_match_returns_false(self):
        """Completing only some expected IDs should return False."""
        completed = {"108.0.5.2-BM"}
        expected = {"108", "109"}
        assert FuotaOrchestrator._all_completed(completed, expected) is False

    def test_all_matching_returns_true(self):
        """All expected IDs having a matching version should return True."""
        completed = {"108.0.5.2-BM", "109.0.5.2-BM"}
        expected = {"108", "109"}
        assert FuotaOrchestrator._all_completed(completed, expected) is True

    def test_app_id_substring_matching(self):
        """Should match app IDs as substrings of completed version strings."""
        completed = {"108.0.5.2-BM"}
        expected = {"108"}
        assert FuotaOrchestrator._all_completed(completed, expected) is True

    def test_empty_expected_returns_true(self):
        """No expected IDs means everything is 'complete'."""
        assert FuotaOrchestrator._all_completed(set(), set()) is True

    def test_extra_completed_ids_still_pass(self):
        """Extra completed versions beyond expected should not cause failure."""
        completed = {"108.0.5.2-BM", "109.0.5.2-BM", "110.0.1.0-P"}
        expected = {"108", "109"}
        assert FuotaOrchestrator._all_completed(completed, expected) is True


# =============================================================================
# upload_transition (BuildAsset-aware)
# =============================================================================


class TestUploadTransition:
    """Tests for FuotaOrchestrator.upload_transition()."""

    def test_uploads_all_cfws_from_both_builds(self, orchestrator, stub_client, resolver):
        """Should upload CFW files from both source and target builds."""
        resolver.add_build("SOURCE", version="0.5.1", track="BM", has_cfw=True)
        resolver.add_build("TARGET", version="0.5.2", track="BM", has_cfw=True)

        source = BuildAsset("SOURCE", resolver)
        target = BuildAsset("TARGET", resolver)

        orchestrator.upload_transition(source, target)

        upload_events = [e for e in stub_client.events if e["action"] == "upload_cfw"]
        # 2 targets (app + comms) x 2 builds = 4 CFW uploads
        assert len(upload_events) == 4

    def test_raises_value_error_when_no_cfws(self, orchestrator, resolver):
        """Should raise ValueError when neither build has CFW files."""
        resolver.add_build("SOURCE", version="0.5.1", track="BM", has_cfw=False)
        resolver.add_build("TARGET", version="0.5.2", track="BM", has_cfw=False)

        source = BuildAsset("SOURCE", resolver)
        target = BuildAsset("TARGET", resolver)

        with pytest.raises(ConfigError, match="No CFW files found"):
            orchestrator.upload_transition(source, target)


# =============================================================================
# create_transition_plan (BuildAsset-aware)
# =============================================================================


class TestCreateTransitionPlan:
    """Tests for FuotaOrchestrator.create_transition_plan()."""

    DEVICE_ID = "70B3D584C01E1FCC"
    DEVICE_TYPE = 2
    DEVICE_VARIANT = 3

    def test_creates_plan_with_target_strings(self, orchestrator, stub_client, resolver):
        """Should create plan using target_strings from the target BuildAsset."""
        resolver.add_build("SOURCE", version="0.5.1", track="BM")
        resolver.add_build("TARGET", version="0.5.2", track="BM")

        source = BuildAsset("SOURCE", resolver)
        target = BuildAsset("TARGET", resolver)

        stub_client.set_plan_id(55)
        plan_id = orchestrator.create_transition_plan(
            device_id=self.DEVICE_ID,
            source=source,
            target=target,
            description="FUOTA transition",
            device_type_id=self.DEVICE_TYPE,
            device_variant_id=self.DEVICE_VARIANT,
        )
        assert plan_id == 55

        plan_events = [
            e for e in stub_client.events if e["action"] == "create_plan"
        ]
        assert len(plan_events) == 1
        stage_targets = sorted(plan_events[0]["stages"][0]["targets"])
        # Should contain target_strings from the TARGET build
        expected_targets = sorted(target.target_strings())
        assert stage_targets == expected_targets

    def test_description_includes_source_and_target_info(self, orchestrator, stub_client, resolver):
        """Plan description should include source/target labels and versions."""
        resolver.add_build("MFG_BASE", version="0.5.1", track="BM")
        resolver.add_build("FUT_VERBOSE_A", version="0.5.2", track="BM")

        source = BuildAsset("MFG_BASE", resolver)
        target = BuildAsset("FUT_VERBOSE_A", resolver)

        orchestrator.create_transition_plan(
            device_id=self.DEVICE_ID,
            source=source,
            target=target,
            description="upgrade test",
            device_type_id=self.DEVICE_TYPE,
            device_variant_id=self.DEVICE_VARIANT,
        )

        plan_events = [
            e for e in stub_client.events if e["action"] == "create_plan"
        ]
        desc = plan_events[0]["description"]
        assert "MFG_BASE" in desc
        assert "FUT_VERBOSE_A" in desc
        assert "0.5.1" in desc
        assert "0.5.2" in desc


# =============================================================================
# personalize_with_retry — existence and signature only
# =============================================================================


class TestPersonalizeWithRetry:
    """Verify personalize_with_retry exists with the expected signature."""

    def test_function_exists(self):
        """personalize_with_retry should be importable."""
        assert callable(personalize_with_retry)

    def test_has_expected_parameters(self):
        """Should accept client, snr, and optional keyword arguments."""
        sig = inspect.signature(personalize_with_retry)
        params = list(sig.parameters.keys())
        assert "client" in params
        assert "snr" in params
        assert "device_id" in params
        assert "max_retries" in params
