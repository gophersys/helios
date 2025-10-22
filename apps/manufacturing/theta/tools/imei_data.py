#!/usr/bin/env python3
"""
Script to extract IMEI and ICCID pairs from alpha manufacturing logs.
Scans log files for IMEI/ICCID verification entries, extracts the data,
and outputs to CSV files organized by carrier (Verizon, Soracom, Onomondo).
"""

import re
import csv
import os
import sys
from datetime import datetime
from pathlib import Path
import argparse
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass


@dataclass
class DeviceInfo:
    """Data class to store device information"""
    serial_number: str
    imei: Optional[str] = None
    iccids: List[str] = None
    timestamp: Optional[datetime] = None
    
    def __post_init__(self):
        if self.iccids is None:
            self.iccids = []


def parse_timestamp(timestamp_str: str) -> Optional[datetime]:
    """Parse timestamp string to datetime object."""
    try:
        # Format: 2025-10-17 20:08:49,316
        return datetime.strptime(timestamp_str.split(',')[0], '%Y-%m-%d %H:%M:%S')
    except ValueError:
        return None


def get_carrier_from_iccid(iccid: str) -> str:
    """Determine carrier from ICCID prefix"""
    if iccid.startswith("89148"):
        return "Verizon"
    elif iccid.startswith("894231"):
        return "Soracom"
    elif iccid.startswith("894573"):
        return "Onomondo"
    else:
        return "Unknown"


def extract_imei_iccid_from_log_line(line: str) -> tuple[Optional[str], List[str]]:
    """Extract IMEI and ICCIDs from a log line"""
    imei = None
    iccids = []
    
    # Extract IMEI: pattern like "IMEI: 359746161663153"
    imei_match = re.search(r'IMEI:\s*(\d+)', line)
    if imei_match:
        imei = imei_match.group(1)
    
    # Extract ICCIDs: pattern like "ICCIDs: ['89148000009808571519', '89457300000035348575']"
    iccids_match = re.search(r'ICCIDs:\s*\[(.*?)\]', line)
    if iccids_match:
        iccids_str = iccids_match.group(1)
        # Extract individual ICCIDs from the list
        iccid_matches = re.findall(r"'([^']+)'", iccids_str)
        iccids = iccid_matches
    
    return imei, iccids


def extract_serial_number_from_log_line(line: str) -> Optional[str]:
    """Extract serial number from personalization log line"""
    # Pattern: "Personalizing device with serial number: 0528"
    match = re.search(r'Personalizing device with serial number:\s*(\S+)', line)
    if match:
        return match.group(1).strip()
    return None


def extract_timestamp_from_log_line(line: str) -> Optional[datetime]:
    """Extract timestamp from log line"""
    # Pattern: "2025-10-17 20:08:49,316 - alpha-manufacturing - INFO - ..."
    match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+)', line)
    if match:
        return parse_timestamp(match.group(1))
    return None


def process_log_file(file_path: Path) -> Dict[str, DeviceInfo]:
    """Process a single log file and extract device information"""
    devices = {}  # Dictionary to store device info: {serial_number: DeviceInfo}
    current_serial = None
    current_timestamp = None
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                
                # Extract timestamp from each line
                timestamp = extract_timestamp_from_log_line(line)
                if timestamp:
                    current_timestamp = timestamp
                
                # Look for serial number personalization
                serial_match = extract_serial_number_from_log_line(line)
                if serial_match:
                    current_serial = serial_match
                    # Initialize device info if not exists
                    if current_serial not in devices:
                        devices[current_serial] = DeviceInfo(
                            serial_number=current_serial,
                            timestamp=current_timestamp
                        )
                
                # Look for IMEI and ICCID verification
                if 'Verifying IMEI and ICCIDs' in line and current_serial:
                    # The next lines should contain the actual IMEI and ICCIDs
                    continue
                
                # Extract IMEI and ICCIDs from the line
                imei, iccids = extract_imei_iccid_from_log_line(line)
                if imei and current_serial and current_serial in devices:
                    devices[current_serial].imei = imei
                    devices[current_serial].timestamp = current_timestamp
                
                if iccids and current_serial and current_serial in devices:
                    devices[current_serial].iccids = iccids
                    devices[current_serial].timestamp = current_timestamp
    
    except (FileNotFoundError, UnicodeDecodeError) as e:
        print(f"Error processing {file_path}: {e}")
        return {}
    
    return devices


def process_log_folder(folder_path: Path, since_datetime: Optional[datetime] = None, until_datetime: Optional[datetime] = None) -> Dict[str, DeviceInfo]:
    """Process all log files in a folder and extract device information"""
    all_devices = {}  # Dictionary to store all device info: {serial_number: DeviceInfo}
    processed_files = 0
    skipped_files = 0
    
    if not folder_path.exists():
        print(f"Error: Folder {folder_path} does not exist")
        return {}
    
    # Find all log files in the folder
    log_files = list(folder_path.glob('*.log'))
    
    if not log_files:
        print(f"No log files found in {folder_path}")
        return {}
    
    print(f"Found {len(log_files)} log files")
    
    for log_file in log_files:
        print(f"Processing {log_file.name}...")
        devices = process_log_file(log_file)
        
        # Merge device information, keeping the most recent data
        for serial, device in devices.items():
            # Apply time filter if specified (filter by device timestamp)
            if since_datetime and device.timestamp and device.timestamp < since_datetime:
                skipped_files += 1
                continue
            
            if until_datetime and device.timestamp and device.timestamp >= until_datetime:
                skipped_files += 1
                continue
                
            if serial not in all_devices:
                all_devices[serial] = device
            else:
                # Update with more recent data if available
                if device.timestamp and (not all_devices[serial].timestamp or 
                                       device.timestamp > all_devices[serial].timestamp):
                    all_devices[serial].imei = device.imei
                    all_devices[serial].iccids = device.iccids
                    all_devices[serial].timestamp = device.timestamp
        
        processed_files += 1
    
    print(f"\n=== PROCESSING SUMMARY ===")
    print(f"Processed {processed_files} files, skipped {skipped_files} files")
    print(f"Total unique devices found: {len(all_devices)}")
    
    # Device information summary
    devices_with_imei = sum(1 for d in all_devices.values() if d.imei)
    devices_with_iccids = sum(1 for d in all_devices.values() if d.iccids)
    total_iccids = sum(len(d.iccids) for d in all_devices.values())
    
    print(f"\n=== DEVICE INFORMATION SUMMARY ===")
    print(f"Devices with IMEI: {devices_with_imei}")
    print(f"Devices with ICCIDs: {devices_with_iccids}")
    print(f"Total ICCIDs: {total_iccids}")
    
    return all_devices


def save_device_info_to_csv(devices: Dict[str, DeviceInfo], output_file: str) -> int:
    """Save device information (Serial, IMEI, ICCID0, ICCID1) to CSV file."""
    device_data = []
    for serial, device in devices.items():
        if device.imei or device.iccids:
            # Get ICCIDs, pad with empty strings if less than 2
            iccid0 = device.iccids[0] if len(device.iccids) > 0 else ""
            iccid1 = device.iccids[1] if len(device.iccids) > 1 else ""
            
            device_data.append({
                'Serial': serial,
                'IMEI': device.imei or "",
                'ICCID0': iccid0,
                'ICCID1': iccid1,
                'Timestamp': device.timestamp.strftime('%Y-%m-%d %H:%M:%S') if device.timestamp else ""
            })
    
    if device_data:
        with open(output_file, 'w', newline='') as f:
            fieldnames = ['Serial', 'IMEI', 'ICCID0', 'ICCID1', 'Timestamp']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(sorted(device_data, key=lambda x: x['Serial']))
        return len(device_data)
    else:
        # Create empty file with headers
        with open(output_file, 'w', newline='') as f:
            fieldnames = ['Serial', 'IMEI', 'ICCID0', 'ICCID1', 'Timestamp']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
        return 0


def save_carrier_imei_iccid_pairs(devices: Dict[str, DeviceInfo], carrier_name: str, output_file: str) -> int:
    """Save IMEI/ICCID pairs for a specific carrier to CSV file."""
    carrier_data = []
    
    for serial, device in devices.items():
        if device.imei and device.iccids:
            for iccid in device.iccids:
                carrier = get_carrier_from_iccid(iccid)
                if carrier == carrier_name:
                    carrier_data.append({
                        'Serial': serial,
                        'IMEI': device.imei,
                        'ICCID': iccid,
                        'Timestamp': device.timestamp.strftime('%Y-%m-%d %H:%M:%S') if device.timestamp else ""
                    })
    
    if carrier_data:
        with open(output_file, 'w', newline='') as f:
            fieldnames = ['Serial', 'IMEI', 'ICCID', 'Timestamp']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(sorted(carrier_data, key=lambda x: x['IMEI']))
        return len(carrier_data)
    else:
        # Create empty file with headers
        with open(output_file, 'w', newline='') as f:
            fieldnames = ['Serial', 'IMEI', 'ICCID', 'Timestamp']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
        return 0


def save_carrier_imei_iccid_only(devices: Dict[str, DeviceInfo], carrier_name: str, output_file: str) -> int:
    """Save only IMEI/ICCID pairs for a specific carrier to CSV file (no serial, no timestamp)."""
    carrier_data = []
    
    for serial, device in devices.items():
        if device.imei and device.iccids:
            for iccid in device.iccids:
                carrier = get_carrier_from_iccid(iccid)
                if carrier == carrier_name:
                    carrier_data.append({
                        'IMEI': device.imei,
                        'ICCID': iccid
                    })
    
    if carrier_data:
        with open(output_file, 'w', newline='') as f:
            fieldnames = ['IMEI', 'ICCID']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(sorted(carrier_data, key=lambda x: x['IMEI']))
        return len(carrier_data)
    else:
        # Create empty file with headers
        with open(output_file, 'w', newline='') as f:
            fieldnames = ['IMEI', 'ICCID']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
        return 0


def main():
    parser = argparse.ArgumentParser(description='Extract IMEI and ICCID pairs from alpha manufacturing logs')
    parser.add_argument('folder_path', help='Path to folder containing log files')
    parser.add_argument('-d', '--devices', default='devices.csv', 
                       help='Output CSV file for device info (Serial, IMEI, ICCID0, ICCID1) (default: devices.csv)')
    parser.add_argument('-s', '--since', 
                       help='Only process files since this datetime (ISO format: YYYY-MM-DDTHH:MM:SS)')
    parser.add_argument('-u', '--until', 
                       help='Only process files until this datetime (ISO format: YYYY-MM-DDTHH:MM:SS)')
    
    args = parser.parse_args()
    
    # Parse since datetime if provided
    since_datetime = None
    if args.since:
        try:
            since_datetime = datetime.fromisoformat(args.since.replace('Z', '+00:00'))
        except ValueError:
            print(f"Error: Invalid datetime format '{args.since}'. Use ISO format: YYYY-MM-DDTHH:MM:SS")
            sys.exit(1)
        print(f"Filtering files since: {since_datetime}")
    
    # Parse until datetime if provided
    until_datetime = None
    if args.until:
        try:
            until_datetime = datetime.fromisoformat(args.until.replace('Z', '+00:00'))
        except ValueError:
            print(f"Error: Invalid datetime format '{args.until}'. Use ISO format: YYYY-MM-DDTHH:MM:SS")
            sys.exit(1)
        print(f"Filtering files until: {until_datetime}")
    
    # Extract device information from logs
    print(f"Scanning folder: {args.folder_path}")
    devices = process_log_folder(Path(args.folder_path), since_datetime, until_datetime)
    
    if not devices:
        print("No devices found")
        return
    
    # Save device information to CSV (Serial, IMEI, ICCID0, ICCID1)
    device_count = save_device_info_to_csv(devices, args.devices)
    print(f"\n=== OUTPUT FILES ===")
    print(f"Device information saved to: {args.devices} ({device_count} entries)")
    
    # Generate carrier-specific IMEI/ICCID pair files
    carriers = ['Verizon', 'Soracom', 'Onomondo']
    carrier_stats = {}
    
    print(f"\n=== CARRIER-SPECIFIC IMEI/ICCID FILES ===")
    for carrier in carriers:
        filename = f"{carrier.lower()}_imei_iccid_pairs.csv"
        count = save_carrier_imei_iccid_pairs(devices, carrier, filename)
        carrier_stats[carrier] = count
        print(f"{carrier} IMEI/ICCID pairs saved to: {filename} ({count} entries)")
    
    # Generate carrier-specific IMEI/ICCID only files (no serial, no timestamp)
    print(f"\n=== CARRIER-SPECIFIC IMEI/ICCID ONLY FILES ===")
    for carrier in carriers:
        filename = f"{carrier.lower()}_imei_iccid_only.csv"
        count = save_carrier_imei_iccid_only(devices, carrier, filename)
        print(f"{carrier} IMEI/ICCID only saved to: {filename} ({count} entries)")
    
    # Display sample device information
    devices_with_data = {serial: device for serial, device in devices.items() if device.imei or device.iccids}
    if devices_with_data:
        print(f"\nSample device information (showing first 5 of {len(devices_with_data)}):")
        for i, (serial, device) in enumerate(sorted(devices_with_data.items())[:5]):
            print(f"  Serial: {serial}")
            if device.imei:
                print(f"    IMEI: {device.imei}")
            if device.iccids:
                print(f"    ICCIDs: {', '.join(device.iccids)}")
                # Show carrier info for each ICCID
                for iccid in device.iccids:
                    carrier = get_carrier_from_iccid(iccid)
                    print(f"      {iccid} -> {carrier}")
            if device.timestamp:
                print(f"    Timestamp: {device.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
            print()
        if len(devices_with_data) > 5:
            print(f"  ... and {len(devices_with_data) - 5} more devices with IMEI/ICCID data")
    
    # Display carrier summary
    print(f"\n=== CARRIER SUMMARY ===")
    total_carrier_pairs = sum(carrier_stats.values())
    for carrier, count in carrier_stats.items():
        percentage = (count / total_carrier_pairs * 100) if total_carrier_pairs > 0 else 0
        print(f"{carrier}: {count} pairs ({percentage:.1f}%)")
    print(f"Total IMEI/ICCID pairs: {total_carrier_pairs}")


if __name__ == '__main__':
    main()
