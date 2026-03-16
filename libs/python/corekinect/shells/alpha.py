"""Legacy Alpha + Comms coprocessor shell commands.

For new code, prefer AlphaAppShell and CommsCoprocShell which use
persistent UART streams and better error handling.

Usage:
    from corekinect.shells.alpha import AlphaShell

    shell = AlphaShell(mtib_client)
    hex_key, b64_key, err = shell.alpha_cmd_personalize("DEVICE_ID")
    imei, iccids, err = shell.alpha_cmd_get_imei_iccids()
"""

import base64
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from protocols.mtib.mtib_pb2 import HostType

from corekinect.shells._uart_cmd import send_uart_cmd


# ── Result types ─────────────────────────────────────────

@dataclass
class BmsTestResult:
    """Result from test_bms command."""
    connected: bool
    chip_id: Optional[str] = None
    charge_percent: Optional[int] = None
    capacity_mah: Optional[int] = None
    temperature_c: Optional[int] = None


@dataclass
class ChargerTestResult:
    """Result from test_charger command."""
    chip_id: Optional[str] = None
    chip_id_error: Optional[int] = None
    on_charger: bool = False
    charging: bool = False
    charge_done: bool = False
    battery_voltage_mv: Optional[int] = None


@dataclass
class GpsTestResult:
    """Result from test_gps command."""
    in_shutdown: bool = True
    tracking: bool = False
    comms_ok: bool = False


@dataclass
class ExtFlashTestResult:
    """Result from external flash read/write test."""
    write_ok: bool = False
    read_ok: bool = False
    data_match: bool = False


# ── Shell interface ──────────────────────────────────────

class AlphaShell:
    """Legacy Alpha + Comms coprocessor shell commands.

    For new code, prefer AlphaAppShell and CommsCoprocShell which use
    persistent UART streams and better error handling.
    """

    def __init__(self, client):
        self._client = client
        self.logger = client.logger

    # ── Alpha App Processor Commands ─────────────────

    def alpha_cmd_personalize(
        self, device_id: str, target: HostType = HostType.HOST_TYPE_NRF9151
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Send a UART command to personalize the device using the given device_id.

        Uses the standard UART helper to send the personalize command and parse
        the response to extract the public key data.

        Args:
            device_id: Device ID to use for personalization
            target: Target host type (default: NRF9151 comms processor)

        Returns:
            Tuple[Optional[str], Optional[str], Optional[str]]: A tuple containing:
                - hex_public_key (Optional[str]): Public key in hexadecimal format, None on error
                - base64_public_key (Optional[str]): Public key in base64 format, None on error
                - error (Optional[str]): Error message string if operation failed, None on success
        """
        response, err = send_uart_cmd(
            self._client,
            target=target,
            command=f"personalize {device_id}",
            success_patterns=["Public key (base64)"],
            timeout_s=60,  # Key generation takes ~5s, plus byte-by-byte UART delivery is SLOW
        )
        if err:
            return None, None, err

        # Strip ANSI escape codes before parsing
        full_response = re.sub(r"\x1b\[[0-9;]*m", "", response or "")

        hex_match = re.search(r"Public key \(hex\)\s*:\s*([0-9a-fA-F]{100,})", full_response)
        b64_match = re.search(r"Public key \(base64\)\s*:\s*([A-Za-z0-9+/=]{40,})", full_response)

        if hex_match and b64_match:
            return hex_match.group(1), b64_match.group(1), None
        else:
            return None, None, f"Failed to parse public keys from response: {full_response[:300]}"

    def alpha_cmd_get_imei_iccids(
        self, target: HostType = HostType.HOST_TYPE_NRF9151
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Send a UART command to get the device IMEI and ICCIDs.

        Uses the standard UART helper to send the imei_iccid command and parse
        the response to extract the IMEI and ICCIDs.

        Args:
            target: Target host type (default: NRF9151 comms processor)

        Returns:
            Tuple[Optional[str], Optional[str], Optional[str]]: A tuple containing:
                - imei (Optional[str]): IMEI number, None on error
                - iccids (Optional[str]): Comma-separated ICCID numbers, None on error
                - error (Optional[str]): Error message string if operation failed, None on success
        """
        response, err = send_uart_cmd(
            self._client,
            target=target,
            command="imei_iccid",
            success_patterns=["IMEI"],
            timeout_s=30,
        )
        if err:
            return None, None, err

        # Parse the response for IMEI and ICCIDs
        imei = None
        iccids = None
        full_response = response or ""

        # Look for IMEI,ICCID line (handle both direct response and modem log response)
        imei_start = full_response.find("IMEI,ICCID")
        if imei_start != -1:
            colon_pos = full_response.find(":", imei_start)
            if colon_pos != -1:
                data_start = colon_pos + 1
                data_end = full_response.find("\n", data_start)
                if data_end == -1:
                    data_end = len(full_response)
                data_line = full_response[data_start:data_end].strip()
                if data_line and "," in data_line:
                    parts = data_line.split(",")
                    if len(parts) >= 2:
                        imei = parts[0].strip()
                        iccids = ",".join(parts[1:]).strip()
                    else:
                        imei = "unknown"
                        iccids = parts[0].strip()

        if imei and iccids:
            return imei, iccids, None
        else:
            return None, None, f"Failed to parse IMEI/ICCIDs from response: {full_response[:300]}"

    def alpha_cmd_get_chip_ids_app(
        self, target: HostType = HostType.HOST_TYPE_NRF52840
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Get chip IDs from the Alpha app processor (NRF52840).

        Returns:
            Tuple of (ext_flash_id, ble_mac, error).
            ext_flash_id: External flash JEDEC ID (e.g., "0xc2 0x28 0x17")
            ble_mac: BLE MAC address string
        """
        response, err = send_uart_cmd(
            self._client,
            target=target,
            command="get_chip_ids",
            success_patterns=["BLE MAC:"],
            timeout_s=15,
        )
        if err:
            return None, None, err

        ext_flash_id = None
        ble_mac = None

        # Parse ext flash ID
        if "Ext flash chip ID:" in response:
            match = re.search(r"Ext flash chip ID:\s*(.+)", response)
            if match:
                ext_flash_id = match.group(1).strip()

        # Parse BLE MAC
        if "BLE MAC:" in response:
            match = re.search(r"BLE MAC:\s*(\S+)", response)
            if match:
                ble_mac = match.group(1).strip()

        if ext_flash_id or ble_mac:
            return ext_flash_id, ble_mac, None
        return None, None, f"Failed to parse chip IDs from: {response[:200]}"

    def alpha_cmd_get_chip_ids_comms(
        self, target: HostType = HostType.HOST_TYPE_NRF9151
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Get chip IDs from the Alpha comms processor (NRF9151).

        Returns:
            Tuple of (ext_flash_id, lora_available, error).
            ext_flash_id: External flash JEDEC ID (e.g., "0xef 0x40 0x17")
            lora_available: LoRa hardware availability string
        """
        response, err = send_uart_cmd(
            self._client,
            target=target,
            command="get_chip_ids",
            success_patterns=["Ext flash chip ID:"],
            timeout_s=15,
        )
        if err:
            return None, None, err

        ext_flash_id = None
        lora_available = None

        # Parse ext flash ID
        if "Ext flash chip ID:" in response:
            match = re.search(r"Ext flash chip ID:\s*(.+)", response)
            if match:
                ext_flash_id = match.group(1).strip()

        # Parse LoRa availability
        if "LoRa hardware available:" in response:
            match = re.search(r"LoRa hardware available:\s*(\w+)", response)
            if match:
                lora_available = match.group(1).strip()

        if ext_flash_id:
            return ext_flash_id, lora_available, None
        return None, None, f"Failed to parse chip IDs from: {response[:200]}"

    def alpha_cmd_test_bms(
        self, target: HostType = HostType.HOST_TYPE_NRF52840
    ) -> Tuple[Optional[BmsTestResult], Optional[str]]:
        """Test BMS (gas gauge) chip on the Alpha app processor.

        Returns:
            Tuple of (BmsTestResult, error).
        """
        response, err = send_uart_cmd(
            self._client,
            target=target,
            command="test_bms",
            success_patterns=["BMS connected:", "Temperature:"],
            timeout_s=15,
        )
        if err:
            return None, err

        result = BmsTestResult(connected=False)

        # Parse BMS connected
        if "BMS connected: yes" in response:
            result.connected = True
        elif "BMS connected: no" in response:
            result.connected = False

        # Parse chip ID
        match = re.search(r"BMS chip ID:\s*(0x[0-9a-fA-F]+)", response)
        if match:
            result.chip_id = match.group(1)

        # Parse charge percent
        match = re.search(r"Charge:\s*(\d+)%", response)
        if match:
            result.charge_percent = int(match.group(1))

        # Parse capacity
        match = re.search(r"Capacity:\s*(\d+)\s*mAh", response)
        if match:
            result.capacity_mah = int(match.group(1))

        # Parse temperature
        match = re.search(r"Temperature:\s*(-?\d+)\s*C", response)
        if match:
            result.temperature_c = int(match.group(1))

        return result, None

    def alpha_cmd_test_charger(
        self, target: HostType = HostType.HOST_TYPE_NRF52840
    ) -> Tuple[Optional[ChargerTestResult], Optional[str]]:
        """Test battery charger chip on the Alpha app processor.

        Returns:
            Tuple of (ChargerTestResult, error).
        """
        response, err = send_uart_cmd(
            self._client,
            target=target,
            command="test_charger",
            success_patterns=["Battery voltage:"],
            timeout_s=15,
        )
        if err:
            return None, err

        result = ChargerTestResult()

        # Parse chip ID
        match = re.search(r"Charger chip ID:\s*(0x[0-9a-fA-F]+)\s*\(err:\s*(-?\d+)\)", response)
        if match:
            result.chip_id = match.group(1)
            result.chip_id_error = int(match.group(2))

        # Parse on charger
        result.on_charger = "On charger: yes" in response

        # Parse charging
        result.charging = "Charging: yes" in response

        # Parse charge done
        result.charge_done = "Charge done: yes" in response

        # Parse battery voltage
        match = re.search(r"Battery voltage:\s*(\d+)\s*mV", response)
        if match:
            result.battery_voltage_mv = int(match.group(1))

        return result, None

    def alpha_cmd_test_gps(
        self, target: HostType = HostType.HOST_TYPE_NRF52840
    ) -> Tuple[Optional[GpsTestResult], Optional[str]]:
        """Test GPS (GNSS) module on the Alpha app processor.

        Returns:
            Tuple of (GpsTestResult, error).
        """
        response, err = send_uart_cmd(
            self._client,
            target=target,
            command="test_gps",
            success_patterns=["GPS comms:"],
            timeout_s=15,
        )
        if err:
            return None, err

        result = GpsTestResult()

        # Parse shutdown state
        result.in_shutdown = "GPS shutdown: yes" in response

        # Parse tracking
        result.tracking = "GPS tracking: yes" in response

        # Parse comms status
        result.comms_ok = "GPS comms: OK" in response

        return result, None

    def alpha_cmd_test_ext_flash(
        self, target: HostType = HostType.HOST_TYPE_NRF52840
    ) -> Tuple[Optional[ExtFlashTestResult], Optional[str]]:
        """Test external flash on the specified processor.

        Writes a test pattern to flash, reads it back, and verifies match.
        Works for both app (NRF52840) and comms (NRF9151) processors.

        Returns:
            Tuple of (ExtFlashTestResult, error).
        """
        result = ExtFlashTestResult()

        # Test pattern: "POST_TEST" encoded as base64
        test_data = base64.b64encode(b"POST_TEST").decode("ascii")
        test_addr = "0x100000"  # Safe test address

        # Write test pattern
        response, err = send_uart_cmd(
            self._client,
            target=target,
            command=f"write_ext_flash {test_addr} {test_data}",
            success_patterns=["Writing", "Mfg shell:"],
            timeout_s=15,
        )
        if err:
            return result, err

        if "Writing" in (response or "") or "Mfg shell:" in (response or ""):
            result.write_ok = True
        else:
            return result, f"Write failed: {response[:200]}"

        # Read back 9 bytes ("POST_TEST")
        response, err = send_uart_cmd(
            self._client,
            target=target,
            command=f"read_ext_flash {test_addr} 9",
            success_patterns=["Reading", "Mfg shell:"],
            timeout_s=15,
        )
        if err:
            return result, err

        if "Reading" in (response or "") or response:
            result.read_ok = True
            # Check for expected hex values (POST_TEST = 504F53545F54455354)
            if "504F53545F54455354" in response.upper().replace(" ", ""):
                result.data_match = True
            elif "POST_TEST" in response:
                result.data_match = True

        return result, None

    def alpha_cmd_get_modem_fw(
        self, target: HostType = HostType.HOST_TYPE_NRF9151
    ) -> Tuple[Optional[str], Optional[str]]:
        """Get modem firmware version from the Alpha comms processor.

        Returns:
            Tuple of (modem_fw_version, error).
        """
        response, err = send_uart_cmd(
            self._client,
            target=target,
            command="get_modem_fw",
            success_patterns=["Modem FW:"],
            timeout_s=15,
        )
        if err:
            return None, err

        match = re.search(r"Modem FW:\s*(.+)", response)
        if match:
            return match.group(1).strip(), None
        return None, f"Failed to parse modem FW from: {response[:200]}"

    def alpha_cmd_rekey_ipc(
        self, target: HostType = HostType.HOST_TYPE_NRF9151
    ) -> Tuple[Optional[bool], Optional[str]]:
        """Trigger IPC rekey on the Alpha comms processor.

        Generates a new IPC encryption key and synchronizes it with the app processor.
        Takes ~2 seconds for the IPC handshake.

        Returns:
            Tuple of (success, error).
        """
        response, err = send_uart_cmd(
            self._client,
            target=target,
            command="rekey_ipc",
            success_patterns=["IPC rekey completed successfully", "IPC rekey failed"],
            timeout_s=15,
        )
        if err:
            return None, err

        if "IPC rekey completed successfully" in (response or ""):
            return True, None
        elif "IPC rekey failed" in (response or ""):
            return False, "IPC rekey failed (reported by device)"
        return None, f"Unexpected response: {response[:200]}"

    def alpha_cmd_get_pub_key(
        self, target: HostType = HostType.HOST_TYPE_NRF9151
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Get the device public key from the Alpha comms processor.

        Returns:
            Tuple of (hex_pub_key, base64_pub_key, error).
        """
        response, err = send_uart_cmd(
            self._client,
            target=target,
            command="get_pub_key",
            success_patterns=["Public key (base64):"],
            timeout_s=15,
        )
        if err:
            return None, None, err

        hex_key = None
        b64_key = None

        # Parse hex key
        match = re.search(r"Public key \(hex\)\s*:\s*([0-9a-fA-F]+)", response)
        if match:
            hex_key = match.group(1)

        # Parse base64 key
        match = re.search(r"Public key \(base64\)\s*:\s*([A-Za-z0-9+/=]+)", response)
        if match:
            b64_key = match.group(1)

        if hex_key and b64_key:
            return hex_key, b64_key, None
        return None, None, f"Failed to parse public keys from: {response[:200]}"

    # ── Comms Coprocessor Commands ───────────────────

    def cmd_comms_coproc_get_chip_ids(
        self, target: HostType = HostType.HOST_TYPE_NRF9151
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Get chip IDs from the communications co-processor device.

        Returns the LoRa hardware availability status and external flash chip ID.

        Returns:
            Tuple[Optional[str], Optional[str], Optional[str]]: A tuple containing:
                - lora_available (Optional[str]): LoRa hardware availability status, None if not present
                - ext_flash_id (Optional[str]): External flash chip ID, None on error
                - error (Optional[str]): Error message string if operation failed, None on success
        """
        response, err = send_uart_cmd(
            self._client,
            target=target,
            command="get_chip_ids",
            success_patterns=["Ext flash chip ID:"],
            timeout_s=15,
        )
        if err:
            return None, None, err

        lora_status = None
        ext_flash_id = None
        full_response = response or ""

        # Extract LoRa status (optional)
        match = re.search(r"LoRa hardware available:\s*(\w+)", full_response)
        if match:
            lora_status = match.group(1).strip()

        # Extract Ext flash chip ID
        match = re.search(r"Ext flash chip ID:\s*(.+)", full_response)
        if match:
            ext_flash_id = match.group(1).strip()

        if ext_flash_id:
            return lora_status, ext_flash_id, None
        return None, None, f"Failed to parse chip IDs from: {full_response[:200]}"

    def cmd_comms_coproc_get_modem_fw_version(
        self, target: HostType = HostType.HOST_TYPE_NRF9151
    ) -> Tuple[Optional[str], Optional[str]]:
        """Get modem firmware version from the communications co-processor device.

        Returns:
            Tuple of (fw_version, error_string)
        """
        response, err = send_uart_cmd(
            self._client,
            target=target,
            command="get_modem_fw",
            success_patterns=["Modem FW:"],
            timeout_s=15,
        )
        if err:
            return None, err

        match = re.search(r"Modem FW:\s*(.+)", response or "")
        if match:
            return match.group(1).strip(), None
        return None, f"Failed to parse modem FW from: {(response or '')[:200]}"

    def cmd_comms_coproc_get_imei_iccid(
        self, target: HostType = HostType.HOST_TYPE_NRF9151
    ) -> Tuple[Optional[str], Optional[List[str]], Optional[str]]:
        """Get IMEI and ICCID from the communications co-processor device.

        Returns:
            Tuple of (imei, iccid_list, error_string)
        """
        response, err = send_uart_cmd(
            self._client,
            target=target,
            command="imei_iccid",
            success_patterns=["IMEI,ICCID"],
            timeout_s=15,
        )
        if err:
            return None, None, err

        full_response = response or ""
        imei = None
        iccid_list = []

        # Parse format: "IMEI,ICCID0[,ICCID1]: 358447171854988,89148000009808536124,89457300000035352429"
        match = re.search(r"IMEI,ICCID[01,]*:\s*(.+)", full_response)
        if match:
            parts = [part.strip() for part in match.group(1).split(",")]
            if len(parts) >= 2:
                imei = parts[0]
                iccid_list = parts[1:]

        if imei and iccid_list:
            return imei, iccid_list, None
        return None, None, f"Failed to parse IMEI/ICCIDs from: {full_response[:200]}"

    def cmd_comms_coproc_personalize(
        self, device_id: str, target: HostType = HostType.HOST_TYPE_NRF9151
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Personalize the communications co-processor device.

        Args:
            device_id: The device ID to personalize
        Returns:
            Tuple of (hex_public_key, base64_public_key, error_string)
        """
        response, err = send_uart_cmd(
            self._client,
            target=target,
            command=f"personalize {device_id}",
            success_patterns=["Public key (base64)"],
            timeout_s=15,
        )
        if err:
            return None, None, err

        full_response = re.sub(r"\x1b\[[0-9;]*m", "", response or "")

        hex_match = re.search(r"Public key \(hex\)\s*:\s*([0-9a-fA-F]{100,})", full_response)
        b64_match = re.search(r"Public key \(base64\)\s*:\s*([A-Za-z0-9+/=]{40,})", full_response)

        if hex_match and b64_match:
            return hex_match.group(1), b64_match.group(1), None
        return None, None, f"Failed to parse public keys from: {full_response[:300]}"

    def cmd_comms_coproc_read_ext_flash(
        self, address: str, num_bytes: int, target: HostType = HostType.HOST_TYPE_NRF9151
    ) -> Tuple[Optional[str], Optional[str]]:
        """Read data from external flash.

        Args:
            address: The address to read from
            num_bytes: The number of bytes to read
        Returns:
            Tuple of (hex_data, error_string)
        """
        response, err = send_uart_cmd(
            self._client,
            target=target,
            command=f"read_ext_flash {address} {num_bytes}",
            success_patterns=["Reading", "Mfg shell:", "Comms Mfg:"],
            timeout_s=15,
        )
        if err:
            return None, err

        full_response = response or ""
        # Extract the hex data from hex dump lines (format: "00000000: xx xx xx | ...")
        hex_data = ""
        for line in full_response.split("\n"):
            if ":" in line and "|" in line:
                hex_part = line.split("|")[0].strip()
                if ":" in hex_part:
                    hex_values = hex_part.split(":", 1)[1].strip()
                    hex_data += hex_values.replace(" ", "")

        if hex_data:
            return hex_data, None
        return None, f"Failed to parse hex data from: {full_response[:200]}"

    def cmd_comms_coproc_erase_ext_flash(
        self, target: HostType = HostType.HOST_TYPE_NRF9151
    ) -> Tuple[Optional[bool], Optional[str]]:
        """Erase entire external flash.

        Returns:
            Tuple of (success, error_string)
        """
        response, err = send_uart_cmd(
            self._client,
            target=target,
            command="erase_ext_flash",
            success_patterns=["Erasing flash", "pages"],
            timeout_s=15,  # Erase can take longer
        )
        if err:
            return None, err
        return "Erasing flash" in (response or ""), None

    def cmd_comms_coproc_write_ext_flash(
        self, address: str, flash_data: str, target: HostType = HostType.HOST_TYPE_NRF9151
    ) -> Tuple[Optional[bool], Optional[str]]:
        """Write data to external flash (data should be base64 encoded).

        Args:
            address: The address to write to
            flash_data: The data to write (base64 encoded)
        Returns:
            Tuple of (success, error_string)
        """
        response, err = send_uart_cmd(
            self._client,
            target=target,
            command=f"write_ext_flash {address} {flash_data}",
            success_patterns=["Writing", "bytes to address:"],
            timeout_s=15,
        )
        if err:
            return None, err
        return "Writing" in (response or ""), None

    def cmd_comms_coproc_rekey_ipc(
        self, target: HostType = HostType.HOST_TYPE_NRF9151
    ) -> Tuple[Optional[bool], Optional[str]]:
        """Rekey IPC.

        Returns:
            Tuple of (success, error_string)
        """
        response, err = send_uart_cmd(
            self._client,
            target=target,
            command="rekey_ipc",
            success_patterns=["IPC rekey completed successfully", "IPC rekey failed"],
            timeout_s=15,
        )
        if err:
            return None, err

        if "IPC rekey completed successfully" in (response or ""):
            return True, None
        elif "IPC rekey failed" in (response or ""):
            return False, "IPC rekey failed"
        return None, f"Unexpected response: {(response or '')[:200]}"
