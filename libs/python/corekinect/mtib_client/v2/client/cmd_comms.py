"""Comms coprocessor (nRF9151) shell commands for V2 MTIB client.

Provides manufacturing shell commands for the communications coprocessor.
Each method sends a command on an existing shell session and parses the
response, returning a Go-style (value, error) tuple.

Shell sessions must be initialized via boot_and_lock_shells() before
calling these methods, which provides a locked ShellCommandHelper.
"""

from typing import List, Optional, Tuple

from .shell import ShellCommandHelper, parse_key_value


class CommsShellCommands:
    """Shell commands for the comms coprocessor (nRF9151).

    Args:
        shell: A locked ShellCommandHelper for the comms coproc UART.
    """

    def __init__(self, shell: ShellCommandHelper):
        self.shell = shell

    def get_chip_ids(self) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Get chip IDs from the comms coprocessor.

        Returns:
            (lora_status, ext_flash_id, error) tuple.
        """
        err, response = self.shell.send_command("get_chip_ids")
        if err:
            return None, None, err

        lora_status = parse_key_value(response, "LoRa hardware available")
        ext_flash_id = parse_key_value(response, "Ext flash chip ID")

        if ext_flash_id is None:
            return None, None, f"Could not parse chip IDs from: {response[:200]}"

        return lora_status, ext_flash_id, None

    def get_modem_fw_version(self) -> Tuple[Optional[str], Optional[str]]:
        """Get modem firmware version.

        Returns:
            (fw_version, error) tuple.
        """
        err, response = self.shell.send_command("get_modem_fw", timeout=15.0)
        if err:
            return None, err

        version = parse_key_value(response, "Modem FW")
        if version is None:
            version = parse_key_value(response, "Modem FW version")
        if version is None:
            version = parse_key_value(response, "modem_fw")

        if version is None:
            return None, f"Could not parse modem FW from: {response[:200]}"

        return version, None

    def get_imei_iccid(self) -> Tuple[Optional[str], Optional[List[str]], Optional[str]]:
        """Get IMEI and ICCID from the cellular modem.

        Returns:
            (imei, iccid_list, error) tuple.
        """
        err, response = self.shell.send_command("imei_iccid", timeout=15.0)
        if err:
            return None, None, err

        # Firmware outputs: "IMEI,ICCID0[,ICCID1]: val1,val2[,val3]"
        # All values are comma-separated after the colon on one line.
        raw = parse_key_value(response, "IMEI")
        if raw is None:
            return None, None, f"Could not parse IMEI from: {response[:200]}"

        parts = [p.strip() for p in raw.split(",") if p.strip()]
        if not parts:
            return None, None, f"Empty IMEI/ICCID value: {response[:200]}"

        imei = parts[0]
        iccid_list = parts[1:] if len(parts) > 1 else None

        return imei, iccid_list, None

    def personalize(self, device_id: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Personalize device with given device ID.

        Returns:
            (hex_key, base64_key, error) tuple.
        """
        err, response = self.shell.send_command(f"personalize {device_id}", timeout=15.0)
        if err:
            return None, None, err

        hex_key = parse_key_value(response, "Public key (hex)")
        base64_key = parse_key_value(response, "Public key (base64)")

        if not hex_key and not base64_key:
            return None, None, f"Could not parse keys from: {response[:200]}"

        return hex_key, base64_key, None

    def write_ext_flash(self, address: str, data_b64: str) -> Tuple[Optional[bool], Optional[str]]:
        """Write data to external flash (data is base64 encoded).

        Returns:
            (success, error) tuple.
        """
        err, response = self.shell.send_command(f"write_ext_flash {address} {data_b64}")
        if err:
            return False, err
        return True, None

    def read_ext_flash(self, address: str, num_bytes: int) -> Tuple[Optional[str], Optional[str]]:
        """Read data from external flash. Returns hex data string.

        Returns:
            (hex_data, error) tuple.
        """
        err, response = self.shell.send_command(f"read_ext_flash {address} {num_bytes}")
        if err:
            return None, err

        hex_data = ""
        for line in response.split("\n"):
            if ":" in line and "|" in line:
                hex_part = line.split("|")[0].strip()
                if ":" in hex_part:
                    hex_values = hex_part.split(":", 1)[1].strip()
                    hex_data += hex_values.replace(" ", "")
        return hex_data, None

    def erase_ext_flash(self) -> Tuple[Optional[bool], Optional[str]]:
        """Erase external flash.

        Returns:
            (success, error) tuple.
        """
        err, response = self.shell.send_command("erase_ext_flash", timeout=30.0)
        if err:
            if response and ("Erase complete" in response or "erased" in response):
                return True, None
            return False, err
        return True, None

    def rekey_ipc(self) -> Tuple[Optional[bool], Optional[str]]:
        """Rekey IPC to replace hard coded keys with device-specific keys.

        Returns:
            (success, error) tuple.
        """
        err, response = self.shell.send_command("rekey_ipc")
        if err:
            if response and "IPC rekey failed" in response:
                return False, "IPC rekey failed"
            return False, err
        return True, None
