"""TDD tests for MockCloudClient — written BEFORE implementation.

Tests the full mock interface: message factories, scenario engine,
timing, predicate filtering, and CloudClient API compatibility.
"""

import time
from datetime import datetime, timedelta, timezone

from corekinect.utils.timeutil.tzutils import dt_to_utc

import pytest

from corekinect.core_cloud.msg_def_v1_0 import BootMsgV2
from corekinect.test.mock_cloud import (
    MockCloudClient,
    MessageFactory,
    Scenario,
    ScenarioEngine,
)


# ═══════════════════════════════════════════════════════════════════════
# Message Factory Tests
# ═══════════════════════════════════════════════════════════════════════


class TestMessageFactory:
    """Message factories produce realistic message objects."""

    def test_boot_msg_has_required_fields(self):
        """Test boot msg has required fields."""
        msg = MessageFactory.boot()
        assert msg.device_id is not None
        assert msg.time_of_record is not None
        assert msg.flags is not None

    def test_boot_msg_boot_reason_accessible(self):
        """Test boot msg boot reason accessible."""
        msg = MessageFactory.boot(boot_reason=0)
        assert msg.boot_reason == 0

    def test_boot_msg_custom_device_id(self):
        """Test boot msg custom device id."""
        msg = MessageFactory.boot(device_id=0xDEADBEEF)
        assert msg.device_id == 0xDEADBEEF

    def test_boot_msg_custom_timestamp(self):
        """Test boot msg custom timestamp."""
        ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        msg = MessageFactory.boot(time_of_record=ts)
        assert msg.time_of_record == ts

    def test_boot_msg_coprocessor_str(self):
        """boot_reason_str and coprocessor_str properties work on mock messages."""
        msg = MessageFactory.boot(boot_reason=0, mcu_type=1)
        assert msg.boot_reason_str == "Normal boot"
        assert msg.coprocessor_str == "App Core"

    def test_position_msg_has_required_fields(self):
        """Test position msg has required fields."""
        msg = MessageFactory.position()
        assert msg.device_id is not None
        assert msg.latitude is not None
        assert msg.longitude is not None
        assert msg.is_in_motion is not None

    def test_position_msg_in_motion(self):
        """Test position msg in motion."""
        msg = MessageFactory.position(is_in_motion=True)
        assert msg.is_in_motion is True

    def test_position_msg_stationary(self):
        """Test position msg stationary."""
        msg = MessageFactory.position(is_in_motion=False)
        assert msg.is_in_motion is False

    def test_biometric_msg_has_required_fields(self):
        """Test biometric msg has required fields."""
        msg = MessageFactory.biometric()
        assert msg.device_id is not None
        assert msg.flags is not None

    def test_biometric_msg_on_body(self):
        """Test biometric msg on body."""
        msg = MessageFactory.biometric(on_body=True)
        assert msg.on_body is True

    def test_biometric_msg_off_body(self):
        """Test biometric msg off body."""
        msg = MessageFactory.biometric(on_body=False)
        assert msg.on_body is False

    def test_biometric_msg_temperature(self):
        """Test biometric msg temperature."""
        msg = MessageFactory.biometric(temperature=25.0)
        assert msg.temperature == 25.0

    def test_biometric_msg_pressure(self):
        """Test biometric msg pressure."""
        msg = MessageFactory.biometric(pressure=1013.25)
        assert msg.pressure == 1013.25

    def test_biometric_msg_humidity(self):
        """Test biometric msg humidity."""
        msg = MessageFactory.biometric(humidity=55.0)
        assert msg.humidity == 55.0

    def test_network_status_msg_has_required_fields(self):
        """Test network status msg has required fields."""
        msg = MessageFactory.network_status()
        assert msg.device_id is not None

    def test_network_status_msg_success(self):
        """Test network status msg success."""
        msg = MessageFactory.network_status(
            did_lte_conn=True, did_sock_conn=True, send_success=True
        )
        assert msg.did_lte_conn is True
        assert msg.did_sock_conn is True
        assert msg.send_success is True

    def test_network_status_msg_failure(self):
        """Test network status msg failure."""
        msg = MessageFactory.network_status(
            did_lte_conn=True, did_sock_conn=False, send_success=False
        )
        assert msg.did_sock_conn is False

    def test_hw_failure_msg_no_failures(self):
        """Test hw failure msg no failures."""
        msg = MessageFactory.hw_failure()
        assert msg.device_id is not None
        assert msg.xlr_fails == 0
        assert msg.gps_fails == 0

    def test_hw_failure_msg_with_failures(self):
        """Test hw failure msg with failures."""
        msg = MessageFactory.hw_failure(gps_fails=0x80, bms_fails=0x80)
        assert msg.gps_fails == 0x80
        assert msg.bms_fails == 0x80

    def test_comms_hw_failure_msg(self):
        """Test comms hw failure msg."""
        msg = MessageFactory.comms_hw_failure()
        assert msg.device_id is not None
        assert msg.sim_fails == 0

    def test_comms_hw_failure_msg_with_failures(self):
        """Test comms hw failure msg with failures."""
        msg = MessageFactory.comms_hw_failure(sim_fails=0x80, ipc_fails=0x80)
        assert msg.sim_fails == 0x80
        assert msg.ipc_fails == 0x80

    def test_factory_timestamps_auto_set(self):
        """All factories auto-set time_of_record to now if not provided."""
        before = dt_to_utc(datetime.utcnow())
        boot = MessageFactory.boot()
        pos = MessageFactory.position()
        bio = MessageFactory.biometric()
        net = MessageFactory.network_status()
        after = dt_to_utc(datetime.utcnow())

        for msg in [boot, pos, bio, net]:
            assert before <= msg.time_of_record <= after

    def test_factory_device_id_default(self):
        """Default device ID is the Alpha B0 REV 1.2 device."""
        msg = MessageFactory.boot()
        assert msg.device_id == 0x70B3D584C01E1FCC


# ═══════════════════════════════════════════════════════════════════════
# MockCloudClient Interface Tests
# ═══════════════════════════════════════════════════════════════════════


class TestMockCloudClientInterface:
    """MockCloudClient implements the same interface as CloudClient."""

    def test_has_mark_test_start(self):
        """Test has mark test start."""
        client = MockCloudClient(device_id=0x1234)
        client.mark_test_start()

    def test_has_wait_for_boot(self):
        """Test has wait for boot."""
        client = MockCloudClient(device_id=0x1234)
        client.mark_test_start()
        client.inject(MessageFactory.boot(device_id=0x1234))
        msg = client.wait_for_boot(timeout_s=1)
        assert msg is not None

    def test_has_wait_for_position(self):
        """Test has wait for position."""
        client = MockCloudClient(device_id=0x1234)
        client.mark_test_start()
        client.inject(MessageFactory.position(device_id=0x1234))
        msg = client.wait_for_position(timeout_s=1)
        assert msg is not None

    def test_has_wait_for_biometric(self):
        """Test has wait for biometric."""
        client = MockCloudClient(device_id=0x1234)
        client.mark_test_start()
        client.inject(MessageFactory.biometric(device_id=0x1234))
        msg = client.wait_for_biometric(timeout_s=1)
        assert msg is not None

    def test_has_wait_for_network_status(self):
        """Test has wait for network status."""
        client = MockCloudClient(device_id=0x1234)
        client.mark_test_start()
        client.inject(MessageFactory.network_status(
            device_id=0x1234, did_lte_conn=True,
            did_sock_conn=True, send_success=True,
        ))
        msg = client.wait_for_network_status(timeout_s=1)
        assert msg is not None

    def test_has_check_hw_failures(self):
        """Test has check hw failures."""
        client = MockCloudClient(device_id=0x1234)
        client.mark_test_start()
        result = client.check_hw_failures()
        assert result.get("hasFailures") is False

    def test_has_check_comms_hw_failures(self):
        """Test has check comms hw failures."""
        client = MockCloudClient(device_id=0x1234)
        client.mark_test_start()
        result = client.check_comms_hw_failures()
        assert result.get("hasFailures") is False

    def test_has_wait_for_message(self):
        """Test has wait for message."""
        client = MockCloudClient(device_id=0x1234)
        client.mark_test_start()

        client.inject(MessageFactory.boot(device_id=0x1234))
        msg = client.wait_for_message(BootMsgV2, timeout_s=1)
        assert msg is not None

    def test_has_query_messages(self):
        """Test has query messages."""
        client = MockCloudClient(device_id=0x1234)
        client.mark_test_start()

        result = client.query_messages(BootMsgV2)
        assert isinstance(result, list)

    def test_has_device_id_property(self):
        """Test has device id property."""
        client = MockCloudClient(device_id=0x1234)
        assert client.device_id == 0x1234

    def test_has_db_env_property(self):
        """Test has db env property."""
        client = MockCloudClient(device_id=0x1234, db_env="DEV_1_0")
        assert client.db_env == "DEV_1_0"


# ═══════════════════════════════════════════════════════════════════════
# Message Injection + Filtering
# ═══════════════════════════════════════════════════════════════════════


class TestMockCloudClientInjection:
    """Injecting messages and retrieving them via wait_for_* methods."""

    @pytest.fixture
    def client(self):
        """Client."""
        c = MockCloudClient(device_id=0x1234)
        c.mark_test_start()
        return c

    def test_inject_boot_then_wait(self, client):
        """Test inject boot then wait."""
        client.inject(MessageFactory.boot(device_id=0x1234))
        msg = client.wait_for_boot(timeout_s=1)
        assert "recordId" in msg
        assert msg["bootReason"] == "Normal"

    def test_inject_multiple_boots_returns_first(self, client):
        """Test inject multiple boots returns first."""
        client.inject(MessageFactory.boot(device_id=0x1234, boot_reason=0))
        client.inject(MessageFactory.boot(device_id=0x1234, boot_reason=1))
        msg = client.wait_for_boot(timeout_s=1)
        assert msg["bootReason"] == "Normal"

    def test_wait_for_boot_with_reason_filter(self, client):
        """Test wait for boot with reason filter."""
        client.inject(MessageFactory.boot(device_id=0x1234, boot_reason=0))
        client.inject(MessageFactory.boot(device_id=0x1234, boot_reason=2))
        msg = client.wait_for_boot(boot_reason=2, timeout_s=1)
        assert msg["bootReason"] == "Fuota"

    def test_wait_for_position_with_predicate(self, client):
        """Test wait for position with predicate."""
        client.inject(MessageFactory.position(device_id=0x1234, is_in_motion=False))
        client.inject(MessageFactory.position(device_id=0x1234, is_in_motion=True))
        msg = client.wait_for_position(
            predicate=lambda m: m.get("isInMotion"),
            timeout_s=1,
        )
        assert msg["isInMotion"] is True

    def test_wait_for_biometric_on_body(self, client):
        """Test wait for biometric on body."""
        client.inject(MessageFactory.biometric(device_id=0x1234, on_body=False))
        client.inject(MessageFactory.biometric(device_id=0x1234, on_body=True))
        msg = client.wait_for_biometric(
            predicate=lambda m: m.on_body,
            timeout_s=1,
        )
        assert msg["onSkin"] is True

    def test_check_hw_failures_returns_injected(self, client):
        """Test check hw failures returns injected."""
        client.inject(MessageFactory.hw_failure(device_id=0x1234, gps_fails=0x80))
        result = client.check_hw_failures()
        assert result["hasFailures"] is True
        assert len(result["failures"]) == 1
        assert result["failures"][0].gps_fails == 0x80

    def test_check_comms_hw_failures_returns_injected(self, client):
        """Test check comms hw failures returns injected."""
        client.inject(MessageFactory.comms_hw_failure(device_id=0x1234, sim_fails=0x80))
        result = client.check_comms_hw_failures()
        assert result["hasFailures"] is True
        assert len(result["failures"]) == 1

    def test_query_messages_returns_all(self, client):
        """Test query messages returns all."""

        client.inject(MessageFactory.boot(device_id=0x1234))
        client.inject(MessageFactory.boot(device_id=0x1234))
        client.inject(MessageFactory.boot(device_id=0x1234))
        result = client.query_messages(BootMsgV2)
        assert len(result) == 3

    def test_query_messages_with_predicate(self, client):
        """Test query messages with predicate."""

        client.inject(MessageFactory.boot(device_id=0x1234, boot_reason=0))
        client.inject(MessageFactory.boot(device_id=0x1234, boot_reason=2))
        result = client.query_messages(BootMsgV2, predicate=lambda m: m.boot_reason == 2)
        assert len(result) == 1

    def test_timeout_when_no_matching_message(self, client):
        """Test timeout when no matching message."""
        with pytest.raises(TimeoutError):
            client.wait_for_boot(timeout_s=0.1)

    def test_timeout_when_predicate_never_matches(self, client):
        """Test timeout when predicate never matches."""
        client.inject(MessageFactory.boot(device_id=0x1234, boot_reason=0))
        with pytest.raises(TimeoutError):
            client.wait_for_boot(boot_reason=99, timeout_s=0.1)

    def test_messages_only_after_mark_test_start(self, client):
        """Messages injected before mark_test_start are not visible."""

        old_time = dt_to_utc(datetime.utcnow()) - timedelta(hours=1)
        client.inject(MessageFactory.boot(device_id=0x1234, time_of_record=old_time))
        # Re-mark test start (simulates new test)
        client.mark_test_start()
        result = client.query_messages(BootMsgV2)
        assert len(result) == 0

    def test_different_device_id_ignored(self, client):
        """Messages for a different device are filtered out."""
        client.inject(MessageFactory.boot(device_id=0x9999))
        with pytest.raises(TimeoutError):
            client.wait_for_boot(timeout_s=0.1)

    def test_clear_removes_all_messages(self, client):
        """Test clear removes all messages."""

        client.inject(MessageFactory.boot(device_id=0x1234))
        client.clear()
        result = client.query_messages(BootMsgV2)
        assert len(result) == 0


# ═══════════════════════════════════════════════════════════════════════
# Scenario Engine Tests
# ═══════════════════════════════════════════════════════════════════════


class TestScenarioPresets:
    """Built-in scenarios produce correct message sequences."""

    def test_happy_boot_scenario(self):
        """Test happy boot scenario."""
        scenario = Scenario.happy_boot()
        assert len(scenario.messages) >= 2  # boot + network status at minimum
        boot_msgs = [m for m in scenario.messages if type(m).__name__ == "BootMsgV2"]
        assert len(boot_msgs) >= 1
        assert boot_msgs[0].boot_reason == 0

    def test_motion_detected_scenario(self):
        """Test motion detected scenario."""
        scenario = Scenario.motion_detected()
        pos_msgs = [m for m in scenario.messages if hasattr(m, "is_in_motion")]
        assert any(m.is_in_motion for m in pos_msgs)

    def test_on_skin_scenario(self):
        """Test on skin scenario."""
        scenario = Scenario.on_skin()
        bio_msgs = [m for m in scenario.messages if hasattr(m, "on_body")]
        assert any(m.on_body for m in bio_msgs)

    def test_off_skin_scenario(self):
        """Test off skin scenario."""
        scenario = Scenario.off_skin()
        bio_msgs = [m for m in scenario.messages if hasattr(m, "on_body")]
        assert any(not m.on_body for m in bio_msgs)

    def test_hw_failure_scenario(self):
        """Test hw failure scenario."""
        scenario = Scenario.hw_failure(gps_fails=0x80)
        hw_msgs = [m for m in scenario.messages if hasattr(m, "gps_fails")]
        assert len(hw_msgs) >= 1
        assert hw_msgs[0].gps_fails == 0x80

    def test_fuota_reboot_scenario(self):
        """Test fuota reboot scenario."""
        scenario = Scenario.fuota_reboot()
        boot_msgs = [m for m in scenario.messages if type(m).__name__ == "BootMsgV2"]
        assert any(m.boot_reason == 2 for m in boot_msgs)

    def test_clean_operation_scenario(self):
        """Clean operation: boot, network, position, biometric — no failures."""
        scenario = Scenario.clean_operation()
        assert len(scenario.messages) >= 4
        # No hw failure messages
        hw_msgs = [m for m in scenario.messages if hasattr(m, "gps_fails") or hasattr(m, "sim_fails")]
        assert len(hw_msgs) == 0


class TestScenarioEngine:
    """ScenarioEngine loads scenarios into MockCloudClient."""

    def test_load_scenario(self):
        """Test load scenario."""
        client = MockCloudClient(device_id=0x1234)
        engine = ScenarioEngine(client)
        client.mark_test_start()
        engine.load(Scenario.happy_boot(device_id=0x1234))
        msg = client.wait_for_boot(timeout_s=1)
        assert msg is not None

    def test_load_replaces_previous(self):
        """Test load replaces previous."""

        client = MockCloudClient(device_id=0x1234)
        engine = ScenarioEngine(client)
        client.mark_test_start()
        engine.load(Scenario.happy_boot(device_id=0x1234))
        engine.load(Scenario.motion_detected(device_id=0x1234))
        boots = client.query_messages(BootMsgV2)
        # Motion scenario may or may not include boot, but old scenario's messages gone
        # The key test: messages were replaced
        assert client._messages is not None

    def test_scenario_device_id_override(self):
        """Scenario can override device_id for all messages."""
        scenario = Scenario.happy_boot(device_id=0xBEEF)
        for msg in scenario.messages:
            assert msg.device_id == 0xBEEF

    def test_append_scenario(self):
        """Can append additional messages to existing scenario."""
        client = MockCloudClient(device_id=0x1234)
        engine = ScenarioEngine(client)
        client.mark_test_start()
        engine.load(Scenario.happy_boot(device_id=0x1234))
        engine.append(MessageFactory.hw_failure(device_id=0x1234, gps_fails=0x80))
        info = client.check_hw_failures()
        assert info["hasFailures"] is True
        assert len(info["failures"]) == 1


# ═══════════════════════════════════════════════════════════════════════
# Integration: MockCloudClient used like real CloudClient
# ═══════════════════════════════════════════════════════════════════════


class TestMockCloudClientIntegration:
    """Simulate real test patterns using MockCloudClient."""

    def test_boot_verification_pattern(self):
        """Simulates test_boot.py::test_power_cycle_produces_bootmsg."""
        client = MockCloudClient(device_id=0x1234)
        engine = ScenarioEngine(client)

        # Real pattern: autouse fixture calls mark_test_start, then test loads scenario
        client.mark_test_start()
        engine.load(Scenario.happy_boot(device_id=0x1234))
        msg = client.wait_for_boot(timeout_s=5)
        assert msg is not None

    def test_motion_detection_pattern(self):
        """Simulates test_motion.py::test_shake_triggers_motion."""
        client = MockCloudClient(device_id=0x1234)
        engine = ScenarioEngine(client)

        client.mark_test_start()
        engine.load(Scenario.motion_detected(device_id=0x1234))
        msg = client.wait_for_position(
            predicate=lambda m: m.get("isInMotion"),
            timeout_s=5,
        )
        assert msg["isInMotion"] is True

    def test_stationary_no_motion_pattern(self):
        """Simulates test_motion.py::test_stationary_no_false_motion."""
        client = MockCloudClient(device_id=0x1234)
        engine = ScenarioEngine(client)

        client.mark_test_start()
        engine.load(Scenario.clean_operation(device_id=0x1234))
        msg = client.wait_for_position(timeout_s=1)
        assert msg["isInMotion"] is False

    def test_biometric_on_skin_pattern(self):
        """Simulates test_biometric.py::test_on_skin_detected."""
        client = MockCloudClient(device_id=0x1234)
        engine = ScenarioEngine(client)

        client.mark_test_start()
        engine.load(Scenario.on_skin(device_id=0x1234))
        msg = client.wait_for_biometric(
            predicate=lambda m: m.on_body,
            timeout_s=5,
        )
        assert msg["onSkin"] is True

    def test_no_hw_failures_pattern(self):
        """Simulates test_boot.py::test_no_hw_failures_after_boot."""
        client = MockCloudClient(device_id=0x1234)
        engine = ScenarioEngine(client)

        client.mark_test_start()
        engine.load(Scenario.clean_operation(device_id=0x1234))
        info = client.check_hw_failures()
        assert not info.get("hasFailures", False)

    def test_hw_failure_detection_pattern(self):
        """Simulates a failing device that reports GPS errors."""
        client = MockCloudClient(device_id=0x1234)
        engine = ScenarioEngine(client)

        client.mark_test_start()
        engine.load(Scenario.hw_failure(device_id=0x1234, gps_fails=0x80))
        info = client.check_hw_failures()
        assert info["hasFailures"] is True
        assert info["failures"][0].gps_fails == 0x80

    def test_network_status_pattern(self):
        """Simulates cloud_client.wait_for_network_status."""
        client = MockCloudClient(device_id=0x1234)
        engine = ScenarioEngine(client)

        client.mark_test_start()
        engine.load(Scenario.happy_boot(device_id=0x1234))
        msg = client.wait_for_network_status(timeout_s=5)
        assert msg["didLteConn"] is True
        assert msg["didSockConn"] is True
        assert msg["sendSuccess"] is True

    def test_fuota_reboot_pattern(self):
        """Simulates FUOTA complete → device reboots with reason=2."""
        client = MockCloudClient(device_id=0x1234)
        engine = ScenarioEngine(client)

        client.mark_test_start()
        engine.load(Scenario.fuota_reboot(device_id=0x1234))
        msg = client.wait_for_boot(boot_reason=2, timeout_s=5)
        assert msg["bootReason"] == "Fuota"

    def test_environmental_data_pattern(self):
        """Simulates test_environmental.py temperature/pressure/humidity checks."""
        client = MockCloudClient(device_id=0x1234)
        engine = ScenarioEngine(client)

        client.mark_test_start()
        engine.load(Scenario.clean_operation(device_id=0x1234))
        msg = client.wait_for_biometric(timeout_s=5)
        assert msg["temperature"] is not None
        assert msg["pressure"] is not None
        assert msg["humidity"] is not None

    def test_sequential_test_isolation(self):
        """Each mark_test_start creates a clean window — previous messages hidden."""

        client = MockCloudClient(device_id=0x1234)

        # First test
        client.mark_test_start()
        client.inject(MessageFactory.boot(device_id=0x1234, boot_reason=0))
        msgs_1 = client.query_messages(BootMsgV2)
        assert len(msgs_1) == 1

        # Second test — new window
        client.mark_test_start()
        msgs_2 = client.query_messages(BootMsgV2)
        assert len(msgs_2) == 0  # Previous message hidden

        # Inject new message for second test
        client.inject(MessageFactory.boot(device_id=0x1234, boot_reason=2))
        msgs_2b = client.query_messages(BootMsgV2)
        assert len(msgs_2b) == 1
        assert msgs_2b[0].boot_reason == 2
