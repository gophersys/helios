"""CFW (CoreKinect Firmware) binary header parsing.

The CFW format is a firmware packaging format used for FUOTA delivery
via CoreCloud. The 23-byte header contains version, app ID, and flags.

Usage:
    from corekinect.test.cfw import parse_cfw_header

    info = parse_cfw_header(Path("108.0.5.2-BM.cfw"))
    print(info["target_string"])  # "108.0.5.2-BM"
    print(info["app_id"])         # 108
    print(info["is_mfg"])         # True
"""

import struct
from pathlib import Path
from typing import Any, Dict, Union

# Release track encoding in CFW flags bits 2:1
RELEASE_TRACKS: Dict[int, str] = {
    0: "B",  # Bench
    1: "E",  # Engineering
    2: "P",  # Production
}


def parse_cfw_header(cfw_path: Union[str, Path]) -> Dict[str, Any]:
    """Parse CFW header (23 bytes) and return metadata.

    Header layout (big-endian):
        FileVersion:  2 bytes (uint16)
        TimeCreated:  8 bytes (uint64)
        AppId:        2 bytes (uint16)
        Flags:        1 byte  (uint8)
        Major:        2 bytes (uint16)
        Minor:        2 bytes (uint16)
        Build:        2 bytes (uint16)
        ImageLen:     4 bytes (int32)

    Flags bits:
        bit 0:   Manufacturing (M)
        bits 2:1: Release track (0=Bench, 1=Engineering, 2=Production)
        bit 3:   Debug (D)

    Returns:
        Dict with: file_version, app_id, flags, major, minor, build,
                   image_len, target_string, version_string, track,
                   is_mfg, is_debug
    """
    with open(cfw_path, "rb") as f:
        header = f.read(23)

    if len(header) < 23:
        raise ValueError(f"CFW header too short: {len(header)} bytes")

    file_ver, _, app_id, flags, major, minor, build, image_len = struct.unpack(
        ">HQHBHHHi", header
    )

    release_track = (flags >> 1) & 0x03  # bits 2:1
    is_mfg = bool(flags & 0x01)
    is_debug = bool(flags & 0x08)

    track_char = RELEASE_TRACKS.get(release_track, "?")

    suffix = track_char
    if is_mfg:
        suffix += "M"
    if is_debug:
        suffix += "D"

    target_string = f"{app_id}.{major}.{minor}.{build}-{suffix}"
    version_string = f"{major}.{minor}.{build}"

    return {
        "file_version": file_ver,
        "app_id": app_id,
        "flags": flags,
        "major": major,
        "minor": minor,
        "build": build,
        "image_len": image_len,
        "target_string": target_string,
        "version_string": version_string,
        "track": track_char,
        "is_mfg": is_mfg,
        "is_debug": is_debug,
    }
