"""Mock CoreCloud client for offline Stage 4 validation testing.

Provides a drop-in replacement for CloudClient that stores messages
in-memory instead of querying the real CoreCloud PostgreSQL database.

Usage:
    # Direct injection
    client = MockCloudClient(device_id=0x1234)
    client.mark_test_start()
    client.inject(MessageFactory.boot(device_id=0x1234))
    msg = client.wait_for_boot(timeout_s=1)

    # Scenario-based (mark_test_start BEFORE load — matches autouse fixture pattern)
    engine = ScenarioEngine(client)
    client.mark_test_start()
    engine.load(Scenario.happy_boot(device_id=0x1234))
    msg = client.wait_for_boot(timeout_s=1)

Activate via MOCK_CLOUD=1 environment variable in conftest.py.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Type, TypeVar

from corekinect.core_cloud.msg_def_v1_0 import (
    AlphaHwFailureMsg,
    BiometricDataMsg,
    BootMsgV2,
    CommsHwFailureMsg,
    MsgBase,
    NetworkStatusMsgV4,
    PositionMsgV6,
)
from corekinect.utils.bits.ops import extract_bits

T = TypeVar("T", bound=MsgBase)

log = logging.getLogger(__name__)

# Default device ID (Alpha B0 REV 1.2)
DEFAULT_DEVICE_ID = 0x70B3D584C01E1FCC


# ═══════════════════════════════════════════════════════════════════════
# Message Factory
# ═══════════════════════════════════════════════════════════════════════


def _encode_boot_flags(boot_reason: int = 0, mcu_type: int = 1, fw_triggered: bool = False) -> int:
    """Encode BootMsgV2 flags from components.

    Bit layout: [7:6] mcu_type, [5] fw_triggered, [4:0] boot_reason
    """
    flags = (mcu_type & 0x3) << 6
    if fw_triggered:
        flags |= 1 << 5
    flags |= boot_reason & 0x1F
    return flags


def _encode_biometric_flags(on_body: bool = False) -> int:
    """Encode BiometricDataMsg flags. Bit 0 = on_body."""
    return 1 if on_body else 0


class MessageFactory:
    """Factory methods for creating realistic mock CoreCloud messages.

    Each factory produces a real frozen dataclass instance (BootMsgV2,
    PositionMsgV6, etc.) with plausible default values. Override any
    field via keyword arguments.
    """

    @staticmethod
    def boot(
        device_id: int = DEFAULT_DEVICE_ID,
        time_of_record: Optional[datetime] = None,
        boot_reason: int = 0,
        mcu_type: int = 1,
        fw_triggered: bool = False,
        num_exceptions: int = 0,
        record_id: int = 1,
    ) -> BootMsgV2:
        if time_of_record is None:
            time_of_record = datetime.now(timezone.utc)
        flags = _encode_boot_flags(boot_reason, mcu_type, fw_triggered)
        return BootMsgV2(
            device_id=device_id,
            interface_type=2,  # Cellular
            time_of_record=time_of_record,
            device_message_id=548,
            record_id=record_id,
            time_of_boot=time_of_record,
            flags=flags,
            num_exceptions=num_exceptions,
        )

    @staticmethod
    def position(
        device_id: int = DEFAULT_DEVICE_ID,
        time_of_record: Optional[datetime] = None,
        is_in_motion: bool = False,
        latitude: float = 43.6532,
        longitude: float = -79.3832,
        num_sat: int = 8,
        record_id: int = 1,
    ) -> PositionMsgV6:
        if time_of_record is None:
            time_of_record = datetime.now(timezone.utc)
        # Encode flags: bit 0 = is_in_motion in the low byte
        # PositionMsgV6 reads is_in_motion directly as a field, not from flags
        return PositionMsgV6(
            device_id=device_id,
            interface_type=2,
            time_of_record=time_of_record,
            device_message_id=556,
            record_id=record_id,
            flags=0,
            is_in_motion=is_in_motion,
            gnss_fix_valid=True,
            gnss_fix_ok=True,
            valid_date=True,
            valid_time=True,
            conf_date=True,
            conf_time=True,
            conf_time_avail=True,
            on_charger=False,
            used_aiding=False,
            update_reason=0,
            psm_state=0,
            num_sat=num_sat,
            fix_type=3,  # 3D fix
            latitude=latitude,
            longitude=longitude,
            gps_on_time=5,
            horizontal_accuracy=10,
            gps_altitude=150,
            pressure_altitude=145,
            time_of_fix=time_of_record,
            ground_speed=0,
            heading=0,
            batt_voltage=4200,
            air_pressure=1013.25,
            temperature=22.0,
            avg_force=0.1,
            max_force=0.5,
            batt_percent=85,
            pdop=2,
            bms_temp=25,
            gps_vert_accuracy=15,
            emergency_event_id=0,
        )

    @staticmethod
    def biometric(
        device_id: int = DEFAULT_DEVICE_ID,
        time_of_record: Optional[datetime] = None,
        on_body: bool = True,
        temperature: Optional[float] = 25.0,
        pressure: Optional[float] = 1013.25,
        humidity: Optional[float] = 55.0,
        heart_rate: int = 72,
        spo2: int = 98,
        record_id: int = 1,
    ) -> "MockBiometricDataMsg":
        """Create a BiometricDataMsg with convenience temperature/pressure/humidity.

        The real BiometricDataMsg stores raw integers (external_temperature,
        air_pressure, relative_humidity). Stage 4 tests access .temperature,
        .pressure, .humidity via hasattr guards. We use a thin wrapper that
        adds these properties.
        """
        if time_of_record is None:
            time_of_record = datetime.now(timezone.utc)
        flags = _encode_biometric_flags(on_body)
        return MockBiometricDataMsg(
            device_id=device_id,
            interface_type=2,
            time_of_record=time_of_record,
            device_message_id=557,
            record_id=record_id,
            time_of_measurement=time_of_record,
            flags=flags,
            air_pressure=int(pressure * 10) if pressure is not None else None,
            external_temperature=int(temperature * 10) if temperature is not None else None,
            relative_humidity=int(humidity * 10) if humidity is not None else None,
            heart_rate=heart_rate,
            heart_rate_confidence=95,
            spo2=spo2,
            spo2_confidence=90,
            skin_temperature=int(temperature * 10) if temperature is not None else None,
            estimated_core_temperature=370,
            heat_strain_index=0,
            wobble_index=0,
            vsm_on_time=120,
            heat_emergency_event_id=0,
            # Extra fields for convenience access
            _temperature=temperature,
            _pressure=pressure,
            _humidity=humidity,
        )

    @staticmethod
    def network_status(
        device_id: int = DEFAULT_DEVICE_ID,
        time_of_record: Optional[datetime] = None,
        did_lte_conn: bool = True,
        did_sock_conn: bool = True,
        send_success: bool = True,
        rsrp: float = -85.0,
        rsrq: float = -10.0,
        band: int = 12,
        record_id: int = 1,
    ) -> NetworkStatusMsgV4:
        if time_of_record is None:
            time_of_record = datetime.now(timezone.utc)
        return NetworkStatusMsgV4(
            device_id=device_id,
            interface_type=2,
            time_of_record=time_of_record,
            device_message_id=512,
            record_id=record_id,
            time_of_connection=time_of_record,
            did_lte_conn=did_lte_conn,
            did_sock_conn=did_sock_conn,
            send_success=send_success,
            used_nb_iot=False,
            did_use_sim1=True,
            did_socket_disconnect_early=False,
            did_use_dns_sec=True,
            flags=0,
            time_spent=3500,
            rsrq=rsrq,
            rsrp=rsrp,
            bytes_sent=256,
            bytes_received=128,
            band=band,
            energy_estimate=5,
            network_id=310260,
        )

    @staticmethod
    def hw_failure(
        device_id: int = DEFAULT_DEVICE_ID,
        time_of_record: Optional[datetime] = None,
        xlr_fails: int = 0,
        alt_fails: int = 0,
        gps_fails: int = 0,
        bms_fails: int = 0,
        ext_flash_fails: int = 0,
        ppg_fails: int = 0,
        imu_fails: int = 0,
        ir_fails: int = 0,
        batt_charger_fails: int = 0,
        record_id: int = 1,
    ) -> AlphaHwFailureMsg:
        if time_of_record is None:
            time_of_record = datetime.now(timezone.utc)
        return AlphaHwFailureMsg(
            device_id=device_id,
            interface_type=2,
            time_of_record=time_of_record,
            device_message_id=559,
            record_id=record_id,
            time_of_event=time_of_record,
            xlr_fails=xlr_fails,
            alt_fails=alt_fails,
            gps_fails=gps_fails,
            bms_fails=bms_fails,
            ext_flash_fails=ext_flash_fails,
            ppg_fails=ppg_fails,
            imu_fails=imu_fails,
            ir_fails=ir_fails,
            batt_charger_fails=batt_charger_fails,
        )

    @staticmethod
    def comms_hw_failure(
        device_id: int = DEFAULT_DEVICE_ID,
        time_of_record: Optional[datetime] = None,
        sim_fails: int = 0,
        lora_fails: int = 0,
        ipc_fails: int = 0,
        ext_flash_fails: int = 0,
        sec_elem_fails: int = 0,
        sat_modem_fails: int = 0,
        record_id: int = 1,
    ) -> CommsHwFailureMsg:
        if time_of_record is None:
            time_of_record = datetime.now(timezone.utc)
        return CommsHwFailureMsg(
            device_id=device_id,
            interface_type=2,
            time_of_record=time_of_record,
            device_message_id=549,
            record_id=record_id,
            time_of_event=time_of_record,
            sim_fails=sim_fails,
            lora_fails=lora_fails,
            ipc_fails=ipc_fails,
            ext_flash_fails=ext_flash_fails,
            sec_elem_fails=sec_elem_fails,
            sat_modem_fails=sat_modem_fails,
        )


# ═══════════════════════════════════════════════════════════════════════
# MockBiometricDataMsg — wrapper with convenience properties
# ═══════════════════════════════════════════════════════════════════════


class MockBiometricDataMsg(BiometricDataMsg):
    """BiometricDataMsg subclass with .temperature, .pressure, .humidity properties.

    The real BiometricDataMsg stores raw int fields (external_temperature,
    air_pressure, relative_humidity). Stage 4 tests use hasattr() guards
    for .temperature, .pressure, .humidity. This wrapper provides those.

    Note: BiometricDataMsg is a frozen dataclass, so we use __init_subclass__
    and object.__setattr__ for the extra fields.
    """

    # We can't add slots to a frozen subclass easily, so we store extras
    # via the _temperature/_pressure/_humidity constructor args and
    # expose them as properties.

    def __new__(cls, *args, _temperature=None, _pressure=None, _humidity=None, **kwargs):
        instance = super().__new__(cls)
        # Bypass frozen to store private attrs
        object.__setattr__(instance, "_mock_temperature", _temperature)
        object.__setattr__(instance, "_mock_pressure", _pressure)
        object.__setattr__(instance, "_mock_humidity", _humidity)
        return instance

    def __init__(self, *args, _temperature=None, _pressure=None, _humidity=None, **kwargs):
        # Filter out our extra kwargs before passing to parent
        super().__init__(*args, **kwargs)

    @property
    def temperature(self) -> Optional[float]:
        return self._mock_temperature

    @property
    def pressure(self) -> Optional[float]:
        return self._mock_pressure

    @property
    def humidity(self) -> Optional[float]:
        return self._mock_humidity


# ═══════════════════════════════════════════════════════════════════════
# Scenario — predefined message sequences
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class Scenario:
    """A predefined sequence of CoreCloud messages for a test scenario.

    Each scenario represents a device behavior pattern: clean boot,
    motion detection, on-skin contact, hardware failure, etc.
    """

    name: str
    messages: List[MsgBase] = field(default_factory=list)

    @staticmethod
    def happy_boot(device_id: int = DEFAULT_DEVICE_ID) -> "Scenario":
        """Normal boot → successful network connection → position report."""
        now = datetime.now(timezone.utc)
        return Scenario(
            name="happy_boot",
            messages=[
                MessageFactory.boot(device_id=device_id, boot_reason=0, time_of_record=now),
                MessageFactory.network_status(
                    device_id=device_id,
                    did_lte_conn=True,
                    did_sock_conn=True,
                    send_success=True,
                    time_of_record=now,
                ),
                MessageFactory.position(
                    device_id=device_id,
                    is_in_motion=False,
                    time_of_record=now,
                ),
            ],
        )

    @staticmethod
    def motion_detected(device_id: int = DEFAULT_DEVICE_ID) -> "Scenario":
        """Boot → motion → stationary → motion (consistent detection)."""
        now = datetime.now(timezone.utc)
        return Scenario(
            name="motion_detected",
            messages=[
                MessageFactory.boot(device_id=device_id, boot_reason=0, time_of_record=now),
                MessageFactory.network_status(
                    device_id=device_id,
                    did_lte_conn=True, did_sock_conn=True, send_success=True,
                    time_of_record=now,
                ),
                MessageFactory.position(
                    device_id=device_id,
                    is_in_motion=True,
                    time_of_record=now,
                ),
                MessageFactory.position(
                    device_id=device_id,
                    is_in_motion=False,
                    time_of_record=now,
                ),
                MessageFactory.position(
                    device_id=device_id,
                    is_in_motion=True,
                    time_of_record=now,
                ),
            ],
        )

    @staticmethod
    def on_skin(device_id: int = DEFAULT_DEVICE_ID) -> "Scenario":
        """Boot → on-skin contact → biometric data with on_body=True."""
        now = datetime.now(timezone.utc)
        return Scenario(
            name="on_skin",
            messages=[
                MessageFactory.boot(device_id=device_id, boot_reason=0, time_of_record=now),
                MessageFactory.network_status(
                    device_id=device_id,
                    did_lte_conn=True, did_sock_conn=True, send_success=True,
                    time_of_record=now,
                ),
                MessageFactory.biometric(
                    device_id=device_id,
                    on_body=True,
                    temperature=36.5,
                    time_of_record=now,
                ),
            ],
        )

    @staticmethod
    def off_skin(device_id: int = DEFAULT_DEVICE_ID) -> "Scenario":
        """On-skin → off-skin (electrode removed)."""
        now = datetime.now(timezone.utc)
        return Scenario(
            name="off_skin",
            messages=[
                MessageFactory.biometric(
                    device_id=device_id,
                    on_body=True,
                    temperature=36.5,
                    time_of_record=now,
                ),
                MessageFactory.biometric(
                    device_id=device_id,
                    on_body=False,
                    temperature=25.0,
                    time_of_record=now,
                ),
            ],
        )

    @staticmethod
    def hw_failure(
        device_id: int = DEFAULT_DEVICE_ID,
        **failure_kwargs,
    ) -> "Scenario":
        """Boot → hardware failure reported."""
        now = datetime.now(timezone.utc)
        return Scenario(
            name="hw_failure",
            messages=[
                MessageFactory.boot(device_id=device_id, boot_reason=0, time_of_record=now),
                MessageFactory.hw_failure(device_id=device_id, time_of_record=now, **failure_kwargs),
            ],
        )

    @staticmethod
    def fuota_reboot(device_id: int = DEFAULT_DEVICE_ID) -> "Scenario":
        """FUOTA complete → device reboots with boot_reason=2 → reconnects."""
        now = datetime.now(timezone.utc)
        return Scenario(
            name="fuota_reboot",
            messages=[
                MessageFactory.boot(device_id=device_id, boot_reason=2, time_of_record=now),
                MessageFactory.network_status(
                    device_id=device_id,
                    did_lte_conn=True, did_sock_conn=True, send_success=True,
                    time_of_record=now,
                ),
            ],
        )

    @staticmethod
    def clean_operation(device_id: int = DEFAULT_DEVICE_ID) -> "Scenario":
        """Full clean operation: boot, network, position, biometric — no failures."""
        now = datetime.now(timezone.utc)
        return Scenario(
            name="clean_operation",
            messages=[
                MessageFactory.boot(device_id=device_id, boot_reason=0, time_of_record=now),
                MessageFactory.network_status(
                    device_id=device_id,
                    did_lte_conn=True, did_sock_conn=True, send_success=True,
                    time_of_record=now,
                ),
                MessageFactory.position(
                    device_id=device_id,
                    is_in_motion=False,
                    latitude=43.6532,
                    longitude=-79.3832,
                    time_of_record=now,
                ),
                MessageFactory.biometric(
                    device_id=device_id,
                    on_body=False,
                    temperature=22.5,
                    pressure=1013.25,
                    humidity=55.0,
                    time_of_record=now,
                ),
            ],
        )

    @staticmethod
    def full_device_activity(device_id: int = DEFAULT_DEVICE_ID) -> "Scenario":
        """Comprehensive scenario covering ALL message types for mock testing.

        Includes: boot, network, stationary position, motion position,
        on-body biometric, off-body biometric, and zero-failure HW reports.
        Designed as the default mock scenario for Stage 4 tests.
        """
        now = datetime.now(timezone.utc)
        return Scenario(
            name="full_device_activity",
            messages=[
                MessageFactory.boot(device_id=device_id, boot_reason=0, time_of_record=now),
                MessageFactory.network_status(
                    device_id=device_id,
                    did_lte_conn=True, did_sock_conn=True, send_success=True,
                    time_of_record=now,
                ),
                # Stationary position
                MessageFactory.position(
                    device_id=device_id,
                    is_in_motion=False,
                    latitude=43.6532, longitude=-79.3832,
                    time_of_record=now,
                ),
                # Motion position
                MessageFactory.position(
                    device_id=device_id,
                    is_in_motion=True,
                    latitude=43.6533, longitude=-79.3831,
                    time_of_record=now,
                ),
                # On-body biometric
                MessageFactory.biometric(
                    device_id=device_id,
                    on_body=True,
                    temperature=36.5, pressure=1013.25, humidity=55.0,
                    heart_rate=72, spo2=98,
                    time_of_record=now,
                ),
                # Off-body biometric (environmental)
                MessageFactory.biometric(
                    device_id=device_id,
                    on_body=False,
                    temperature=22.5, pressure=1013.25, humidity=55.0,
                    time_of_record=now,
                ),
                # No HW failure messages — tests assert check_hw_failures() returns []
            ],
        )


# ═══════════════════════════════════════════════════════════════════════
# MockCloudClient — drop-in replacement for CloudClient
# ═══════════════════════════════════════════════════════════════════════


class MockCloudClient:
    """In-memory replacement for CloudClient — same interface, no DB.

    Messages are injected via inject() or loaded via ScenarioEngine.
    wait_for_* methods search the in-memory store instead of polling
    CoreCloud PostgreSQL.

    The mock respects mark_test_start() — only messages with
    time_of_record >= test_start are visible to queries.
    """

    def __init__(self, device_id: int, db_env: str = "MOCK"):
        self._device_id = device_id
        self._db_env = db_env
        self._test_start: Optional[datetime] = None
        self._messages: List[MsgBase] = []
        self._active_scenario: Optional[Scenario] = None

    @property
    def device_id(self) -> int:
        return self._device_id

    @property
    def db_env(self) -> str:
        return self._db_env

    def mark_test_start(self) -> None:
        """Record timestamp — subsequent queries only return messages after this point.

        If a scenario is active (loaded via ScenarioEngine), it is automatically
        re-injected with fresh timestamps. This handles mid-test mark_test_start()
        calls that would otherwise make scenario messages invisible.
        """
        self._test_start = datetime.now(timezone.utc)
        log.debug("MockCloudClient: test start marked at %s", self._test_start.isoformat())

        if self._active_scenario is not None:
            self._messages.clear()
            now = datetime.now(timezone.utc)
            for msg in self._active_scenario.messages:
                object.__setattr__(msg, "time_of_record", now)
                self._messages.append(msg)
            log.debug(
                "MockCloudClient: re-injected %d messages from scenario '%s'",
                len(self._active_scenario.messages),
                self._active_scenario.name,
            )

    def inject(self, msg: MsgBase) -> None:
        """Add a message to the in-memory store."""
        self._messages.append(msg)

    def clear(self) -> None:
        """Remove all messages from the store."""
        self._messages.clear()

    def _require_test_start(self) -> datetime:
        if self._test_start is None:
            raise RuntimeError("mark_test_start() must be called before querying messages")
        return self._test_start

    def _visible_messages(self, msg_class: Type[T]) -> List[T]:
        """Return messages of the given type visible in the current test window."""
        since = self._require_test_start()
        result = []
        for msg in self._messages:
            # Type check — msg must be an instance of the requested class
            if not isinstance(msg, msg_class):
                continue
            # Device ID filter
            if msg.device_id != self._device_id:
                continue
            # Time window filter
            if msg.time_of_record is not None and msg.time_of_record < since:
                continue
            result.append(msg)
        return result

    def _poll(
        self,
        msg_class: Type[T],
        predicate: Optional[Callable[[T], bool]],
        timeout_s: float,
        poll_interval_s: float = 0.05,
    ) -> T:
        """Search for a matching message. Short poll interval since data is in-memory."""
        deadline = time.monotonic() + timeout_s

        while time.monotonic() < deadline:
            visible = self._visible_messages(msg_class)
            for msg in visible:
                if predicate is None or predicate(msg):
                    return msg
            time.sleep(poll_interval_s)

        raise TimeoutError(
            f"MockCloudClient: no {msg_class.__name__} matching predicate for "
            f"device {self._device_id:#X} within {timeout_s}s "
            f"({len(self._messages)} total messages in store)"
        )

    # ── CloudClient-compatible interface ──────────────────────────

    def wait_for_boot(
        self,
        boot_reason: Optional[int] = None,
        timeout_s: float = 120,
    ) -> BootMsgV2:
        def pred(b: BootMsgV2) -> bool:
            if boot_reason is not None and b.boot_reason != boot_reason:
                return False
            return True
        return self._poll(BootMsgV2, pred, timeout_s)

    def wait_for_position(
        self,
        predicate: Optional[Callable[[PositionMsgV6], bool]] = None,
        timeout_s: float = 300,
    ) -> PositionMsgV6:
        return self._poll(PositionMsgV6, predicate, timeout_s)

    def wait_for_biometric(
        self,
        predicate: Optional[Callable[[BiometricDataMsg], bool]] = None,
        timeout_s: float = 120,
    ) -> BiometricDataMsg:
        # MockBiometricDataMsg is a subclass of BiometricDataMsg, so isinstance works
        return self._poll(BiometricDataMsg, predicate, timeout_s)

    def wait_for_network_status(
        self, timeout_s: float = 120
    ) -> NetworkStatusMsgV4:
        def pred(n: NetworkStatusMsgV4) -> bool:
            return bool(n.did_lte_conn and n.did_sock_conn and n.send_success)
        return self._poll(NetworkStatusMsgV4, pred, timeout_s)

    def check_hw_failures(self) -> List[AlphaHwFailureMsg]:
        return self._visible_messages(AlphaHwFailureMsg)

    def check_comms_hw_failures(self) -> List[CommsHwFailureMsg]:
        return self._visible_messages(CommsHwFailureMsg)

    def wait_for_message(
        self,
        msg_class: Type[T],
        predicate: Optional[Callable[[T], bool]] = None,
        timeout_s: float = 120,
        poll_interval_s: float = 0.05,
    ) -> T:
        return self._poll(msg_class, predicate, timeout_s, poll_interval_s)

    def query_messages(
        self,
        msg_class: Type[T],
        predicate: Optional[Callable[[T], bool]] = None,
    ) -> List[T]:
        visible = self._visible_messages(msg_class)
        if predicate:
            return [m for m in visible if predicate(m)]
        return visible


# ═══════════════════════════════════════════════════════════════════════
# ScenarioEngine — loads scenarios into MockCloudClient
# ═══════════════════════════════════════════════════════════════════════


class ScenarioEngine:
    """Loads predefined Scenarios into a MockCloudClient.

    Usage:
        engine = ScenarioEngine(client)
        engine.load(Scenario.happy_boot(device_id=0x1234))
    """

    def __init__(self, client: MockCloudClient):
        self._client = client

    def load(self, scenario: Scenario) -> None:
        """Replace all messages in client with scenario messages.

        Re-timestamps all messages to now so they appear after any
        subsequent mark_test_start() call. Sets the scenario as "active"
        so mark_test_start() auto-reinjects fresh messages.
        """
        self._client.clear()
        self._client._active_scenario = scenario
        now = datetime.now(timezone.utc)
        for msg in scenario.messages:
            # Frozen dataclass — bypass __setattr__
            object.__setattr__(msg, "time_of_record", now)
            self._client.inject(msg)
        log.info("Loaded scenario '%s' with %d messages", scenario.name, len(scenario.messages))

    def append(self, msg: MsgBase) -> None:
        """Add a single message without clearing existing ones.

        Re-timestamps the message to now for consistency with load().
        """
        object.__setattr__(msg, "time_of_record", datetime.now(timezone.utc))
        self._client.inject(msg)
