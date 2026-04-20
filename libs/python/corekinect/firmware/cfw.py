"""CoreFirmware (.cfw) file generator and parser.

The .cfw format is a proprietary binary container that wraps an encrypted,
app-only firmware image with version metadata for FUOTA delivery via CoreCloud.

Format v2 (23-byte header, big-endian):
    FileVersion   uint16    Always 2
    TimeCreated   uint64    Unix timestamp (seconds)
    AppId         uint16    Firmware application ID (e.g., 108=nRF9151, 109=nRF52840)
    Flags         uint8     bit0=manufacturing, bit2:1=release_track, bit3=debug
    Major         uint16    Major version
    Minor         uint16    Minor version
    Build         uint16    Build number
    ImageLength   uint32    Length of firmware binary
    Image         bytes     Encrypted app-only firmware binary

Release tracks: 0=Bench, 1=Engineering, 2=Production
"""

import struct
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

HEADER_SIZE_V2 = 23
FILE_VERSION_V2 = 2

# Release track constants
TRACK_BENCH = 0
TRACK_ENGINEERING = 1
TRACK_PRODUCTION = 2

# Alpha B0 App IDs
APPID_NRF9151_COMMS = 108
APPID_NRF52840_APP = 109


@dataclass
class CfwMetadata:
    """Parsed .cfw file metadata."""
    file_version: int
    timestamp: int
    app_id: int
    flags: int
    major: int
    minor: int
    build: int
    image_length: int

    @property
    def is_manufacturing(self) -> bool:
        """True if the manufacturing flag is set."""
        return bool(self.flags & 0x01)

    @property
    def release_track(self) -> int:
        """Release track integer: 0=Bench, 1=Engineering, 2=Production."""
        return (self.flags >> 1) & 0x03

    @property
    def is_debug(self) -> bool:
        """True if the debug logging flag is set."""
        return bool(self.flags & 0x08)

    @property
    def version_string(self) -> str:
        """Formatted version string with app_id, version, and track flags."""
        tracks = {0: "B", 1: "E", 2: "P"}
        s = tracks.get(self.release_track, "?")
        if self.is_manufacturing:
            s += "M"
        if self.is_debug:
            s += "D"
        return f"{self.app_id}.{self.major}.{self.minor}.{self.build}-{s}"


def encode_flags(
    release_track: int = TRACK_PRODUCTION,
    manufacturing: bool = False,
    debug: bool = False,
) -> int:
    """Encode release track, manufacturing, and debug flags into a single byte."""
    flags = (release_track & 0x03) << 1
    if manufacturing:
        flags |= 0x01
    if debug:
        flags |= 0x08
    return flags


def generate_cfw(
    image_bin: bytes,
    app_id: int,
    major: int,
    minor: int,
    build: int,
    release_track: int = TRACK_PRODUCTION,
    manufacturing: bool = False,
    debug: bool = False,
    timestamp: Optional[int] = None,
) -> bytes:
    """Generate a .cfw v2 binary from an encrypted app-only firmware image.

    Args:
        image_bin: The encrypted firmware binary (zephyr.signed.encrypted.bin).
        app_id: Application ID (108 for nRF9151 comms, 109 for nRF52840 app).
        major: Major version number.
        minor: Minor version number.
        build: Build number.
        release_track: 0=Bench, 1=Engineering, 2=Production.
        manufacturing: True if this is a manufacturing image.
        debug: True if debug logging is enabled.
        timestamp: Unix timestamp (default: now).

    Returns:
        Complete .cfw v2 binary ready to write to file.
    """
    if timestamp is None:
        timestamp = int(time.time())

    flags = encode_flags(release_track, manufacturing, debug)

    header = struct.pack(
        ">HQHBHHHI",
        FILE_VERSION_V2,
        timestamp,
        app_id,
        flags,
        major,
        minor,
        build,
        len(image_bin),
    )

    if len(header) != HEADER_SIZE_V2:
        # Survives ``python -O`` (``assert`` is stripped) — this is an
        # internal-invariant check that should fail loudly in production
        # if the header pack ever drifts from the documented layout.
        raise ValueError(
            f"CFW header pack produced {len(header)} bytes, expected {HEADER_SIZE_V2}"
        )
    return header + image_bin


def parse_cfw(data: bytes) -> tuple[CfwMetadata, bytes]:
    """Parse a .cfw file into metadata and firmware binary.

    Returns:
        (metadata, image_bytes)
    """
    if len(data) < HEADER_SIZE_V2:
        raise ValueError(f"File too small: {len(data)} bytes (need >= {HEADER_SIZE_V2})")

    ver, ts, appid, flags, major, minor, build, imglen = struct.unpack(
        ">HQHBHHHI", data[:HEADER_SIZE_V2]
    )

    if ver != FILE_VERSION_V2:
        raise ValueError(f"Unsupported .cfw version: {ver} (expected {FILE_VERSION_V2})")

    expected_size = HEADER_SIZE_V2 + imglen
    if len(data) < expected_size:
        raise ValueError(
            f"File truncated: {len(data)} bytes (header says {expected_size})"
        )

    meta = CfwMetadata(
        file_version=ver,
        timestamp=ts,
        app_id=appid,
        flags=flags,
        major=major,
        minor=minor,
        build=build,
        image_length=imglen,
    )

    image = data[HEADER_SIZE_V2 : HEADER_SIZE_V2 + imglen]
    return meta, image


def generate_cfw_from_build(
    signed_encrypted_bin_path: str,
    app_id: int,
    major: int,
    minor: int,
    build: int,
    output_path: Optional[str] = None,
    release_track: int = TRACK_PRODUCTION,
    manufacturing: bool = False,
    debug: bool = False,
) -> str:
    """Generate a .cfw file from a build artifact (zephyr.signed.encrypted.bin).

    Args:
        signed_encrypted_bin_path: Path to zephyr.signed.encrypted.bin from west build.
        app_id: Application ID.
        major, minor, build: Version numbers.
        output_path: Output .cfw path. Auto-generated if None.
        release_track: Release track.
        manufacturing: Manufacturing flag.
        debug: Debug flag.

    Returns:
        Path to the generated .cfw file.
    """
    image_bin = Path(signed_encrypted_bin_path).read_bytes()

    cfw_data = generate_cfw(
        image_bin=image_bin,
        app_id=app_id,
        major=major,
        minor=minor,
        build=build,
        release_track=release_track,
        manufacturing=manufacturing,
        debug=debug,
    )

    if output_path is None:
        flags = encode_flags(release_track, manufacturing, debug)
        tracks = {0: "B", 1: "E", 2: "P"}
        flag_str = tracks.get(release_track, "?")
        if manufacturing:
            flag_str += "M"
        if debug:
            flag_str += "D"
        output_path = str(
            Path(signed_encrypted_bin_path).parent
            / f"{app_id}.{major}.{minor}.{build}-{flag_str}.cfw"
        )

    Path(output_path).write_bytes(cfw_data)
    return output_path


def main():
    """CLI for generating .cfw files from build artifacts."""
    import argparse

    parser = argparse.ArgumentParser(description="Generate .cfw files from firmware builds")
    parser.add_argument("bin_path", help="Path to zephyr.signed.encrypted.bin")
    parser.add_argument("--app-id", type=int, required=True, help="App ID (108=comms, 109=app)")
    parser.add_argument("--major", type=int, required=True, help="Major version")
    parser.add_argument("--minor", type=int, required=True, help="Minor version")
    parser.add_argument("--build", type=int, required=True, help="Build number")
    parser.add_argument("--output", "-o", help="Output .cfw path (auto-generated if omitted)")
    parser.add_argument(
        "--track",
        type=int,
        choices=[0, 1, 2],
        default=0,
        help="Release track: 0=Bench, 1=Engineering, 2=Production",
    )
    parser.add_argument("--mfg", action="store_true", help="Set manufacturing flag")
    parser.add_argument("--debug", action="store_true", help="Set debug flag")

    args = parser.parse_args()

    output = generate_cfw_from_build(
        signed_encrypted_bin_path=args.bin_path,
        app_id=args.app_id,
        major=args.major,
        minor=args.minor,
        build=args.build,
        output_path=args.output,
        release_track=args.track,
        manufacturing=args.mfg,
        debug=args.debug,
    )
    print(f"Generated: {output}")


if __name__ == "__main__":
    main()
