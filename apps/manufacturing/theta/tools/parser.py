#!/usr/bin/env python3
"""
Manufacturing Log Parser

This tool parses through manufacturing logs to extract device information:
- Serial number
- IMEI
- ICCIDs (split into Verizon and Onomondo columns)

It can distinguish between complete and incomplete runs, discards duplicates,
and outputs results to CSV format. Handles multiple devices per log file.
"""

import argparse
import csv
import glob
import logging
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class DeviceInfo:
    """Represents device information extracted from logs."""

    serial_number: str
    imei: str
    verizon_iccid: str
    onomondo_iccid: str
    log_file: str
    timestamp: str

    def __post_init__(self):
        # Ensure ICCIDs are strings
        if self.verizon_iccid is None:
            self.verizon_iccid = ""
        if self.onomondo_iccid is None:
            self.onomondo_iccid = ""


class ManufacturingLogParser:
    """Parser for manufacturing logs to extract device information."""

    def __init__(self):
        self.logger = self._setup_logging()

        # Regex patterns for extracting information
        self.serial_pattern = re.compile(r"Personalizing device with serial number: (\w+)")
        self.imei_pattern = re.compile(r"Device IMEI: (\d+)")
        self.iccid_pattern = re.compile(r"Device ICCIDs: (.+)")
        self.timestamp_pattern = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+")

        # Patterns to identify complete vs incomplete runs
        self.completion_patterns = [
            re.compile(r"Personalization took \d+\.\d+ seconds"),
            re.compile(r"Successfully flashed app proc firmware"),
            re.compile(r"Device ID: [A-F0-9]+"),
            re.compile(r"Device public key \(base64\): .+"),
        ]

        self.start_pattern = re.compile(r"Personalizing device with serial number:")
        self.error_patterns = [
            re.compile(r"ERROR"),
            re.compile(r"Exception"),
            re.compile(r"Traceback"),
            re.compile(r"Failed"),
        ]

    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration."""
        logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
        return logging.getLogger(__name__)

    def clean_iccid(self, iccid: str) -> str:
        """
        Clean ICCID by removing ANSI escape sequences and trailing characters.

        Args:
            iccid: Raw ICCID string

        Returns:
            Cleaned ICCID string
        """
        # Remove ANSI escape sequences (like [0m)
        cleaned = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", iccid)
        # Remove any trailing whitespace and non-printable characters
        cleaned = re.sub(r"[^\d]", "", cleaned)
        return cleaned

    def parse_iccids(self, iccids_str: str) -> Tuple[str, str]:
        """
        Parse ICCIDs string and separate into Verizon and Onomondo.

        Args:
            iccids_str: Comma-separated ICCIDs string

        Returns:
            Tuple of (verizon_iccid, onomondo_iccid)
        """
        verizon_iccid = ""
        onomondo_iccid = ""

        # Split by comma and clean each ICCID
        iccids = [self.clean_iccid(iccid.strip()) for iccid in iccids_str.split(",")]

        for iccid in iccids:
            if not iccid:  # Skip empty ICCIDs
                continue
            if iccid.startswith("891480"):
                verizon_iccid = iccid
            elif iccid.startswith("894573"):
                onomondo_iccid = iccid
            # Note: We're ignoring other carriers for now

        return verizon_iccid, onomondo_iccid

    def split_log_into_device_runs(self, log_content: str) -> List[str]:
        """
        Split a log file into individual device runs.

        Args:
            log_content: The full log content as string

        Returns:
            List of individual device run log sections
        """
        # Find all positions where a new device starts
        start_positions = []
        for match in self.start_pattern.finditer(log_content):
            start_positions.append(match.start())

        if not start_positions:
            return []

        # Add the end of the file as the last position
        start_positions.append(len(log_content))

        # Extract each device run
        device_runs = []
        for i in range(len(start_positions) - 1):
            start = start_positions[i]
            end = start_positions[i + 1]
            device_run = log_content[start:end].strip()
            if device_run:
                device_runs.append(device_run)

        return device_runs

    def is_complete_run(self, log_content: str) -> bool:
        """
        Determine if a log represents a complete manufacturing run.

        Args:
            log_content: The full log content as string

        Returns:
            True if the run appears complete, False otherwise
        """
        # Check for completion indicators
        has_completion = any(pattern.search(log_content) for pattern in self.completion_patterns)

        # Check for error indicators
        has_errors = any(pattern.search(log_content) for pattern in self.error_patterns)

        # Check for start indicator
        has_start = self.start_pattern.search(log_content) is not None

        # A complete run should have start, completion, and no errors
        return has_start and has_completion and not has_errors

    def extract_device_info(self, log_content: str, log_file: str) -> Optional[DeviceInfo]:
        """
        Extract device information from a log section.

        Args:
            log_content: The log content as string
            log_file: Name of the log file

        Returns:
            DeviceInfo object if successful, None otherwise
        """
        try:
            # Extract serial number
            serial_match = self.serial_pattern.search(log_content)
            if not serial_match:
                self.logger.warning(f"No serial number found in {log_file}")
                return None

            serial_number = serial_match.group(1)

            # Extract IMEI
            imei_match = self.imei_pattern.search(log_content)
            if not imei_match:
                self.logger.warning(f"No IMEI found in {log_file} for serial {serial_number}")
                return None

            imei = imei_match.group(1)

            # Extract ICCIDs
            iccid_match = self.iccid_pattern.search(log_content)
            if not iccid_match:
                self.logger.warning(f"No ICCIDs found in {log_file} for serial {serial_number}")
                return None

            # Parse and separate ICCIDs
            iccids_str = iccid_match.group(1)
            verizon_iccid, onomondo_iccid = self.parse_iccids(iccids_str)

            # Extract timestamp (first timestamp in the log)
            timestamp_match = self.timestamp_pattern.search(log_content)
            timestamp = timestamp_match.group(1) if timestamp_match else "Unknown"

            return DeviceInfo(
                serial_number=serial_number,
                imei=imei,
                verizon_iccid=verizon_iccid,
                onomondo_iccid=onomondo_iccid,
                log_file=log_file,
                timestamp=timestamp,
            )

        except Exception as e:
            self.logger.error(f"Error extracting device info from {log_file}: {e}")
            return None

    def parse_log_file(self, log_file_path: str) -> List[DeviceInfo]:
        """
        Parse a single log file and extract device information for all devices.

        Args:
            log_file_path: Path to the log file

        Returns:
            List of DeviceInfo objects
        """
        try:
            with open(log_file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Split the log into individual device runs
            device_runs = self.split_log_into_device_runs(content)

            if not device_runs:
                self.logger.info(f"No device runs found in {log_file_path}")
                return []

            self.logger.info(f"Found {len(device_runs)} device runs in {log_file_path}")

            device_infos = []
            for i, device_run in enumerate(device_runs):
                # Check if this is a complete run
                if not self.is_complete_run(device_run):
                    self.logger.info(f"Skipping incomplete run {i+1} in {log_file_path}")
                    continue

                # Extract device information
                device_info = self.extract_device_info(device_run, os.path.basename(log_file_path))

                if device_info:
                    self.logger.info(
                        f"Successfully extracted info for serial {device_info.serial_number} (run {i+1}) from {log_file_path}"
                    )
                    device_infos.append(device_info)

            return device_infos

        except Exception as e:
            self.logger.error(f"Error reading log file {log_file_path}: {e}")
            return []

    def find_log_files(self, folder_path: str) -> List[str]:
        """
        Find all log files in the specified folder.

        Args:
            folder_path: Path to the folder containing logs

        Returns:
            List of log file paths
        """
        log_extensions = ["*.log", "*.txt"]
        log_files = []

        for ext in log_extensions:
            pattern = os.path.join(folder_path, ext)
            log_files.extend(glob.glob(pattern))

        # Also look for files without extensions that might be logs
        for file_path in glob.glob(os.path.join(folder_path, "*")):
            if os.path.isfile(file_path) and not os.path.splitext(file_path)[1]:
                log_files.append(file_path)

        return sorted(log_files)

    def parse_all_logs(self, folder_path: str) -> List[DeviceInfo]:
        """
        Parse all log files in the specified folder.

        Args:
            folder_path: Path to the folder containing logs

        Returns:
            List of DeviceInfo objects
        """
        log_files = self.find_log_files(folder_path)

        if not log_files:
            self.logger.warning(f"No log files found in {folder_path}")
            return []

        self.logger.info(f"Found {len(log_files)} log files to process")

        device_infos = []
        for log_file in log_files:
            device_infos.extend(self.parse_log_file(log_file))

        return device_infos

    def remove_duplicates(self, device_infos: List[DeviceInfo]) -> List[DeviceInfo]:
        """
        Remove duplicate device information based on serial number.
        Keeps the most recent entry for each serial number.

        Args:
            device_infos: List of DeviceInfo objects

        Returns:
            List of DeviceInfo objects with duplicates removed
        """
        # Group by serial number
        serial_groups = defaultdict(list)
        for device_info in device_infos:
            serial_groups[device_info.serial_number].append(device_info)

        # Keep the most recent entry for each serial number
        unique_devices = []
        for serial, devices in serial_groups.items():
            if len(devices) > 1:
                self.logger.info(f"Found {len(devices)} entries for serial {serial}, keeping most recent")
                # Sort by timestamp and keep the latest
                devices.sort(key=lambda x: x.timestamp, reverse=True)

            unique_devices.append(devices[0])

        return unique_devices

    def write_csv(self, device_infos: List[DeviceInfo], output_file: str):
        """
        Write device information to CSV file.

        Args:
            device_infos: List of DeviceInfo objects
            output_file: Path to output CSV file
        """
        try:
            with open(output_file, "w", newline="", encoding="utf-8") as csvfile:
                fieldnames = ["Index", "Serial Number", "IMEI", "Verizon ICCID", "Onomondo ICCID", "Timestamp"]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                writer.writeheader()
                for i, device_info in enumerate(device_infos, 1):
                    writer.writerow(
                        {
                            "Index": i,
                            "Serial Number": device_info.serial_number,
                            "IMEI": device_info.imei,
                            "Verizon ICCID": device_info.verizon_iccid,
                            "Onomondo ICCID": device_info.onomondo_iccid,
                            "Timestamp": device_info.timestamp,
                        }
                    )

            self.logger.info(f"Successfully wrote {len(device_infos)} device records to {output_file}")

        except Exception as e:
            self.logger.error(f"Error writing CSV file {output_file}: {e}")
            raise

    def write_simple_csv(self, device_infos: List[DeviceInfo], output_file: str):
        """
        Write simple CSV with just IMEI and Verizon ICCID, no headers.

        Args:
            device_infos: List of DeviceInfo objects
            output_file: Path to output CSV file
        """
        try:
            with open(output_file, "w", newline="", encoding="utf-8") as csvfile:
                for device_info in device_infos:
                    # Only write if there's a Verizon ICCID
                    if device_info.verizon_iccid:
                        csvfile.write(f"{device_info.imei},{device_info.verizon_iccid}\n")

            self.logger.info(f"Successfully wrote {len(device_infos)} IMEI/Verizon records to {output_file}")

        except Exception as e:
            self.logger.error(f"Error writing simple CSV file {output_file}: {e}")
            raise


def main():
    """Main function to run the log parser."""
    parser = argparse.ArgumentParser(
        description="Parse manufacturing logs to extract device information",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python parser.py /path/to/logs
  python parser.py /path/to/logs --output devices.csv
  python parser.py /path/to/logs --verbose
        """,
    )

    parser.add_argument("folder", help="Folder containing log files to parse")

    parser.add_argument(
        "--output",
        "-o",
        default="alpha_devices.csv",
        help="Output CSV file (default: alpha_devices.csv)",
    )

    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    # Setup logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Validate folder path
    if not os.path.isdir(args.folder):
        print(f"Error: '{args.folder}' is not a valid directory", file=sys.stderr)
        sys.exit(1)

    # Create parser and process logs
    log_parser = ManufacturingLogParser()

    try:
        # Parse all logs
        device_infos = log_parser.parse_all_logs(args.folder)

        if not device_infos:
            print("No valid device information found in logs")
            sys.exit(0)

        # Remove duplicates
        unique_devices = log_parser.remove_duplicates(device_infos)

        print(f"Found {len(device_infos)} total device records")
        print(f"After removing duplicates: {len(unique_devices)} unique devices")

        # Write to CSV
        log_parser.write_csv(unique_devices, args.output)

        # Write simple IMEI/Verizon CSV
        simple_output = args.output.replace(".csv", "_imei_verizon.csv")
        log_parser.write_simple_csv(unique_devices, simple_output)

        print(f"Results written to: {args.output}")
        print(f"Simple IMEI/Verizon CSV written to: {simple_output}")
        print(f"Total devices found: {len(unique_devices)}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
