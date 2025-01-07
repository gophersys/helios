import base64
import json
import logging
import struct
from copy import deepcopy
from datetime import datetime
from time import sleep, time
from typing import List

import requests
from corekinect.utils.log import Logger
from corekinect.validation.utils import get_bits, set_bits

from ._db_orm_v0_9 import *
from ._message_spec_constants import *
from .data_types import *


class DebugSqlAlchemy:
    def __init__(self, log_level=logging.INFO):
        self.log_level = log_level

    def __enter__(self):
        logging.getLogger("sqlalchemy.engine").setLevel(self.log_level)

    def __exit__(self, exc_type, exc_val, exc_tb):
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


class APIInterface:
    def __init__(self, use_db_over_api: bool = True):
        self.use_db_over_api = use_db_over_api

        if self.use_db_over_api:
            self._use_database()
        else:
            self._use_api()

    def _use_api(self):
        with open("secrets.json") as f:
            conf = json.load(f)

        base_url = conf["CORE_CLOUD_VAL_DEV_BASE_URL"]
        base_port = conf["CORE_CLOUD_VAL_DEV_PORT"]
        self.api_url = f"{base_url}:{base_port}"

        client_id = conf["CORE_CLOUD_VAL_DEV_CLIENT_ID"]
        client_secret = conf["CORE_CLOUD_VAL_DEV_CLIENT_SECRET"]

        # Get the access token
        url = f"{base_url}:{base_port}/auth/requesttoken"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {base64.b64encode(f'{client_id}:{client_secret}'.encode()).decode()}",
        }
        data = {"grant_type": "client_credentials"}

        response = requests.post(url, headers=headers, data=data)

        if response.status_code != 200:
            raise Exception("Failed to get access token.")

        self.access_token = response.json()["access_token"]

        if self.access_token is None:
            raise Exception("Failed to get access token.")

    def _use_database(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        with open("secrets.json") as f:
            conf = json.load(f)

        self.engine = create_engine(
            f"mysql+mysqlconnector://{conf['DB_0_9_CC_TEST_DATA_VAL_USER']}:{conf['DB_0_9_CC_TEST_DATA_VAL_PASSWORD']}@{conf['DB_0_9_CC_TEST_DATA_URI']}/CoreCloudTestData",
            pool_pre_ping=True,
        )
        self.Session = sessionmaker(bind=self.engine)
        self._default_limit = 1000

    def _api_query(self, endpoint: str, query: dict) -> List[dict]:
        url = f"{self.api_url}/0v9/val/{endpoint}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.access_token}",
        }

        response = requests.post(url, headers=headers, data=json.dumps(query))

        if response.status_code != 200:
            raise Exception(f"Failed to get data, {response.status_code=}, {response.text=}")

        return response.json()

    def _send_config_msg(self, dut_id: int, msg: str, timeout=180) -> None:
        """
        Send a config message to the CoreCloudTestData DownlinkMessagesTbl

        SQl Query:
            INSERT INTO DownlinkMessagesTbl(DeviceId, DeviceTypeId, TimeQueued, NonceSent, IsAcked, IsNaked, Message, AccountId) VALUES (1, 9, UTC_TIME(), b'0', b'0', b'0', 'base64_msg', 21);

        """
        log = Logger.get_test_case_logger()

        last_downlink_message_id = None
        db = self.Session()
        last_downlink_message: DownlinkMessagesTbl = (
            db.query(DownlinkMessagesTbl)
            .filter_by(DeviceId=dut_id)
            .order_by(DownlinkMessagesTbl.DownlinkMessageId.desc())
            .first()
        )
        if last_downlink_message is not None:
            last_downlink_message_id = last_downlink_message.DownlinkMessageId
        else:
            last_downlink_message_id = 0

        last_downlink_message = deepcopy(last_downlink_message)
        db.close()

        log.debug(f"Sending config message to DeviceId: {hex(dut_id)}, {msg=}")
        config_msg = DownlinkMessagesTbl(
            DeviceId=dut_id,
            DeviceTypeId=9,
            TimeQueued=datetime.utcnow(),
            NonceSent=b"0",
            IsAcked=False,
            IsNaked=False,
            Message=msg,
            AccountId=21,
        )

        db = self.Session()
        db.add(config_msg)
        db.commit()
        db.close()

        # Wait for the message to be added to the database
        end_time = time() + timeout
        downlink_message_queued = False
        while not downlink_message_queued and time() < end_time:
            with self.Session() as db:
                new_downlink_message = (
                    db.query(DownlinkMessagesTbl)
                    .filter(
                        DownlinkMessagesTbl.DeviceId == dut_id,
                        DownlinkMessagesTbl.DownlinkMessageId > last_downlink_message_id,
                    )
                    .order_by(DownlinkMessagesTbl.DownlinkMessageId.desc())
                    .all()
                )
                for new_msg in new_downlink_message:
                    if new_msg.Message == msg:
                        downlink_message_queued = True
                        break
                sleep(1)

        log.debug(f"{end_time=}, {time()=}")
        log.debug(f"{downlink_message_queued=}")
        if end_time < time():
            # raise FailTest(
            #     message="DownlinkMessagesTbl was not updated.",
            #     function_name="_send_config_msg",
            #     details="Timeout waiting for message to be added to the database.",
            # )
            pass
        if not downlink_message_queued:
            # raise FailTest(
            #     message="Message did not appear in the DownlinkMessageTbl.",
            #     function_name="_send_config_msg",
            #     details="Message was not added to the database.",
            # )
            pass

    # -----------------------------------------------------------------------------------------------------------------
    #                                                                                                   Config Messages
    # -----------------------------------------------------------------------------------------------------------------

    # -------------------------------------------------------------------------------------------- JumpTrack GPS Config
    def send_jumptrack_gps_config(self, dut_id: int, new_config: JumpTrackGpsConfig) -> None:
        """
        Apply the GPS aiding configuration to the DUT.

        Parameters:
            config (TestStepConfig): The test step configuration.
            aiding_enabled (bool): True to enable GPS aiding, False to disable GPS aiding.

        Raises:
            FailTest: If the GPS aiding configuration could not be applied.

        SQL Query:
            INSERT INTO JumpTrackGpsConfigMsgTbl(DeviceId, TimeReceived, FromDevice, NonceReceived, TimeOfGpsConfig, Flags, TargetFixAccuracy, TargetFixPdop) VALUES (1, 1626950000, 1, 1, 1626950000, 1, 1, 1, 1);
        """
        log = Logger.get_test_case_logger()
        log.debug("Applying GPS configuration using CoreCloud v0.9")

        log.warning(f"USING DIRECT DATABASE ACCESS!")

        constants = JumpTrackGPSConfigConstants()

        # Encode the flags
        flags = 0
        flags = set_bits(
            flags, constants.aiding_enabled_bits[0], constants.aiding_enabled_bits[1], new_config.aiding_enabled
        )
        flags = set_bits(
            flags,
            constants.gnss_update_frequency_bits[0],
            constants.gnss_update_frequency_bits[1],
            new_config.gnss_update_frequency,
        )
        flags = set_bits(
            flags, constants.low_power_enable_bits[0], constants.low_power_enable_bits[1], new_config.low_power_enabled
        )

        # Generate the message
        b64_msg = struct.pack(
            constants.packed_format,
            constants.message_id,
            constants.message_length,
            int(datetime.utcnow().timestamp()),
            flags,
            new_config.target_accuracy,
            new_config.target_pdop,
        )

        # Send the config message
        self._send_config_msg(dut_id, b64_msg)

    def get_jumptrack_gps_config(self, dut_id: int) -> JumpTrackGpsConfig | None:
        log = Logger.get_test_case_logger()
        log.debug("Getting GPS configuration using CoreCloud v0.9")

        log.warning(f"USING DIRECT DATABASE ACCESS!")

        # Return object
        gps_config = JumpTrackGpsConfig()

        # Get the latest GPS configuration
        current_config: JumpTrackGpsConfigMsgTbl = None
        db = self.Session()
        current_config = (
            db.query(JumpTrackGpsConfigMsgTbl)
            .filter_by(DeviceId=dut_id)
            .order_by(JumpTrackGpsConfigMsgTbl.CheckinId.desc())
            .first()
        )
        current_config = deepcopy(current_config)
        db.close()

        # Check if the configuration was found
        if current_config is None:
            return None

        # Populate the GPS configuration
        constants = JumpTrackGPSConfigConstants()
        gps_config.checkin_id = current_config.CheckinId
        gps_config.device_id = current_config.DeviceId
        gps_config.time_received = current_config.TimeReceived
        gps_config.from_device = current_config.FromDevice
        gps_config.nonce_received = current_config.NonceReceived
        gps_config.time_of_gps_config = current_config.TimeOfGpsConfig
        gps_config.flags = current_config.Flags
        gps_config.aiding_enabled = get_bits(
            current_config.Flags, constants.aiding_enabled_bits[0], constants.aiding_enabled_bits[1]
        )
        gps_config.gnss_update_frequency = get_bits(
            current_config.Flags, constants.gnss_update_frequency_bits[0], constants.gnss_update_frequency_bits[1]
        )
        gps_config.low_power_enabled = get_bits(
            current_config.Flags, constants.low_power_enable_bits[0], constants.low_power_enable_bits[1]
        )
        gps_config.target_accuracy = current_config.TargetFixAccuracy
        gps_config.target_pdop = current_config.TargetFixPdop

        return gps_config

    # ------------------------------------------------------------------------------------- JumpTrack Ble Beacon Config
    def send_jumptrack_ble_beacon_config(self, dut_id: int, new_config: JumpTrackBleBeaconConfig) -> None:
        log = Logger.get_test_case_logger()
        log.debug("Applying BLE Beacon configuration using CoreCloud v0.9")

        log.warning(f"USING DIRECT DATABASE ACCESS!")

        constants = JumpTrackBleBeaconConfigConstants()

        # Encode the flags
        flags = 0
        flags = set_bits(flags, constants.is_beacon_bits[0], constants.is_beacon_bits[1], new_config.is_beacon_enabled)
        flags = set_bits(
            flags,
            constants.is_ble_beacon_scan_adv_enabled_bits[0],
            constants.is_ble_beacon_scan_adv_enabled_bits[1],
            new_config.is_ble_beacon_scan_advertising_enabled,
        )

        # Generate the message
        b64_msg = struct.pack(
            constants.packed_format,
            constants.message_id,
            constants.message_length,
            int(datetime.utcnow().timestamp()),
            flags,
            new_config.beacon_period_seconds,
            new_config.beacon_duration_milliseconds,
            new_config.beacon_power,
            new_config.ble_session_key_crc,
        )

        # Send the config message
        self._send_config_msg(dut_id, b64_msg)

    def get_jumptrack_ble_beacon_config(self, dut_id: int) -> JumpTrackBleBeaconConfig | None:
        log = Logger.get_test_case_logger()
        log.debug("Getting BLE Beacon configuration using CoreCloud v0.9")

        log.warning(f"USING DIRECT DATABASE ACCESS!")

        # Return object
        ble_beacon_config = JumpTrackBleBeaconConfig()

        # Get the current BLE Beacon configuration
        current_config: JumpTrackBleBeaconConfigMsgTbl = None
        db = self.Session()
        current_config = (
            db.query(JumpTrackBleBeaconConfigMsgTbl)
            .filter_by(DeviceId=dut_id)
            .order_by(JumpTrackBleBeaconConfigMsgTbl.CheckinId.desc())
            .first()
        )
        current_config = deepcopy(current_config)
        db.close()

        if current_config is None:
            return None

        # Populate the BLE Beacon configuration
        constants = JumpTrackBleBeaconConfigConstants()
        ble_beacon_config.checkin_id = current_config.CheckinId
        ble_beacon_config.device_id = current_config.DeviceId
        ble_beacon_config.time_received = current_config.TimeReceived
        ble_beacon_config.from_device = current_config.FromDevice
        ble_beacon_config.nonce_received = current_config.NonceReceived
        ble_beacon_config.time_of_config = current_config.TimeOfConfig
        ble_beacon_config.flags = current_config.Flags
        ble_beacon_config.is_beacon_enabled = get_bits(
            current_config.Flags, constants.is_beacon_bits[0], constants.is_beacon_bits[1]
        )
        ble_beacon_config.is_ble_beacon_scan_advertising_enabled = get_bits(
            current_config.Flags,
            constants.is_ble_beacon_scan_adv_enabled_bits[0],
            constants.is_ble_beacon_scan_adv_enabled_bits[1],
        )
        ble_beacon_config.beacon_period_seconds = current_config.BeaconPeriod
        ble_beacon_config.beacon_duration_milliseconds = current_config.BeaconDuration
        ble_beacon_config.beacon_power = current_config.BeaconPower
        ble_beacon_config.ble_session_key_crc = current_config.BleSessionKeyCrc

        return ble_beacon_config

    # -------------------------------------------------------------------------------------- JumpTrack Emergency Config
    def send_jumptrack_emergency_config(self, dut_id: int, new_config: JumpTrackEmergencyConfig):
        log = Logger.get_test_case_logger()
        log.debug("Applying Emergency configuration using CoreCloud v0.9")

        log.warning(f"USING DIRECT DATABASE ACCESS!")

        constants = JumpTrackEmergencyConfigConstants()

        # Generate the message
        b64_msg = struct.pack(
            constants.packed_format,
            constants.message_id,
            constants.message_length,
            int(datetime.utcnow().timestamp()),
            new_config.time_limit_minutes,
            new_config.button_activation_time_seconds,
            new_config.button_timeout_seconds,
        )

        # Send the config message
        self._send_config_msg(dut_id, b64_msg)

    def get_jumptrack_emergency_config(self, dut_id: int) -> JumpTrackEmergencyConfig | None:
        log = Logger.get_test_case_logger()
        log.debug("Getting Emergency configuration using CoreCloud v0.9")

        log.warning(f"USING DIRECT DATABASE ACCESS!")

        # Return object
        emergency_config = JumpTrackEmergencyConfig()

        # Get the current Emergency configuration
        current_config: JumpTrackEmergencyConfigV2MsgTbl = None
        db = self.Session()
        current_config = db.query(JumpTrackEmergencyConfigV2MsgTbl).filter_by(DeviceId=dut_id).first()
        current_config = deepcopy(current_config)
        db.close()

        if current_config is None:
            return None

        # Populate the Emergency configuration
        emergency_config.device_id = current_config.DeviceId
        emergency_config.time_limit_minutes = current_config.TimeLimit
        emergency_config.button_activation_time_seconds = current_config.BtnActivationTime
        emergency_config.button_timeout_seconds = current_config.BtnTimeout

        return emergency_config

    # ------------------------------------------------------------------------------------------- JumpTrack Fall Config
    def send_jumptrack_fall_config(self, dut_id: int, new_config: JumpTrackFallConfig):
        log = Logger.get_test_case_logger()
        log.debug("Applying Fall configuration using CoreCloud v0.9")

        log.warning(f"USING DIRECT DATABASE ACCESS!")

        constants = JumpTrackFallConfigConstants()

        flags = 0
        flags = set_bits(
            flags,
            constants.jump_mode_enabled_bits[0],
            constants.jump_mode_enabled_bits[1],
            new_config.jump_mode_enabled,
        )

        # Generate the message
        b64_msg = struct.pack(
            constants.packed_format,
            constants.message_id,
            constants.message_length,
            int(datetime.utcnow().timestamp()),
            new_config.flags,
            new_config.jump_state_gps_report_period_seconds,
            new_config.jump_state_state_duration_minutes,
            new_config.free_fall_acceleration_threshold,
            new_config.free_fall_acceleration_duration_centiseconds,
            new_config.altitude_change_free_fall_trigger_ft_per_minute,
            new_config.altitude_change_jump_trigger_ft_per_minute,
            new_config.stable_altitude_num_samples,
            new_config.stable_altitude_threshold_ft,
        )

        # Send the config message
        self._send_config_msg(dut_id, b64_msg)

    def get_jumptrack_fall_config(self, dut_id: int) -> JumpTrackFallConfig | None:
        log = Logger.get_test_case_logger()
        log.debug("Getting Fall configuration using CoreCloud v0.9")

        log.warning(f"USING DIRECT DATABASE ACCESS!")

        # Return object
        fall_config = JumpTrackFallConfig()

        # Get the current Fall configuration
        current_config: JumpTrackFallConfigMsgTbl = None
        db = self.Session()
        current_config = db.query(JumpTrackFallConfigMsgTbl).filter_by(DeviceId=dut_id).first()
        current_config = deepcopy(current_config)
        db.close()

        if current_config is None:
            return None

        # Populate the Fall configuration
        constants = JumpTrackFallConfigConstants()
        fall_config.checkin_id = current_config.CheckinId
        fall_config.device_id = current_config.DeviceId
        fall_config.time_received = current_config.TimeReceived
        fall_config.from_device = current_config.FromDevice
        fall_config.nonce_received = current_config.NonceReceived
        fall_config.time_of_config = current_config.TimeOfConfig
        fall_config.flags = current_config.Flags
        fall_config.jump_mode_enabled = get_bits(
            current_config.Flags, constants.jump_mode_enabled_bits[0], constants.jump_mode_enabled_bits[1]
        )
        fall_config.jump_state_gps_report_period_seconds = current_config.JumpStateGpsReportPeriod
        fall_config.jump_state_state_duration_minutes = current_config.JumpStateTime
        fall_config.free_fall_acceleration_threshold = current_config.FreeFallAccThresh
        fall_config.free_fall_acceleration_duration_centiseconds = current_config.FreeFallAccDur
        fall_config.altitude_change_free_fall_trigger_ft_per_minute = current_config.FreeFallAltChangeThresh
        fall_config.altitude_change_jump_trigger_ft_per_minute = current_config.AltChangeJumpTrig
        fall_config.stable_altitude_num_samples = current_config.NumAltStableSamples
        fall_config.stable_altitude_threshold_ft = current_config.AltStabilityThreshold

        return fall_config

    # -------------------------------------------------------------------------------------- JumpTrack Ground Config V1
    def send_jumptrack_ground_config_v1(self, dut_id: int, new_config: JumpTrackGndConfigV1):
        log = Logger.get_test_case_logger()
        log.debug("Applying JumpTrack Ground configuration using CoreCloud v0.9")

        log.warning(f"USING DIRECT DATABASE ACCESS!")

        constants = JumpTrackGroundV1ConfigConstants()

        # Generate the message
        b64_msg = struct.pack(
            constants.packed_format,
            constants.message_id,
            constants.message_length,
            int(datetime.utcnow().timestamp()),
            new_config.gps_heartbeat_period_minutes,
            new_config.continuous_motion_period_seconds,
            new_config.stop_motion_timeout_seconds,
            new_config.heartbeat_acquisition_timeout_seconds,
            new_config.motion_acquisition_timeout_seconds,
            new_config.motion_acceleration_threshold,
            new_config.motion_acceleration_duration,
            new_config.start_motion_window_start,
            new_config.start_motion_window_end,
        )

        # Send the config message
        self._send_config_msg(dut_id, b64_msg)

    def get_jumptrack_ground_config_v1(self, dut_id: int) -> JumpTrackGndConfigV1 | None:
        log = Logger.get_test_case_logger()
        log.debug("Getting JumpTrack Ground configuration using CoreCloud v0.9")

        log.warning(f"USING DIRECT DATABASE ACCESS!")

        # Return object
        ground_config = JumpTrackGndConfigV1()

        # Get the current JumpTrack Ground configuration
        current_config: JumpTrackGndConfigMsgTbl = None
        db = self.Session()
        current_config = db.query(JumpTrackGndConfigMsgTbl).filter_by(DeviceId=dut_id).first()
        current_config = deepcopy(current_config)
        db.close()

        if current_config is None:
            return None

        # Populate the JumpTrack Ground configuration
        ground_config.checkin_id = current_config.CheckinId
        ground_config.device_id = current_config.DeviceId
        ground_config.time_received = current_config.TimeReceived
        ground_config.from_device = current_config.FromDevice
        ground_config.nonce_received = current_config.NonceReceived
        ground_config.time_of_config = current_config.TimeOfConfig
        ground_config.gps_heartbeat_period_minutes = current_config.GpsHeartbeatPeriod
        ground_config.continuous_motion_period_seconds = current_config.ContMotionPeriod
        ground_config.stop_motion_timeout_seconds = current_config.StopMotionPeriod
        ground_config.heartbeat_acquisition_timeout_seconds = current_config.HeartbeatAcqTimeout
        ground_config.motion_acquisition_timeout_seconds = current_config.MotionAcqTimeout
        ground_config.motion_acceleration_threshold = current_config.MotionThreshold
        ground_config.motion_acceleration_duration = current_config.MotionDuration
        ground_config.start_motion_window_start = current_config.StartMotionWindowStart
        ground_config.start_motion_window_end = current_config.StartMotionWindowEnd

        return ground_config

    # -------------------------------------------------------------------------------------- JumpTrack Ground Config V2
    def send_jumptrack_ground_config_v2(self, dut_id: int, new_config: JumpTrackGndConfigV2):
        log = Logger.get_test_case_logger()
        log.debug("Applying JumpTrack Ground configuration using CoreCloud v0.9")

        log.warning(f"USING DIRECT DATABASE ACCESS!")

        constants = JumpTrackGroundV2ConfigConstants()

        # Generate the message
        b64_msg = struct.pack(
            constants.packed_format,
            constants.message_id,
            constants.message_length,
            int(datetime.utcnow().timestamp()),
            new_config.gps_heartbeat_period_minutes,
            new_config.continuous_motion_period_seconds,
            new_config.stop_motion_timeout_seconds,
            new_config.heartbeat_acquisition_timeout_seconds,
            new_config.motion_acquisition_timeout_seconds,
            new_config.motion_acceleration_threshold,
            new_config.motion_acceleration_duration,
            new_config.start_motion_window_start_seconds,
            new_config.start_motion_window_end_seconds,
            new_config.motion_acquisition_on_time_seconds,
            new_config.motion_initial_acquisition_on_time_seconds,
            0,
        )

        # Send the config message
        self._send_config_msg(dut_id, b64_msg)

    def get_jumptrack_ground_config_v2(self, dut_id: int) -> JumpTrackGndConfigV2 | None:
        log = Logger.get_test_case_logger()
        log.debug("Getting JumpTrack Ground configuration using CoreCloud v0.9")

        log.warning(f"USING DIRECT DATABASE ACCESS!")

        # Return object
        ground_config = JumpTrackGndConfigV2()

        # Get the current JumpTrack Ground configuration
        current_config: JumpTrackGndConfigV2MsgTbl = None
        db = self.Session()
        current_config = db.query(JumpTrackGndConfigV2MsgTbl).filter_by(DeviceId=dut_id).first()
        current_config = deepcopy(current_config)
        db.close()

        if current_config is None:
            return None

        # Populate the JumpTrack Ground configuration
        ground_config.device_id = current_config.DeviceId
        ground_config.time_received = current_config.TimeReceived
        ground_config.from_device = current_config.FromDevice
        ground_config.nonce_received = current_config.NonceReceived
        ground_config.time_of_config = current_config.TimeOfConfig
        ground_config.gps_heartbeat_period_minutes = current_config.GpsHeartbeatPeriod
        ground_config.continuous_motion_period_seconds = current_config.ContMotionPeriod
        ground_config.stop_motion_timeout_seconds = current_config.MotionStopTimeout
        ground_config.heartbeat_acquisition_timeout_seconds = current_config.HeartbeatAcqTimeout
        ground_config.motion_acquisition_timeout_seconds = current_config.MotionAcqTimeout
        ground_config.motion_acceleration_threshold = current_config.MotionThreshold
        ground_config.motion_acceleration_duration = current_config.MotionDuration
        ground_config.start_motion_window_start_seconds = current_config.StartMotionWindowStart
        ground_config.start_motion_window_end_seconds = current_config.StartMotionWindowEnd
        ground_config.motion_acquisition_on_time_seconds = current_config.MotionAcqOnTime
        ground_config.motion_initial_acquisition_on_time_seconds = current_config.MotionInitAcqOnTime

        return ground_config

    # ------------------------------------------------------------------------------------------- JumpTrack HIPS Config
    def send_jumptrack_hips_config(self, dut_id: int, new_config: JumpTrackHipsConfig):
        log = Logger.get_test_case_logger()
        log.debug("Applying HIPS configuration using CoreCloud v0.9")

        log.warning(f"USING DIRECT DATABASE ACCESS!")

        constants = JumpTrackHipsConfigConstants()

        # Encode the flags
        flags = 0
        flags = set_bits(
            flags, constants.force_checkin_bits[0], constants.force_checkin_bits[1], new_config.force_checkin
        )
        flags = set_bits(
            flags, constants.scan_constantly_bits[0], constants.scan_constantly_bits[1], new_config.scan_constantly
        )
        flags = set_bits(flags, constants.mode_bits[0], constants.mode_bits[1], new_config.mode)

        # Generate the message
        b64_msg = struct.pack(
            constants.packed_format,
            constants.message_id,
            constants.message_length,
            int(datetime.utcnow().timestamp()),
            flags,
            new_config.group_code,
            new_config.source_user_id,
        )

        # Send the config message
        self._send_config_msg(dut_id, b64_msg)

    def get_jumptrack_hips_config(self, dut_id: int) -> JumpTrackHipsConfig | None:
        log = Logger.get_test_case_logger()
        log.debug("Getting HIPS configuration using CoreCloud v0.9")

        log.warning(f"USING DIRECT DATABASE ACCESS!")

        # Return object
        hips_config = JumpTrackHipsConfig()

        # Get the current HIPS configuration
        current_config: JumpTrackHipsConfigMsgTbl = None
        db = self.Session()
        current_config = db.query(JumpTrackHipsConfigMsgTbl).filter_by(DeviceId=dut_id).first()
        current_config = deepcopy(current_config)
        db.close()

        if current_config is None:
            return None

        # Populate the HIPS configuration
        constants = JumpTrackHipsConfigConstants()
        hips_config.device_id = current_config.DeviceId
        hips_config.time_received = current_config.TimeReceived
        hips_config.from_device = current_config.FromDevice
        hips_config.nonce_received = current_config.NonceReceived
        hips_config.time_of_config = current_config.TimeOfConfig
        hips_config.flags = current_config.Flags
        hips_config.force_checkin = get_bits(
            current_config.Flags, constants.force_checkin_bits[0], constants.force_checkin_bits[1]
        )
        hips_config.scan_constantly = get_bits(
            current_config.Flags, constants.scan_constantly_bits[0], constants.scan_constantly_bits[1]
        )
        hips_config.mode = get_bits(current_config.Flags, constants.mode_bits[0], constants.mode_bits[1])
        hips_config.group_code = current_config.GroupCode
        hips_config.source_user_id = current_config.SourceUserId

        return hips_config

    # ------------------------------------------------------------------------------------------- JumpTrack LoRa Config
    def send_jumptrack_lora_config(self, dut_id: int, new_config: JumpTrackLoRaConfig):
        log = Logger.get_test_case_logger()
        log.debug("Applying LoRa configuration using CoreCloud v0.9")

        log.warning(f"USING DIRECT DATABASE ACCESS!")

        constants = JumpTrackLoRaConfigConstants()

        # Encode the flags
        flags = 0
        flags = set_bits(
            flags, constants.lora_enabled_bits[0], constants.lora_enabled_bits[1], new_config.lora_enabled
        )

        # Generate the message
        b64_msg = struct.pack(
            constants.packed_format,
            constants.message_id,
            constants.message_length,
            int(datetime.utcnow().timestamp()),
            flags,
            constants.session_config_crc,
        )

        # Send the config message
        self._send_config_msg(dut_id, b64_msg)

    def get_jumptrack_lora_config(self, dut_id: int) -> JumpTrackLoRaConfig | None:
        log = Logger.get_test_case_logger()
        log.debug("Getting LoRa configuration using CoreCloud v0.9")

        log.warning(f"USING DIRECT DATABASE ACCESS!")

        # Return object
        lora_config = JumpTrackLoRaConfig()

        # Get the current LoRa configuration
        current_config: JumpTrackLoRaConfigMsgTbl = None
        db = self.Session()
        current_config = db.query(JumpTrackLoRaConfigMsgTbl).filter_by(DeviceId=dut_id).first()
        current_config = deepcopy(current_config)
        db.close()

        if not current_config:
            return None

        # Populate the LoRa configuration
        constants = JumpTrackLoRaConfigConstants()
        lora_config.checkin_id = current_config.CheckinId
        lora_config.device_id = current_config.DeviceId
        lora_config.time_received = current_config.TimeReceived
        lora_config.from_device = current_config.FromDevice
        lora_config.nonce_received = current_config.NonceReceived
        lora_config.time_of_lora_config = current_config.TimeOfLoRaConfig
        lora_config.flags = current_config.Flags
        lora_config.lora_enabled = get_bits(
            current_config.Flags, constants.lora_enabled_bits[0], constants.lora_enabled_bits[1]
        )
        lora_config.session_config_crc = current_config.SessionConfigCrc

        return lora_config

    # ------------------------------------------------------------------------------------------ JumpTrack Modem Config
    def send_jumptrack_modem_config(self, dut_id: int, new_config: JumpTrackModemConfig):
        log = Logger.get_test_case_logger()
        log.debug("Applying Modem configuration using CoreCloud v0.9")

        log.warning(f"USING DIRECT DATABASE ACCESS!")

        constants = JumpTrackModemConfigConstants()

        # Generate the message
        b64_msg = struct.pack(
            constants.packed_format,
            constants.message_id,
            constants.message_length,
            int(datetime.utcnow().timestamp()),
            new_config.short_backoff_time_seconds,
            new_config.normal_backoff_time_seconds,
            new_config.long_backoff_time_minutes,
            new_config.registration_timeout_period_minutes,
            new_config.socket_connection_timeout_period_minutes,
            new_config.connection_failure_threshold,
            new_config.socket_timeout_period_seconds,
        )

        # Send the config message
        self._send_config_msg(dut_id, b64_msg)

    def get_jumptrack_modem_config(self, dut_id: int) -> JumpTrackModemConfig | None:
        log = Logger.get_test_case_logger()
        log.debug("Getting Modem configuration using CoreCloud v0.9")

        log.warning(f"USING DIRECT DATABASE ACCESS!")

        # Return object
        modem_config = JumpTrackModemConfig()

        # Get the current Modem configuration
        current_config: JumpTrackModemConfigMsgTbl = None
        db = self.Session()
        current_config = db.query(JumpTrackModemConfigMsgTbl).filter_by(DeviceId=dut_id).first()
        current_config = deepcopy(current_config)
        db.close()

        if current_config is None:
            return None

        # Populate the Modem configuration
        modem_config.device_id = current_config.DeviceId
        modem_config.time_received = current_config.TimeReceived
        modem_config.from_device = current_config.FromDevice
        modem_config.nonce_received = current_config.NonceReceived
        modem_config.time_of_config = current_config.TimeOfConfig
        modem_config.short_backoff_time_seconds = current_config.ShortBackoff
        modem_config.normal_backoff_time_seconds = current_config.NormalBackoff
        modem_config.long_backoff_time_minutes = current_config.LongBackoff
        modem_config.registration_timeout_period_minutes = current_config.RegistrationTimeoutPeriod
        modem_config.socket_connection_timeout_period_minutes = current_config.SocketConnectionTimeoutPeriod
        modem_config.connection_failure_threshold = current_config.ConnectionFailureThreshold
        modem_config.socket_timeout_period_seconds = current_config.SocketTimeoutPeriod

        return modem_config

    # ---------------------------------------------------------------------------------------- JumpTrack Reboot Message
    def send_jumptrack_reboot_message(self, dut_id: int, reboot_message: JumpTrackRebootMessage):
        log = Logger.get_test_case_logger()
        log.debug("Applying Reboot message.")

        log.warning(f"USING DIRECT DATABASE ACCESS!")

        constants = JumpTrackRebootMessageConstants()

        # Encode the flags
        flags = 0
        flags = set_bits(
            flags, constants.reboot_9160_bits[0], constants.reboot_9160_bits[1], reboot_message.reboot_9160
        )
        flags = set_bits(
            flags, constants.reboot_52840_bits[0], constants.reboot_52840_bits[1], reboot_message.reboot_52840
        )
        flags = set_bits(
            flags, constants.do_hard_reset_bits[0], constants.do_hard_reset_bits[1], reboot_message.do_hard_reset
        )
        flags = set_bits(
            flags,
            constants.preserve_device_state_bits[0],
            constants.preserve_device_state_bits[1],
            reboot_message.preserve_device_state,
        )
        flags = set_bits(
            flags,
            constants.cold_restart_gps_bits[0],
            constants.cold_restart_gps_bits[1],
            reboot_message.cold_restart_gps,
        )

        # Generate the message
        b64_msg = struct.pack(
            constants.packed_format,
            constants.message_id,
            constants.message_length,
            constants.reboot_pattern,
            flags,
        )

        # Send the config message
        self._send_config_msg(dut_id, b64_msg)

    def get_jumptrack_reboot_message(self, dut_id: int) -> JumpTrackRebootMessage | None:
        log = Logger.get_test_case_logger()
        log.debug("Getting Reboot message.")

        log.warning(f"USING DIRECT DATABASE ACCESS!")

        # Return object
        reboot_message = JumpTrackRebootMessage()

        # Get the last Reboot message
        last_message: JumpTrackRebootMsgTbl = None
        db = self.Session()
        last_message = db.query(JumpTrackRebootMsgTbl).filter_by(DeviceId=dut_id).first()
        last_message = deepcopy(last_message)
        db.close()

        if last_message is None:
            return None

        # Populate the Reboot message
        constants = JumpTrackRebootMessageConstants()
        reboot_message.device_id = last_message.DeviceId
        reboot_message.time_received = last_message.TimeReceived
        reboot_message.from_device = last_message.FromDevice
        reboot_message.nonce_received = last_message.NonceReceived
        reboot_message.time_received = last_message.TimeReceived
        reboot_message.reboot_pattern = last_message.RebootPattern
        reboot_message.reboot_flags = last_message.RebootFlags
        reboot_message.reboot_9160 = get_bits(
            last_message.RebootFlags, constants.reboot_9160_bits[0], constants.reboot_9160_bits[1]
        )
        reboot_message.reboot_52840 = get_bits(
            last_message.RebootFlags, constants.reboot_52840_bits[0], constants.reboot_52840_bits[1]
        )
        reboot_message.do_hard_reset = get_bits(
            last_message.RebootFlags, constants.do_hard_reset_bits[0], constants.do_hard_reset_bits[1]
        )
        reboot_message.preserve_device_state = get_bits(
            last_message.RebootFlags, constants.preserve_device_state_bits[0], constants.preserve_device_state_bits[1]
        )
        reboot_message.cold_restart_gps = get_bits(
            last_message.RebootFlags, constants.cold_restart_gps_bits[0], constants.cold_restart_gps_bits[1]
        )
        reboot_message.reserved = get_bits(
            last_message.RebootFlags, constants.reserved_bits[0], constants.reserved_bits[1]
        )

        return reboot_message

    # -------------------------------------------------------------------------------------------- JumpTrack SIM Config
    def send_jumptrack_sim_config(self, dut_id: int, new_config: JumpTrackSimConfig):
        log = Logger.get_test_case_logger()
        log.debug("Applying SIM configuration using CoreCloud v0.9")

        log.warning(f"USING DIRECT DATABASE ACCESS!")

        constants = JumpTrackSimConfigConstants()

        # Encode the flags
        flags = 0
        flags = set_bits(
            flags,
            constants.prevent_sim_swapping_bits[0],
            constants.prevent_sim_swapping_bits[1],
            new_config.prevent_sim_swapping,
        )
        flags = set_bits(
            flags,
            constants.default_sim_select_bits[0],
            constants.default_sim_select_bits[1],
            new_config.default_sim_select,
        )

        # Generate the message
        b64_msg = struct.pack(
            constants.packed_format,
            constants.message_id,
            constants.message_length,
            int(datetime.utcnow().timestamp()),
            flags,
        )

        # Send the config message
        self._send_config_msg(dut_id, b64_msg)

    def get_jumptrack_sim_config(self, dut_id: int) -> JumpTrackSimConfig | None:
        log = Logger.get_test_case_logger()
        log.debug("Getting SIM configuration using CoreCloud v0.9")

        log.warning(f"USING DIRECT DATABASE ACCESS!")

        # Return object
        sim_config = JumpTrackSimConfig()

        # Get the current SIM configuration
        current_config: JumpTrackSimConfigMsgTbl = None
        db = self.Session()
        current_config = db.query(JumpTrackSimConfigMsgTbl).filter_by(DeviceId=dut_id).first()
        current_config = deepcopy(current_config)
        db.close()

        if current_config is None:
            return None

        # Populate the SIM configuration
        constants = JumpTrackSimConfigConstants()
        sim_config.device_id = current_config.DeviceId
        sim_config.time_received = current_config.TimeReceived
        sim_config.from_device = current_config.FromDevice
        sim_config.nonce_received = current_config.NonceReceived
        sim_config.time_of_config = current_config.TimeOfConfig
        sim_config.flags = current_config.Flags
        sim_config.prevent_sim_swapping = get_bits(
            current_config.Flags, constants.prevent_sim_swapping_bits[0], constants.prevent_sim_swapping_bits[1]
        )
        sim_config.default_sim_select = get_bits(
            current_config.Flags, constants.default_sim_select_bits[0], constants.default_sim_select_bits[1]
        )

        return sim_config

    # ---------------------------------------------------------------------------------- JumpTrack Socket Server Config
    def send_jumptrack_server_config(self, dut_id: int, new_config: JumpTrackServerConfig):
        log = Logger.get_test_case_logger()
        log.debug("Applying Server configuration using CoreCloud v0.9")

        log.warning(f"USING DIRECT DATABASE ACCESS!")

        constants = JumpTrackServerConfigConstants()

        # Encode the flags
        flags = 0
        flags = set_bits(flags, constants.server_type_bits[0], constants.server_type_bits[1], new_config.server_type)
        flags = set_bits(
            flags,
            constants.production_server_bits[0],
            constants.production_server_bits[1],
            new_config.production_server,
        )
        flags = set_bits(flags, constants.write_bits[0], constants.write_bits[1], new_config.write)

        # Encode the URL
        url_encoded = new_config.url.encode() + b"\x00"

        # Update the packed format
        base_packed_format = constants.packed_format
        base_packed_format += f"{len(url_encoded)}s"

        # Calculate the message length
        _flags_size = 0  # bytes
        _port_size = 2  # bytes
        _url_size = len(url_encoded)  # bytes

        message_length = _flags_size + _port_size + _url_size

        # Generate the message
        b64_msg = struct.pack(
            base_packed_format,
            constants.message_id,
            message_length,
            flags,
            new_config.port,
            url_encoded,
        )

        # Send the config message
        self._send_config_msg(dut_id, b64_msg)

    def get_jumptrack_server_config(self, dut_id: int) -> JumpTrackServerConfig | None:
        log = Logger.get_test_case_logger()
        log.debug("Getting Server configuration using CoreCloud v0.9")

        log.warning(f"USING DIRECT DATABASE ACCESS!")

        # Return object
        server_config = JumpTrackServerConfig()

        # Get the current Server configuration
        current_config: JumpTrackServerConfigMsgTbl = None
        db = self.Session()
        current_config = db.query(JumpTrackServerConfigMsgTbl).filter_by(DeviceId=dut_id).first()
        current_config = deepcopy(current_config)
        db.close()

        if current_config is None:
            return None

        # Populate the Server configuration
        constants = JumpTrackServerConfigConstants()
        server_config.device_id = current_config.DeviceId
        server_config.time_received = current_config.TimeReceived
        server_config.from_device = current_config.FromDevice
        server_config.nonce_received = current_config.NonceReceived
        server_config.time_received = current_config.TimeReceived
        server_config.flags = current_config.Flags
        server_config.server_type = get_bits(
            current_config.Flags, constants.server_type_bits[0], constants.server_type_bits[1]
        )
        server_config.production_server = get_bits(
            current_config.Flags, constants.production_server_bits[0], constants.production_server_bits[1]
        )
        server_config.write = get_bits(current_config.Flags, constants.write_bits[0], constants.write_bits[1])
        server_config.port = current_config.Port
        server_config.url = current_config.ServerUrl

        return server_config

    # -----------------------------------------------------------------------------------------------------------------
    #                                                                                            Position Message Table
    # -----------------------------------------------------------------------------------------------------------------

    def _repackage_position_message(self, raw_position_message: JumpTrack1CMsgTbl) -> JumpTrackPositionMessage:
        log = Logger.get_test_case_logger()
        log.debug("Repackaging the Position message.")

        # Return object
        position_message = JumpTrackPositionMessage()

        # 1:1 mappings
        position_message.checkin_id = raw_position_message.CheckinId
        position_message.device_id = raw_position_message.DeviceId
        position_message.time_received = raw_position_message.TimeReceived
        position_message.from_device = raw_position_message.FromDevice
        position_message.flags = raw_position_message.Flags
        position_message.is_valid_gps_fix = raw_position_message.IsValidGpsFix
        position_message.is_gps_indoors = raw_position_message.IsGpsIndoors
        position_message.is_in_motion = raw_position_message.IsInMotion
        position_message.update_reason = raw_position_message.UpdateReason
        position_message.latitude = raw_position_message.Latitude
        position_message.longitude = raw_position_message.Longitude
        position_message.ttf = raw_position_message.Ttf
        position_message.accuracy = raw_position_message.Accuracy
        position_message.altitude_gps = raw_position_message.AltitudeGps
        position_message.altitude_calculated = raw_position_message.AltitudeCalculated
        position_message.ground_speed = raw_position_message.GroundSpeed
        position_message.heading = raw_position_message.Heading
        position_message.time_of_fix = raw_position_message.TimeOfFix
        position_message.battery_voltage = raw_position_message.BatteryVoltage
        position_message.battery_percentage = raw_position_message.BatteryPercentage
        position_message.air_pressure_in_hg = raw_position_message.AirPressureInHg
        position_message.temperature = raw_position_message.Temperature
        position_message.average_force = raw_position_message.AverageForce
        position_message.max_force = raw_position_message.MaxForce
        position_message.account_id = raw_position_message.AccountId
        position_message.data_source = raw_position_message.DataSource
        position_message.crc = raw_position_message.Crc
        position_message.nonce_received = raw_position_message.NonceReceived
        position_message.f_cnt_up = raw_position_message.FCntUp
        position_message.f_cnt_dn = raw_position_message.FCntDn
        position_message.gateway_lat = raw_position_message.GatewayLat
        position_message.gateway_lon = raw_position_message.GatewayLon
        position_message.gateway_id = raw_position_message.GatewayId
        position_message.gateway_count = raw_position_message.GatewayCount
        position_message.gateway_rssi = raw_position_message.GatewayRssi
        position_message.gateway_snr = raw_position_message.GatewaySnr
        position_message.channel = raw_position_message.Channel
        position_message.spreading_factor = raw_position_message.SpreadingFactor
        position_message.network_time_received = raw_position_message.NetworkTimeReceived
        position_message.fix_type = raw_position_message.FixType
        position_message.num_satellites = raw_position_message.NumSatellites
        position_message.psm_state = raw_position_message.PsmState
        position_message.pdop = raw_position_message.Pdop
        position_message.bms_temp = raw_position_message.BmsTemp
        position_message.gps_vert_accuracy = raw_position_message.GpsVertAccuracy
        position_message.emergency_event_id = raw_position_message.EmergencyEventId

        constants = JumpTrackPositionV5MessageConstants()

        # Decode the flags
        position_message.flags_reserved_31_28 = get_bits(
            position_message.flags, constants.reserved_31_28_bits[0], constants.reserved_31_28_bits[1]
        )
        position_message.flags_aiding_data_used = get_bits(
            position_message.flags, constants.aiding_data_used_bits[0], constants.aiding_data_used_bits[1]
        )
        position_message.flags_on_charger = get_bits(
            position_message.flags, constants.on_charger_bits[0], constants.on_charger_bits[1]
        )
        position_message.flags_fix_type = get_bits(
            position_message.flags, constants.fix_type_bits[0], constants.fix_type_bits[1]
        )
        position_message.flags_num_of_satellites = get_bits(
            position_message.flags, constants.num_of_satellites_bits[0], constants.num_of_satellites_bits[1]
        )
        position_message.flags_confirmed_time_available = get_bits(
            position_message.flags,
            constants.confirmed_time_available_bits[0],
            constants.confirmed_time_available_bits[1],
        )
        position_message.flags_confirmed_time = get_bits(
            position_message.flags, constants.confirmed_time_bits[0], constants.confirmed_time_bits[1]
        )
        position_message.flags_confirmed_date = get_bits(
            position_message.flags, constants.confirmed_date_bits[0], constants.confirmed_date_bits[1]
        )
        position_message.flags_valid_time = get_bits(
            position_message.flags, constants.valid_time_bits[0], constants.valid_time_bits[1]
        )
        position_message.flags_valid_date = get_bits(
            position_message.flags, constants.valid_date_bits[0], constants.valid_date_bits[1]
        )
        position_message.flags_gnss_fix_ok = get_bits(
            position_message.flags, constants.gnss_fix_ok_bits[0], constants.gnss_fix_ok_bits[1]
        )
        position_message.flags_gnss_fix_valid = get_bits(
            position_message.flags, constants.gnss_fix_valid_bits[0], constants.gnss_fix_valid_bits[1]
        )
        position_message.flags_psm_state = get_bits(
            position_message.flags, constants.psm_state_bits[0], constants.psm_state_bits[1]
        )
        position_message.flags_reserved_7_5 = get_bits(
            position_message.flags, constants.reserved_7_5_bits[0], constants.reserved_7_5_bits[1]
        )
        position_message.flags_update_reason = get_bits(
            position_message.flags, constants.update_reason_bits[0], constants.update_reason_bits[1]
        )
        position_message.flags_in_motion = get_bits(
            position_message.flags, constants.in_motion_bits[0], constants.in_motion_bits[1]
        )

        # Decode the fix type
        position_message.fix_type_str = constants.fix_type_map.get(
            position_message.fix_type, f"Unknown: {position_message.fix_type}"
        )

        # Decode the PSM state
        position_message.psm_state_str = constants.psm_state_map.get(
            position_message.psm_state, f"Unknown: {position_message.psm_state}"
        )

        # Decode the update reason
        position_message.update_reason_str = constants.update_reason_map.get(
            position_message.update_reason, f"Unknown: {position_message.update_reason}"
        )

        return position_message

    def get_last_jumptrack_position_message(self, dut_id: int) -> JumpTrackPositionMessage | None:
        log = Logger.get_test_case_logger()
        log.debug("Getting the last Position message.")

        # Return object
        position_message: JumpTrackPositionMessage = None

        # Get the last Position message
        if self.use_db_over_api:
            log.warning(f"USING DIRECT DATABASE ACCESS!")

            raw_position_message: JumpTrack1CMsgTbl = None
            db = self.Session()
            raw_position_message = (
                db.query(JumpTrack1CMsgTbl)
                .filter_by(DeviceId=dut_id)
                .order_by(JumpTrack1CMsgTbl.CheckinId.desc())
                .first()
            )
            raw_position_message = deepcopy(raw_position_message)
            db.close()

            if not raw_position_message:
                return None

            position_message = self._repackage_position_message(raw_position_message)
        else:  # Use the API
            raw_position_message: List[dict] = self._api_query(
                endpoint="jumptrack/GetPositions",
                query={"DeviceIds": [dut_id], "Limit": 1, "OrderByCheckinId": "desc"},
            )

            if not raw_position_message:
                return None

            # The API returns a list of dictionaries in the same format as the JumpTrackPositionMessage object
            try:
                position_message = JumpTrackPositionMessage(**raw_position_message[0])
            except TypeError as e:
                log.error(f"Error populating the object: {e}")
                raise e

        return position_message

    def get_jumptrack_position_messages_since_time(
        self, dut_id: int, start_time: datetime, end_time: datetime = None
    ) -> List[JumpTrackPositionMessage] | None:
        """
        Get Position messages since a specific time.

        Parameters:
            dut_id (int): The Device ID.
            start_time (datetime): The time to get Position messages since.
            end_time (datetime): Optional; The time to get Position messages until.

        Returns:
            List[JumpTrackPositionMessage] | None: A list of Position messages since the time, or None if no messages are found.

        Raises:
            TypeError: If there is an error converting the json from the API to the JumpTrackPositionMessage object.
        """
        log = Logger.get_test_case_logger()
        log.debug("Getting Position messages since a specific time.")

        # Return object
        position_messages: List[JumpTrackPositionMessage] = []

        # Get the Position messages
        if self.use_db_over_api:
            log.warning(f"USING DIRECT DATABASE ACCESS!")

            raw_position_messages: List[JumpTrack1CMsgTbl] = []
            db = self.Session()
            raw_position_messages = (
                db.query(JumpTrack1CMsgTbl)
                .filter(JumpTrack1CMsgTbl.DeviceId == dut_id, JumpTrack1CMsgTbl.TimeReceived > start_time)
                .order_by(JumpTrack1CMsgTbl.CheckinId.desc())
            )

            if end_time is not None:
                raw_position_messages = raw_position_messages.filter(JumpTrack1CMsgTbl.TimeReceived < end_time)

            raw_position_messages = raw_position_messages.all()
            raw_position_messages = deepcopy(raw_position_messages)
            db.close()

            if not raw_position_messages:
                return None

            # Repackage the Position messages
            for raw_position_message in raw_position_messages:
                if raw_position_message is None:
                    continue
                position_message: JumpTrackPositionMessage = self._repackage_position_message(raw_position_message)
                position_messages.append(position_message)
        else:
            _start_time = start_time.strftime("%Y-%m-%dT%H:%M:%S")
            _end_time = end_time.strftime("%Y-%m-%dT%H:%M:%S") if end_time else ""
            raw_position_messages: List[dict] = self._api_query(
                endpoint="jumptrack/GetPositions",
                query={
                    "DeviceIds": [dut_id],
                    "TimeReceivedGreaterThan": _start_time,
                    "TimeReceivedLessThan": _end_time,
                    "OrderByCheckinId": "desc",
                },
            )

            if not raw_position_messages:
                return None

            # The API returns a list of dictionaries in the same format as the JumpTrackPositionMessage object
            try:
                position_messages = [
                    JumpTrackPositionMessage(**raw_position_message) for raw_position_message in raw_position_messages
                ]
            except TypeError as e:
                log.error(f"Error populating the object: {e}")
                raise e

        return position_messages

    def get_jumptrack_position_messages_since_checkin_id(
        self, dut_id: int, checkin_id: int
    ) -> List[JumpTrackPositionMessage] | None:
        """
        Get Position messages since a specific CheckinId.

        Parameters:
            dut_id (int): The Device ID.
            checkin_id (int): The CheckinId to get Position messages since.

        Returns:
            List[JumpTrackPositionMessage] | None: A list of Position messages since the CheckinId, or None if no messages are found.

        Raises:
            TypeError: If there is an error converting the json from the API to the JumpTrackPositionMessage object.

        """
        log = Logger.get_test_case_logger()
        log.debug("Getting Position messages since a specific CheckinId.")

        # Return object
        position_messages: List[JumpTrackPositionMessage] = []

        # Get the Position messages
        if self.use_db_over_api:
            log.warning(f"USING DIRECT DATABASE ACCESS!")

            raw_position_messages: List[JumpTrack1CMsgTbl] = []
            db = self.Session()
            raw_position_messages = (
                db.query(JumpTrack1CMsgTbl)
                .filter(JumpTrack1CMsgTbl.DeviceId == dut_id, JumpTrack1CMsgTbl.CheckinId > checkin_id)
                .order_by(JumpTrack1CMsgTbl.CheckinId.desc())
                .all()
            )
            raw_position_messages = deepcopy(raw_position_messages)
            db.close()

            if not raw_position_messages:
                return None

            # Repackage the Position messages
            for raw_position_message in raw_position_messages:
                if raw_position_message is None:
                    continue

                position_message: JumpTrackPositionMessage = self._repackage_position_message(raw_position_message)
                position_messages.append(position_message)
        else:
            raw_position_messages: List[dict] = self._api_query(
                endpoint="jumptrack/GetPositions",
                query={"DeviceIds": [dut_id], "CheckinIdGreaterThan": checkin_id, "OrderByCheckinId": "desc"},
            )

            if not raw_position_messages:
                return None

            # The API returns a list of dictionaries in the same format as the JumpTrackPositionMessage object
            try:
                position_messages = [
                    JumpTrackPositionMessage(**raw_position_message) for raw_position_message in raw_position_messages
                ]
            except TypeError as e:
                log.error(f"Error populating the object: {e}")
                raise e

        return position_messages

    # -----------------------------------------------------------------------------------------------------------------
    #                                                                                                Boot Message Table
    # -----------------------------------------------------------------------------------------------------------------
    def _repackage_boot_message(self, raw_boot_message: JumpTrackBootMessageTbl) -> JumpTrackBootMessage:
        log = Logger.get_test_case_logger()
        log.debug("Repackaging the Boot message.")

        # Return object
        boot_message = JumpTrackBootMessage()

        # 1:1 mappings
        boot_message.checkin_id = raw_boot_message.CheckinId
        boot_message.device_id = raw_boot_message.DeviceId
        boot_message.time_received = raw_boot_message.TimeReceived
        boot_message.from_device = raw_boot_message.FromDevice
        boot_message.nonce_received = raw_boot_message.NonceReceived
        boot_message.boot_reason = raw_boot_message.BootReason
        boot_message.number_of_exceptions = raw_boot_message.NumberOfExceptions
        boot_message.time_of_boot = raw_boot_message.TimeOfBoot

        constants = JumpTrackBootMessageConstants()

        # Decode the boot reason
        flag_mcu_type = get_bits(boot_message.boot_reason, constants.mcu_type_bits[0], constants.mcu_type_bits[1])
        flag_fw_triggered = get_bits(
            boot_message.boot_reason, constants.fw_triggered_bits[0], constants.fw_triggered_bits[1]
        )
        flag_boot_reason = get_bits(
            boot_message.boot_reason, constants.boot_reason_bits[0], constants.boot_reason_bits[1]
        )

        # Decode the MCU type
        boot_message.mcu_type = constants.mcu_type_map.get(flag_mcu_type, f"Unknown: {flag_mcu_type}")

        # Decode the FW triggered reset
        boot_message.fw_triggered = constants.fw_triggered_map.get(flag_fw_triggered, f"Unknown: {flag_fw_triggered}")

        # Decode the boot reason
        boot_message.boot_reason_str = constants.boot_reason_map.get(flag_boot_reason, f"Unknown: {flag_boot_reason}")

        return boot_message

    def get_last_jumptrack_boot_message(self, dut_id: int) -> JumpTrackBootMessage | None:
        log = Logger.get_test_case_logger()
        log.debug("Getting the last Boot message.")

        # Return object
        boot_message: JumpTrackBootMessage = None

        # Get the last Boot message
        if self.use_db_over_api:
            log.warning(f"USING DIRECT DATABASE ACCESS!")

            raw_boot_message: JumpTrackBootMessageTbl = None
            db = self.Session()
            raw_boot_message = (
                db.query(JumpTrackBootMessageTbl)
                .filter_by(DeviceId=dut_id)
                .order_by(JumpTrackBootMessageTbl.CheckinId.desc())
                .first()
            )
            raw_boot_message = deepcopy(raw_boot_message)
            db.close()

            if not raw_boot_message:
                return None

            boot_message = self._repackage_boot_message(raw_boot_message)
        else:  # Use the API
            raise NotImplementedError("API not implemented for get_last_jumptrack_boot_message")

        return boot_message

    def get_jumptrack_boot_messages_since_time(
        self, dut_id: int, start_time: datetime, end_time: datetime = None
    ) -> List[JumpTrackBootMessage] | None:
        log = Logger.get_test_case_logger()
        log.debug("Getting Boot messages since a specific time.")

        # Return object
        boot_messages: List[JumpTrackBootMessage] = []

        # Get the Boot messages
        if self.use_db_over_api:
            log.warning(f"USING DIRECT DATABASE ACCESS!")

            raw_boot_messages: List[JumpTrackBootMessageTbl] = []
            db = self.Session()
            raw_boot_messages = (
                db.query(JumpTrackBootMessageTbl)
                .filter(JumpTrackBootMessageTbl.DeviceId == dut_id, JumpTrackBootMessageTbl.TimeReceived > start_time)
                .order_by(JumpTrackBootMessageTbl.CheckinId.desc())
            )

            if end_time is not None:
                raw_boot_messages = raw_boot_messages.filter(JumpTrackBootMessageTbl.TimeReceived < end_time)

            raw_boot_messages = raw_boot_messages.all()
            raw_boot_messages = deepcopy(raw_boot_messages)
            db.close()

            if not raw_boot_messages:
                return None

            # Repackage the Boot messages
            for raw_boot_message in raw_boot_messages:
                if raw_boot_message is None:
                    continue
                boot_message: JumpTrackBootMessage = self._repackage_boot_message(raw_boot_message)
                boot_messages.append(boot_message)
        else:
            raise NotImplementedError("API not implemented for get_jumptrack_boot_messages_since_time")

        return boot_messages

    def get_jumptrack_boot_messages_since_checkin_id(
        self, dut_id: int, checkin_id: int
    ) -> List[JumpTrackBootMessage] | None:
        log = Logger.get_test_case_logger()
        log.debug("Getting Boot messages since a specific CheckinId.")

        # Return object
        boot_messages: List[JumpTrackBootMessage] = []

        # Get the Boot messages
        if self.use_db_over_api:
            log.warning(f"USING DIRECT DATABASE ACCESS!")

            raw_boot_messages: List[JumpTrackBootMessageTbl] = []
            db = self.Session()
            raw_boot_messages = (
                db.query(JumpTrackBootMessageTbl)
                .filter(JumpTrackBootMessageTbl.DeviceId == dut_id, JumpTrackBootMessageTbl.CheckinId > checkin_id)
                .order_by(JumpTrackBootMessageTbl.CheckinId.desc())
                .all()
            )
            raw_boot_messages = deepcopy(raw_boot_messages)
            db.close()

            if not raw_boot_messages:
                return None

            # Repackage the Boot messages
            for raw_boot_message in raw_boot_messages:
                if raw_boot_message is None:
                    continue

                boot_message: JumpTrackBootMessage = self._repackage_boot_message(raw_boot_message)
                boot_messages.append(boot_message)
        else:
            raise NotImplementedError("API not implemented for get_jumptrack_boot_messages_since_checkin_id")

        return boot_messages

    # -----------------------------------------------------------------------------------------------------------------
    #                                                                                            Downlink Message Table
    # -----------------------------------------------------------------------------------------------------------------
    def _repackage_downlink_message(self, raw_downlink_message: DownlinkMessagesTbl) -> DownlinkMessage:
        log = Logger.get_test_case_logger()
        log.debug("Repackaging the Downlink message.")

        # Return object
        downlink_message = DownlinkMessage()

        # 1:1 mappings
        downlink_message.downlink_message_id = raw_downlink_message.DownlinkMessageId
        downlink_message.device_id = raw_downlink_message.DeviceId
        downlink_message.device_type_id = raw_downlink_message.DeviceTypeId
        downlink_message.time_queued = raw_downlink_message.TimeQueued
        downlink_message.nonce_sent = raw_downlink_message.NonceSent
        downlink_message.is_acked = raw_downlink_message.IsAcked
        downlink_message.is_naked = raw_downlink_message.IsNaked
        downlink_message.message = raw_downlink_message.Message

        return downlink_message

    def get_last_downlink_message(self, dut_id: int) -> DownlinkMessage:
        log = Logger.get_test_case_logger()
        log.debug("Getting the last Downlink message.")

        # Return object
        downlink_message: DownlinkMessage = None

        # Get the last Downlink message
        if self.use_db_over_api:
            log.warning(f"USING DIRECT DATABASE ACCESS!")

            raw_downlink_message: DownlinkMessagesTbl = None
            db = self.Session()
            raw_downlink_message = (
                db.query(DownlinkMessagesTbl)
                .filter_by(DeviceId=dut_id)
                .order_by(DownlinkMessagesTbl.DownlinkMessageId.desc())
                .first()
            )
            raw_downlink_message = deepcopy(raw_downlink_message)
            db.close()

            if not raw_downlink_message:
                return None

            downlink_message = self._repackage_downlink_message(raw_downlink_message)
        else:  # Use the API
            raise NotImplementedError("API not implemented for get_last_downlink_message")

        return downlink_message

    def get_downlink_messages_since_time(
        self, dut_id: int, start_time: datetime, end_time: datetime = None
    ) -> List[DownlinkMessage] | None:
        log = Logger.get_test_case_logger()
        log.debug("Getting Downlink messages since a specific time.")

        # Return object
        downlink_messages: List[DownlinkMessage] = []

        # Get the Downlink messages
        if self.use_db_over_api:
            log.warning(f"USING DIRECT DATABASE ACCESS!")

            raw_downlink_messages: List[DownlinkMessagesTbl] = []
            db = self.Session()
            raw_downlink_messages = (
                db.query(DownlinkMessagesTbl)
                .filter(DownlinkMessagesTbl.DeviceId == dut_id, DownlinkMessagesTbl.TimeQueued > start_time)
                .order_by(DownlinkMessagesTbl.DownlinkMessageId.desc())
            )

            if end_time is not None:
                raw_downlink_messages = raw_downlink_messages.filter(DownlinkMessagesTbl.TimeQueued < end_time)

            raw_downlink_messages = raw_downlink_messages.all()
            raw_downlink_messages = deepcopy(raw_downlink_messages)
            db.close()

            if not raw_downlink_messages:
                return None

            # Repackage the Downlink messages
            for raw_downlink_message in raw_downlink_messages:
                if raw_downlink_message is None:
                    continue
                downlink_message: DownlinkMessage = self._repackage_downlink_message(raw_downlink_message)
                downlink_messages.append(downlink_message)
        else:
            raise NotImplementedError("API not implemented for get_downlink_messages_since_time")

        return downlink_messages

    def get_downlink_messages_since_downlink_message_id(
        self, dut_id: int, downlink_message_id: int
    ) -> List[DownlinkMessage] | None:
        log = Logger.get_test_case_logger()
        log.debug("Getting Downlink messages since a specific DownlinkMessageId.")

        # Return object
        downlink_messages: List[DownlinkMessage] = []

        # Get the Downlink messages
        if self.use_db_over_api:
            log.warning(f"USING DIRECT DATABASE ACCESS!")

            raw_downlink_messages: List[DownlinkMessagesTbl] = []
            db = self.Session()
            raw_downlink_messages = (
                db.query(DownlinkMessagesTbl)
                .filter(
                    DownlinkMessagesTbl.DeviceId == dut_id, DownlinkMessagesTbl.DownlinkMessageId > downlink_message_id
                )
                .order_by(DownlinkMessagesTbl.DownlinkMessageId.desc())
                .all()
            )
            raw_downlink_messages = deepcopy(raw_downlink_messages)
            db.close()

            if not raw_downlink_messages:
                return None

            # Repackage the Downlink messages
            for raw_downlink_message in raw_downlink_messages:
                if raw_downlink_message is None:
                    continue

                downlink_message: DownlinkMessage = self._repackage_downlink_message(raw_downlink_message)
                downlink_messages.append(downlink_message)
        else:
            raise NotImplementedError("API not implemented for get_downlink_messages_since_downlink_message_id")

        return downlink_messages

    # -----------------------------------------------------------------------------------------------------------------
    #                                                                                    Firmware Version Message Table
    # -----------------------------------------------------------------------------------------------------------------
    def _repackage_jumptrack_firmware_v2_message(
        self, raw_fw_message: JumpTrackFirmwareV2MessageTbl
    ) -> JumpTrackFirmwareMessage:
        log = Logger.get_test_case_logger()
        log.debug("Repackaging the Firmware Version message.")

        # Return object
        fw_message = JumpTrackFirmwareMessage()

        # 1:1 mappings
        fw_message.checkin_id = raw_fw_message.CheckinId
        fw_message.device_id = raw_fw_message.DeviceId
        fw_message.time_received = raw_fw_message.TimeReceived
        fw_message.from_device = raw_fw_message.FromDevice
        fw_message.nonce_received = raw_fw_message.NonceReceived
        fw_message.bootloader_91_version = raw_fw_message.Bootloader9160Version
        fw_message.bootloader_52_version = raw_fw_message.Bootloader52833Version
        fw_message.application_91_version = raw_fw_message.Application9160Version
        fw_message.application_52_version = raw_fw_message.Application52833Version

        # Decode the firmware versions
        constants = JumpTrackFirmwareV2MessageConstants()
        fw_message.nrf91_fw_type_id = get_bits(
            fw_message.application_91_version, constants.device_type_bits[0], constants.device_type_bits[1]
        )
        fw_message.nrf91_fw_version = get_bits(
            fw_message.application_91_version, constants.device_version_bits[0], constants.device_version_bits[1]
        )
        fw_message.nrf91_fw_is_manufacturing = constants.device_type_map.get(
            fw_message.nrf91_fw_type_id, f"Unknown: {fw_message.nrf91_fw_type_id}"
        ).is_manufacturing
        fw_message.nrf91_fw_target_board = constants.device_type_map.get(
            fw_message.nrf91_fw_type_id, f"Unknown: {fw_message.nrf91_fw_type_id}"
        ).board_name
        fw_message.nrf91_fw_target_board_version = constants.device_type_map.get(
            fw_message.nrf91_fw_type_id, f"Unknown: {fw_message.nrf91_fw_type_id}"
        ).board_revision
        fw_message.nrf91_fw_target_microcontroller = constants.device_type_map.get(
            fw_message.nrf91_fw_type_id, f"Unknown: {fw_message.nrf91_fw_type_id}"
        ).target_microcontroller
        fw_message.nrf91_fw_product_variant = constants.device_type_map.get(
            fw_message.nrf91_fw_type_id, f"Unknown: {fw_message.nrf91_fw_type_id}"
        ).product_name

        fw_message.nrf52_fw_type_id = get_bits(
            fw_message.application_52_version, constants.device_type_bits[0], constants.device_type_bits[1]
        )
        fw_message.nrf52_fw_version = get_bits(
            fw_message.application_52_version, constants.device_version_bits[0], constants.device_version_bits[1]
        )
        fw_message.nrf52_fw_is_manufacturing = constants.device_type_map.get(
            fw_message.nrf52_fw_type_id, f"Unknown: {fw_message.nrf52_fw_type_id}"
        ).is_manufacturing
        fw_message.nrf52_fw_target_board = constants.device_type_map.get(
            fw_message.nrf52_fw_type_id, f"Unknown: {fw_message.nrf52_fw_type_id}"
        ).board_name
        fw_message.nrf52_fw_target_board_version = constants.device_type_map.get(
            fw_message.nrf52_fw_type_id, f"Unknown: {fw_message.nrf52_fw_type_id}"
        ).board_revision
        fw_message.nrf52_fw_target_microcontroller = constants.device_type_map.get(
            fw_message.nrf52_fw_type_id, f"Unknown: {fw_message.nrf52_fw_type_id}"
        ).target_microcontroller
        fw_message.nrf52_fw_product_variant = constants.device_type_map.get(
            fw_message.nrf52_fw_type_id, f"Unknown: {fw_message.nrf52_fw_type_id}"
        ).product_name

        return fw_message

    def get_last_jumptrack_firmware_v2_message(self, dut_id: int) -> JumpTrackFirmwareMessage | None:
        log = Logger.get_test_case_logger()
        log.debug("Getting the last Firmware Version message.")

        # Return object
        fw_message: JumpTrackFirmwareMessage = None

        # Get the last Firmware Version message
        if self.use_db_over_api:
            log.warning(f"USING DIRECT DATABASE ACCESS!")

            raw_fw_message: JumpTrackFirmwareV2MessageTbl = None
            db = self.Session()
            raw_fw_message = (
                db.query(JumpTrackFirmwareV2MessageTbl)
                .filter_by(DeviceId=dut_id)
                .order_by(JumpTrackFirmwareV2MessageTbl.CheckinId.desc())
                .first()
            )
            raw_fw_message = deepcopy(raw_fw_message)
            db.close()

            if not raw_fw_message:
                return None

            fw_message = self._repackage_jumptrack_firmware_v2_message(raw_fw_message)
        else:
            raise NotImplementedError("API not implemented for get_last_jumptrack_firmware_v2_message")

        return fw_message

    def get_jumptrack_firmware_v2_messages_since_time(
        self, dut_id: int, start_time: datetime, end_time: datetime = None
    ) -> List[JumpTrackFirmwareMessage] | None:
        log = Logger.get_test_case_logger()
        log.debug("Getting Firmware Version messages since a specific time.")

        # Return object
        fw_messages: List[JumpTrackFirmwareMessage] = []

        # Get the Firmware Version messages
        if self.use_db_over_api:
            log.warning(f"USING DIRECT DATABASE ACCESS!")

            raw_fw_messages: List[JumpTrackFirmwareV2MessageTbl] = []
            db = self.Session()
            raw_fw_messages = (
                db.query(JumpTrackFirmwareV2MessageTbl)
                .filter(
                    JumpTrackFirmwareV2MessageTbl.DeviceId == dut_id,
                    JumpTrackFirmwareV2MessageTbl.TimeReceived > start_time,
                )
                .order_by(JumpTrackFirmwareV2MessageTbl.CheckinId.desc())
            )

            if end_time is not None:
                raw_fw_messages = raw_fw_messages.filter(JumpTrackFirmwareV2MessageTbl.TimeReceived < end_time)

            raw_fw_messages = raw_fw_messages.all()
            raw_fw_messages = deepcopy(raw_fw_messages)
            db.close()

            if not raw_fw_messages:
                return None

            # Repackage the Firmware Version messages
            for raw_fw_message in raw_fw_messages:
                if raw_fw_message is None:
                    continue
                fw_message: JumpTrackFirmwareMessage = self._repackage_jumptrack_firmware_v2_message(raw_fw_message)
                fw_messages.append(fw_message)
        else:
            raise NotImplementedError("API not implemented for get_jumptrack_firmware_v2_messages_since_time")

        return fw_messages

    def get_jumptrack_firmware_v2_messages_since_checkin_id(
        self, dut_id: int, checkin_id: int
    ) -> List[JumpTrackFirmwareMessage] | None:
        log = Logger.get_test_case_logger()
        log.debug("Getting Firmware Version messages since a specific CheckinId.")

        # Return object
        fw_messages: List[JumpTrackFirmwareMessage] = []

        # Get the Firmware Version messages
        if self.use_db_over_api:
            log.warning(f"USING DIRECT DATABASE ACCESS!")

            raw_fw_messages: List[JumpTrackFirmwareV2MessageTbl] = []
            db = self.Session()
            raw_fw_messages = (
                db.query(JumpTrackFirmwareV2MessageTbl)
                .filter(
                    JumpTrackFirmwareV2MessageTbl.DeviceId == dut_id,
                    JumpTrackFirmwareV2MessageTbl.CheckinId > checkin_id,
                )
                .order_by(JumpTrackFirmwareV2MessageTbl.CheckinId.desc())
                .all()
            )
            raw_fw_messages = deepcopy(raw_fw_messages)
            db.close()

            if not raw_fw_messages:
                return None

            # Repackage the Firmware Version messages
            for raw_fw_message in raw_fw_messages:
                if raw_fw_message is None:
                    continue

                fw_message: JumpTrackFirmwareMessage = self._repackage_jumptrack_firmware_v2_message(raw_fw_message)
                fw_messages.append(fw_message)
        else:
            raise NotImplementedError("API not implemented for get_jumptrack_firmware_v2_messages_since_checkin_id")

        return fw_messages

    # -----------------------------------------------------------------------------------------------------------------
    #                                                                                    Hardware Failure Message Table
    # -----------------------------------------------------------------------------------------------------------------
    def _repackage_jumptrack_hardware_failure_message(
        self, raw_hw_failure_message: JumpTrackHardwareFailureV2MsgTbl
    ) -> JumpTrackHardwareFailureMessage:
        log = Logger.get_test_case_logger()
        log.debug("Repackaging the Hardware Failure message.")

        # Return object
        hw_failure_message = JumpTrackHardwareFailureMessage()

        # 1:1 mappings
        hw_failure_message.checkin_id = raw_hw_failure_message.CheckinId
        hw_failure_message.device_id = raw_hw_failure_message.DeviceId
        hw_failure_message.time_received = raw_hw_failure_message.TimeReceived
        hw_failure_message.from_device = raw_hw_failure_message.FromDevice
        hw_failure_message.nonce_received = raw_hw_failure_message.NonceReceived
        hw_failure_message.failure_time = raw_hw_failure_message.FailureTime
        hw_failure_message.acc_failures = raw_hw_failure_message.AccFailures
        hw_failure_message.is_acc_com_failure = raw_hw_failure_message.IsAccComFailure
        hw_failure_message.alt_failures = raw_hw_failure_message.AltFailures
        hw_failure_message.is_alt_com_failure = raw_hw_failure_message.IsAltComFailure
        hw_failure_message.is_alt_int_failure = raw_hw_failure_message.IsAltIntFailure
        hw_failure_message.gps_failures = raw_hw_failure_message.GpsFailures
        hw_failure_message.is_gps_com_failure = raw_hw_failure_message.IsGpsComFailure
        hw_failure_message.is_gps_crystal_failure = raw_hw_failure_message.IsGpsCrystalFailure
        hw_failure_message.lora_failures = raw_hw_failure_message.Sx1262Failures
        hw_failure_message.is_lora_com_failure = raw_hw_failure_message.IsSx1262ComFailure
        hw_failure_message.is_lora_pll_failure = raw_hw_failure_message.IsSx1262PllFailure
        hw_failure_message.ipc_failures = raw_hw_failure_message.IpcFailures
        hw_failure_message.is_ipc_com_failure = raw_hw_failure_message.IsIpcComFailure
        hw_failure_message.bms_failures = raw_hw_failure_message.BmsFailures
        hw_failure_message.is_bms_com_failure = raw_hw_failure_message.IsBmsComFailure
        hw_failure_message.ext_flash_failure = raw_hw_failure_message.ExtFlashFailure
        hw_failure_message.is_ext_flash_com_failure = raw_hw_failure_message.IsExtFlashComFailure
        hw_failure_message.sec_element_failure = raw_hw_failure_message.SecElementFailure
        hw_failure_message.is_sec_element_com_failure = raw_hw_failure_message.IsSecElementComFailure

        # Decode the hardware failures
        constants = JumpTrackHardwareFailureV2MessageConstants()
        hw_failure_message.is_gps_pvt_failure = get_bits(
            hw_failure_message.gps_failures, constants.gps_pvt_failure_bits[0], constants.gps_pvt_failure_bits[1]
        )
        hw_failure_message.is_gps_v_back_failure = get_bits(
            hw_failure_message.gps_failures, constants.gps_v_back_failure_bits[0], constants.gps_v_back_failure_bits[1]
        )

        # Get reserved bits
        hw_failure_message.acc_failures_reserved = get_bits(
            hw_failure_message.acc_failures,
            constants.accelerometer_reserved_bits[0],
            constants.accelerometer_reserved_bits[1],
        )
        hw_failure_message.alt_failures_reserved = get_bits(
            hw_failure_message.alt_failures, constants.altimeter_reserved_bits[0], constants.altimeter_reserved_bits[1]
        )
        hw_failure_message.gps_failures_reserved = get_bits(
            hw_failure_message.gps_failures, constants.gps_reserved_bits[0], constants.gps_reserved_bits[1]
        )
        hw_failure_message.lora_failures_reserved = get_bits(
            hw_failure_message.lora_failures, constants.lora_reserved_bits[0], constants.lora_reserved_bits[1]
        )
        hw_failure_message.ipc_failures_reserved = get_bits(
            hw_failure_message.ipc_failures, constants.ipc_reserved_bits[0], constants.ipc_reserved_bits[1]
        )
        hw_failure_message.bms_failures_reserved = get_bits(
            hw_failure_message.bms_failures, constants.bms_reserved_bits[0], constants.bms_reserved_bits[1]
        )
        hw_failure_message.ext_flash_failures_reserved = get_bits(
            hw_failure_message.ext_flash_failure,
            constants.external_flash_reserved_bits[0],
            constants.external_flash_reserved_bits[1],
        )
        hw_failure_message.sec_element_failures_reserved = get_bits(
            hw_failure_message.sec_element_failure,
            constants.secure_element_reserved_bits[0],
            constants.secure_element_reserved_bits[1],
        )

        return hw_failure_message

    def get_last_jumptrack_hardware_failure_message(self, dut_id: int) -> JumpTrackHardwareFailureMessage | None:
        log = Logger.get_test_case_logger()
        log.debug("Getting the last Hardware Failure message.")

        # Return object
        hw_failure_message: JumpTrackHardwareFailureMessage = None

        # Get the last Hardware Failure message
        if self.use_db_over_api:
            log.warning(f"USING DIRECT DATABASE ACCESS!")

            raw_hw_failure_message: JumpTrackHardwareFailureV2MsgTbl = None
            db = self.Session()
            raw_hw_failure_message = (
                db.query(JumpTrackHardwareFailureV2MsgTbl)
                .filter_by(DeviceId=dut_id)
                .order_by(JumpTrackHardwareFailureV2MsgTbl.CheckinId.desc())
                .first()
            )
            raw_hw_failure_message = deepcopy(raw_hw_failure_message)
            db.close()

            if not raw_hw_failure_message:
                return None

            hw_failure_message = self._repackage_jumptrack_hardware_failure_message(raw_hw_failure_message)
        else:
            raise NotImplementedError("API not implemented for get_last_jumptrack_hardware_failure_message")

        return hw_failure_message

    def get_jumptrack_hardware_failure_messages_since_time(
        self, dut_id: int, start_time: datetime, end_time: datetime = None
    ) -> List[JumpTrackHardwareFailureMessage] | None:
        log = Logger.get_test_case_logger()
        log.debug("Getting Hardware Failure messages since a specific time.")

        # Return object
        hw_failure_messages: List[JumpTrackHardwareFailureMessage] = []

        # Get the Hardware Failure messages
        if self.use_db_over_api:
            log.warning(f"USING DIRECT DATABASE ACCESS!")

            raw_hw_failure_messages: List[JumpTrackHardwareFailureV2MsgTbl] = []
            db = self.Session()
            raw_hw_failure_messages = (
                db.query(JumpTrackHardwareFailureV2MsgTbl)
                .filter(
                    JumpTrackHardwareFailureV2MsgTbl.DeviceId == dut_id,
                    JumpTrackHardwareFailureV2MsgTbl.TimeReceived > start_time,
                )
                .order_by(JumpTrackHardwareFailureV2MsgTbl.CheckinId.desc())
            )

            if end_time is not None:
                raw_hw_failure_messages = raw_hw_failure_messages.filter(
                    JumpTrackHardwareFailureV2MsgTbl.TimeReceived < end_time
                )

            raw_hw_failure_messages = raw_hw_failure_messages.all()
            raw_hw_failure_messages = deepcopy(raw_hw_failure_messages)
            db.close()

            if not raw_hw_failure_messages:
                return None

            # Repackage the Hardware Failure messages
            for raw_hw_failure_message in raw_hw_failure_messages:
                if raw_hw_failure_message is None:
                    continue
                hw_failure_message: JumpTrackHardwareFailureMessage = (
                    self._repackage_jumptrack_hardware_failure_message(raw_hw_failure_message)
                )
                hw_failure_messages.append(hw_failure_message)
        else:
            raise NotImplementedError("API not implemented for get_jumptrack_hardware_failure_messages_since_time")

        return hw_failure_messages

    def get_jumptrack_hardware_failure_messages_since_checkin_id(
        self, dut_id: int, checkin_id: int
    ) -> List[JumpTrackHardwareFailureMessage] | None:
        log = Logger.get_test_case_logger()
        log.debug("Getting Hardware Failure messages since a specific CheckinId.")

        # Return object
        hw_failure_messages: List[JumpTrackHardwareFailureMessage] = []

        # Get the Hardware Failure messages
        if self.use_db_over_api:
            log.warning(f"USING DIRECT DATABASE ACCESS!")

            raw_hw_failure_messages: List[JumpTrackHardwareFailureV2MsgTbl] = []
            db = self.Session()
            raw_hw_failure_messages = (
                db.query(JumpTrackHardwareFailureV2MsgTbl)
                .filter(
                    JumpTrackHardwareFailureV2MsgTbl.DeviceId == dut_id,
                    JumpTrackHardwareFailureV2MsgTbl.CheckinId > checkin_id,
                )
                .order_by(JumpTrackHardwareFailureV2MsgTbl.CheckinId.desc())
                .all()
            )
            raw_hw_failure_messages = deepcopy(raw_hw_failure_messages)
            db.close()

            if not raw_hw_failure_messages:
                return None

            # Repackage the Hardware Failure messages
            for raw_hw_failure_message in raw_hw_failure_messages:
                if raw_hw_failure_message is None:
                    continue

                hw_failure_message: JumpTrackHardwareFailureMessage = (
                    self._repackage_jumptrack_hardware_failure_message(raw_hw_failure_message)
                )
                hw_failure_messages.append(hw_failure_message)
        else:
            raise NotImplementedError(
                "API not implemented for get_jumptrack_hardware_failure_messages_since_checkin_id"
            )

        return hw_failure_messages

    # -----------------------------------------------------------------------------------------------------------------
    #                                                                                            HIPS Sensor Data Table
    # -----------------------------------------------------------------------------------------------------------------'
    def _repackage_jumptrack_hips_sensor_message(
        self, raw_hips_sensor_message: JumpTrackHipsSensorDataMsgTbl
    ) -> JumpTrackHipsSensorMessage:
        log = Logger.get_test_case_logger()
        log.debug("Repackaging the HIPS Sensor Data message.")

        # Return object
        hips_sensor_message = JumpTrackHipsSensorMessage()

        # 1:1 mappings
        hips_sensor_message.checkin_id = raw_hips_sensor_message.CheckinId
        hips_sensor_message.device_id = raw_hips_sensor_message.DeviceId
        hips_sensor_message.time_received = raw_hips_sensor_message.TimeReceived
        hips_sensor_message.from_device = raw_hips_sensor_message.FromDevice
        hips_sensor_message.nonce_received = raw_hips_sensor_message.NonceReceived
        hips_sensor_message.time_of_measurement = raw_hips_sensor_message.TimeOfMeasurement
        hips_sensor_message.group_code = raw_hips_sensor_message.GroupCode
        hips_sensor_message.source_user_id = raw_hips_sensor_message.SourceUserId
        hips_sensor_message.hsi_data_value = raw_hips_sensor_message.HsiDataValue
        hips_sensor_message.hr_data_value = raw_hips_sensor_message.HrDataValue
        hips_sensor_message.estimated_core_temp = raw_hips_sensor_message.EstimatedCoreTemp
        hips_sensor_message.skin_temp = raw_hips_sensor_message.SkinTemp
        hips_sensor_message.nii = raw_hips_sensor_message.NII
        hips_sensor_message.risk = raw_hips_sensor_message.Risk
        hips_sensor_message.confidence = raw_hips_sensor_message.Confidence
        hips_sensor_message.hips_battery_life = raw_hips_sensor_message.HipsBatteryLife

        return hips_sensor_message

    def get_last_jumptrack_hips_sensor_message(self, dut_id: int) -> JumpTrackHipsSensorMessage | None:
        log = Logger.get_test_case_logger()
        log.debug("Getting the last HIPS Sensor Data message.")

        # Return object
        hips_sensor_message: JumpTrackHipsSensorMessage = None

        # Get the last HIPS Sensor Data message
        if self.use_db_over_api:
            log.warning(f"USING DIRECT DATABASE ACCESS!")

            raw_hips_sensor_message: JumpTrackHipsSensorDataMsgTbl = None
            db = self.Session()
            raw_hips_sensor_message = (
                db.query(JumpTrackHipsSensorDataMsgTbl)
                .filter_by(DeviceId=dut_id)
                .order_by(JumpTrackHipsSensorDataMsgTbl.CheckinId.desc())
                .first()
            )
            raw_hips_sensor_message = deepcopy(raw_hips_sensor_message)
            db.close()

            if not raw_hips_sensor_message:
                return None

            hips_sensor_message = self._repackage_jumptrack_hips_sensor_message(raw_hips_sensor_message)
        else:
            raise NotImplementedError("API not implemented for get_last_jumptrack_hips_sensor_message")

        return hips_sensor_message

    def get_jumptrack_hips_sensor_messages_since_time(
        self, dut_id: int, start_time: datetime, end_time: datetime = None
    ) -> List[JumpTrackHipsSensorMessage] | None:
        log = Logger.get_test_case_logger()
        log.debug("Getting HIPS Sensor Data messages since a specific time.")

        # Return object
        hips_sensor_messages: List[JumpTrackHipsSensorMessage] = []

        # Get the HIPS Sensor Data messages
        if self.use_db_over_api:
            log.warning(f"USING DIRECT DATABASE ACCESS!")

            raw_hips_sensor_messages: List[JumpTrackHipsSensorDataMsgTbl] = []
            db = self.Session()
            raw_hips_sensor_messages = (
                db.query(JumpTrackHipsSensorDataMsgTbl)
                .filter(
                    JumpTrackHipsSensorDataMsgTbl.DeviceId == dut_id,
                    JumpTrackHipsSensorDataMsgTbl.TimeReceived > start_time,
                )
                .order_by(JumpTrackHipsSensorDataMsgTbl.CheckinId.desc())
            )

            if end_time is not None:
                raw_hips_sensor_messages = raw_hips_sensor_messages.filter(
                    JumpTrackHipsSensorDataMsgTbl.TimeReceived < end_time
                )

            raw_hips_sensor_messages = raw_hips_sensor_messages.all()
            raw_hips_sensor_messages = deepcopy(raw_hips_sensor_messages)
            db.close()

            if not raw_hips_sensor_messages:
                return None

            # Repackage the HIPS Sensor Data messages
            for raw_hips_sensor_message in raw_hips_sensor_messages:
                if raw_hips_sensor_message is None:
                    continue
                hips_sensor_message: JumpTrackHipsSensorMessage = self._repackage_jumptrack_hips_sensor_message(
                    raw_hips_sensor_message
                )
                hips_sensor_messages.append(hips_sensor_message)
        else:
            raise NotImplementedError("API not implemented for get_jumptrack_hips_sensor_messages_since_time")

        return hips_sensor_messages

    def get_jumptrack_hips_sensor_messages_since_checkin_id(
        self, dut_id: int, checkin_id: int
    ) -> List[JumpTrackHipsSensorMessage] | None:
        log = Logger.get_test_case_logger()
        log.debug("Getting HIPS Sensor Data messages since a specific CheckinId.")

        # Return object
        hips_sensor_messages: List[JumpTrackHipsSensorMessage] = []

        # Get the HIPS Sensor Data messages
        if self.use_db_over_api:
            log.warning(f"USING DIRECT DATABASE ACCESS!")

            raw_hips_sensor_messages: List[JumpTrackHipsSensorDataMsgTbl] = []
            db = self.Session()
            raw_hips_sensor_messages = (
                db.query(JumpTrackHipsSensorDataMsgTbl)
                .filter(
                    JumpTrackHipsSensorDataMsgTbl.DeviceId == dut_id,
                    JumpTrackHipsSensorDataMsgTbl.CheckinId > checkin_id,
                )
                .order_by(JumpTrackHipsSensorDataMsgTbl.CheckinId.desc())
                .all()
            )
            raw_hips_sensor_messages = deepcopy(raw_hips_sensor_messages)
            db.close()

            if not raw_hips_sensor_messages:
                return None

            # Repackage the HIPS Sensor Data messages
            for raw_hips_sensor_message in raw_hips_sensor_messages:
                if raw_hips_sensor_message is None:
                    continue

                hips_sensor_message: JumpTrackHipsSensorMessage = self._repackage_jumptrack_hips_sensor_message(
                    raw_hips_sensor_message
                )
                hips_sensor_messages.append(hips_sensor_message)
        else:
            raise NotImplementedError("API not implemented for get_jumptrack_hips_sensor_messages_since_checkin_id")

        return hips_sensor_messages

    # -----------------------------------------------------------------------------------------------------------------
    #                                                                                      Network Status Message Table
    # -----------------------------------------------------------------------------------------------------------------

    def _repackage_network_status_message(
        self, raw_net_status_message: NetSocketNetworkStatusMessageTbl
    ) -> NetworkStatusMessage:
        log = Logger.get_test_case_logger()
        log.debug("Repackaging the Network Status message.")

        # Return object
        net_status_message = NetworkStatusMessage()

        # 1:1 mappings
        net_status_message.checkin_id = raw_net_status_message.CheckinId
        net_status_message.device_id = raw_net_status_message.DeviceId
        net_status_message.time_received = raw_net_status_message.TimeReceived
        net_status_message.from_device = raw_net_status_message.FromDevice
        net_status_message.nonce_received = raw_net_status_message.NonceReceived
        net_status_message.flags = raw_net_status_message.Flags
        net_status_message.lte_connected = raw_net_status_message.LteConnected
        net_status_message.socket_connected = raw_net_status_message.SocketConnected
        net_status_message.send_success = raw_net_status_message.SendSuccess
        net_status_message.wireless_technology = raw_net_status_message.WirelessTechnology
        net_status_message.active_sim_slot = raw_net_status_message.ActiveSimSlot
        net_status_message.early_socket_disconnect = raw_net_status_message.EarlySocketDisconnect
        net_status_message.dnssec_resolved = raw_net_status_message.DnssecResolved
        net_status_message.time_spent = raw_net_status_message.TimeSpent
        net_status_message.time_of_connection = raw_net_status_message.TimeOfConnection
        net_status_message.rsrq = raw_net_status_message.RSRQ
        net_status_message.rsrp = raw_net_status_message.RSRP
        net_status_message.number_of_bytes_sent = raw_net_status_message.NumberOfBytesSent
        net_status_message.number_of_bytes_received = raw_net_status_message.NumberOfBytesReceived
        net_status_message.band = raw_net_status_message.Band
        net_status_message.energy_estimate = raw_net_status_message.EnergyEstimate
        net_status_message.network_id = raw_net_status_message.NetworkId

        constants = NetworkStatusV4MessageConstants()
        wireless_technology_str = constants.wireless_technology_map.get(
            net_status_message.wireless_technology, f"Unknown: {net_status_message.wireless_technology}"
        )

        return net_status_message

    def get_last_network_status_message(self, dut_id: int) -> NetworkStatusMessage | None:
        log = Logger.get_test_case_logger()
        log.debug("Getting the last Network Status message.")

        # Return object
        net_status_message: NetworkStatusMessage = None

        # Get the last Network Status message
        if self.use_db_over_api:
            log.warning(f"USING DIRECT DATABASE ACCESS!")

            raw_net_status_message: NetSocketNetworkStatusMessageTbl = None
            db = self.Session()
            raw_net_status_message = (
                db.query(NetSocketNetworkStatusMessageTbl)
                .filter_by(DeviceId=dut_id)
                .order_by(NetSocketNetworkStatusMessageTbl.CheckinId.desc())
                .first()
            )
            raw_net_status_message = deepcopy(raw_net_status_message)
            db.close()

            if not raw_net_status_message:
                return None

            net_status_message = self._repackage_network_status_message(raw_net_status_message)
        else:
            raise NotImplementedError("API not implemented for get_last_net_socket_network_status_message")

        return net_status_message

    def get_network_status_messages_since_time(
        self, dut_id: int, start_time: datetime, end_time: datetime = None
    ) -> List[NetworkStatusMessage] | None:
        log = Logger.get_test_case_logger()
        log.debug("Getting Network Status messages since a specific time.")

        # Return object
        net_status_messages: List[NetworkStatusMessage] = []

        # Get the Network Status messages
        if self.use_db_over_api:
            log.warning(f"USING DIRECT DATABASE ACCESS!")

            raw_net_status_messages: List[NetSocketNetworkStatusMessageTbl] = []
            db = self.Session()
            raw_net_status_messages = (
                db.query(NetSocketNetworkStatusMessageTbl)
                .filter(
                    NetSocketNetworkStatusMessageTbl.DeviceId == dut_id,
                    NetSocketNetworkStatusMessageTbl.TimeReceived > start_time,
                )
                .order_by(NetSocketNetworkStatusMessageTbl.CheckinId.desc())
            )

            if end_time is not None:
                raw_net_status_messages = raw_net_status_messages.filter(
                    NetSocketNetworkStatusMessageTbl.TimeReceived < end_time
                )

            raw_net_status_messages = raw_net_status_messages.all()
            raw_net_status_messages = deepcopy(raw_net_status_messages)
            db.close()

            if not raw_net_status_messages:
                return None

            # Repackage the Network Status messages
            for raw_net_status_message in raw_net_status_messages:
                if raw_net_status_message is None:
                    continue
                net_status_message: NetworkStatusMessage = self._repackage_network_status_message(
                    raw_net_status_message
                )
                net_status_messages.append(net_status_message)
        else:
            raise NotImplementedError("API not implemented for get_net_socket_network_status_messages_since_time")

        return net_status_messages

    def get_network_status_messages_since_checkin_id(
        self, dut_id: int, checkin_id: int
    ) -> List[NetworkStatusMessage] | None:
        log = Logger.get_test_case_logger()
        log.debug("Getting Network Status messages since a specific CheckinId.")

        # Return object
        net_status_messages: List[NetworkStatusMessage] = []

        # Get the Network Status messages
        if self.use_db_over_api:
            log.warning(f"USING DIRECT DATABASE ACCESS!")

            raw_net_status_messages: List[NetSocketNetworkStatusMessageTbl] = []
            db = self.Session()
            raw_net_status_messages = (
                db.query(NetSocketNetworkStatusMessageTbl)
                .filter(
                    NetSocketNetworkStatusMessageTbl.DeviceId == dut_id,
                    NetSocketNetworkStatusMessageTbl.CheckinId > checkin_id,
                )
                .order_by(NetSocketNetworkStatusMessageTbl.CheckinId.desc())
                .all()
            )
            raw_net_status_messages = deepcopy(raw_net_status_messages)
            db.close()

            if not raw_net_status_messages:
                return None

            # Repackage the Network Status messages
            for raw_net_status_message in raw_net_status_messages:
                if raw_net_status_message is None:
                    continue

                net_status_message: NetworkStatusMessage = self._repackage_network_status_message(
                    raw_net_status_message
                )
                net_status_messages.append(net_status_message)
        else:
            raise NotImplementedError(
                "API not implemented for get_net_socket_network_status_messages_since_checkin_id"
            )

        return net_status_messages
