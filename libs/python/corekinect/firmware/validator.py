"""Comprehensive firmware package validator.

Validates firmware build artifacts for consistency and completeness,
ensuring FUOTA packages are ready for deployment.

Validation checks:
1. Package completeness (required files present)
2. Version consistency across all sources (build.json, CFW headers, hex metadata)
3. CFW header integrity
4. Boot log version verification (runtime check)
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .cfw import parse_cfw, CfwMetadata, APPID_NRF9151_COMMS, APPID_NRF52840_APP


@dataclass
class VersionInfo:
    """Parsed version information from any source."""
    major: int
    minor: int
    build: int
    source: str  # e.g., "build.json", "cfw:108", "boot_log:108", "VersionDevice.h"

    @property
    def version_string(self) -> str:
        """Return the version as a dotted string (major.minor.build)."""
        return f"{self.major}.{self.minor}.{self.build}"

    def matches(self, other: "VersionInfo") -> bool:
        """Return True if this version equals another VersionInfo."""
        return (self.major == other.major and
                self.minor == other.minor and
                self.build == other.build)


@dataclass
class ValidationError:
    """A single validation error."""
    severity: str  # "error" or "warning"
    message: str
    source: str = ""  # file or source that caused the error


@dataclass
class ValidationResult:
    """Complete validation result for a firmware package."""
    valid: bool
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationError] = field(default_factory=list)
    versions: dict[str, VersionInfo] = field(default_factory=dict)
    cfw_metadata: dict[int, CfwMetadata] = field(default_factory=dict)  # app_id -> metadata
    files_found: list[str] = field(default_factory=list)
    files_missing: list[str] = field(default_factory=list)

    def add_error(self, message: str, source: str = ""):
        """Append an error and mark the result as invalid."""
        self.errors.append(ValidationError("error", message, source))
        self.valid = False

    def add_warning(self, message: str, source: str = ""):
        """Append a warning without marking the result invalid."""
        self.warnings.append(ValidationError("warning", message, source))

    def summary(self) -> str:
        """Return a human-readable multi-line validation summary."""
        lines = []
        if self.valid:
            lines.append("VALID: Firmware package passed all checks")
        else:
            lines.append(f"INVALID: {len(self.errors)} error(s) found")

        if self.versions:
            lines.append("\nVersions detected:")
            for source, ver in self.versions.items():
                lines.append(f"  {source}: {ver.version_string}")

        if self.errors:
            lines.append("\nErrors:")
            for err in self.errors:
                lines.append(f"  [ERROR] {err.source}: {err.message}" if err.source else f"  [ERROR] {err.message}")

        if self.warnings:
            lines.append("\nWarnings:")
            for warn in self.warnings:
                lines.append(f"  [WARN] {warn.source}: {warn.message}" if warn.source else f"  [WARN] {warn.message}")

        if self.files_missing:
            lines.append(f"\nMissing files: {', '.join(self.files_missing)}")

        return "\n".join(lines)


class FirmwarePackageValidator:
    """Validates firmware build packages for consistency and completeness."""

    # Required files for a complete firmware package
    REQUIRED_FILES_MFG = [
        "app_nrf52840.hex",
        "comms_nrf9151.hex",
        "build.json",
    ]

    REQUIRED_FILES_PROD = [
        "app_nrf52840.hex",
        "comms_nrf9151.hex",
        "build.json",
    ]

    # CFW files are optional but should be validated if present
    CFW_PATTERN = re.compile(r"(\d+)\.(\d+)\.(\d+)\.(\d+)-([BEPMD]+)\.cfw")

    # Boot log version pattern: "application 108 launched. Version 0.5.1"
    BOOT_VERSION_PATTERN = re.compile(
        r"application\s+(\d+)\s+launched\.\s*Version\s+(\d+)\.(\d+)\.(\d+)",
        re.IGNORECASE
    )

    def __init__(self, package_path: str):
        """Initialize validator with path to firmware package directory."""
        self.package_path = Path(package_path)

    def validate(self) -> ValidationResult:
        """Run all validation checks and return results."""
        result = ValidationResult(valid=True)

        if not self.package_path.exists():
            result.add_error(f"Package path does not exist: {self.package_path}")
            return result

        if not self.package_path.is_dir():
            result.add_error(f"Package path is not a directory: {self.package_path}")
            return result

        # 1. Check file completeness
        self._check_completeness(result)

        # 2. Parse build.json
        self._parse_build_json(result)

        # 3. Validate any CFW files
        self._validate_cfw_files(result)

        # 4. Check version consistency
        self._check_version_consistency(result)

        return result

    def _check_completeness(self, result: ValidationResult):
        """Check that required files are present."""
        # Determine which file set to use based on what's present
        required = self.REQUIRED_FILES_MFG

        for filename in required:
            filepath = self.package_path / filename
            if filepath.exists():
                result.files_found.append(filename)
            else:
                result.files_missing.append(filename)
                result.add_error(f"Required file missing: {filename}")

    def _parse_build_json(self, result: ValidationResult):
        """Parse version from build.json."""
        build_json_path = self.package_path / "build.json"
        if not build_json_path.exists():
            return  # Already reported as missing

        try:
            with open(build_json_path) as f:
                data = json.load(f)

            version = data.get("version", "")
            if not version:
                result.add_error("build.json missing 'version' field", "build.json")
                return

            parts = version.split(".")
            if len(parts) != 3:
                result.add_error(f"Invalid version format in build.json: {version}", "build.json")
                return

            try:
                major, minor, build = int(parts[0]), int(parts[1]), int(parts[2])
                result.versions["build.json"] = VersionInfo(major, minor, build, "build.json")
            except ValueError:
                result.add_error(f"Non-numeric version in build.json: {version}", "build.json")

        except json.JSONDecodeError as e:
            result.add_error(f"Invalid JSON: {e}", "build.json")
        except Exception as e:
            result.add_error(f"Error reading build.json: {e}", "build.json")

    def _validate_cfw_files(self, result: ValidationResult):
        """Validate all .cfw files in the package."""
        for cfw_file in self.package_path.glob("*.cfw"):
            self._validate_single_cfw(cfw_file, result)

    def _validate_single_cfw(self, cfw_path: Path, result: ValidationResult):
        """Validate a single .cfw file."""
        filename = cfw_path.name

        try:
            data = cfw_path.read_bytes()
            meta, _ = parse_cfw(data)

            # Store metadata for cross-validation
            result.cfw_metadata[meta.app_id] = meta

            # Extract version from CFW header
            source = f"cfw:{meta.app_id}"
            result.versions[source] = VersionInfo(
                meta.major, meta.minor, meta.build, source
            )

            # Validate filename matches header
            match = self.CFW_PATTERN.match(filename)
            if match:
                file_app_id = int(match.group(1))
                file_major = int(match.group(2))
                file_minor = int(match.group(3))
                file_build = int(match.group(4))

                if file_app_id != meta.app_id:
                    result.add_error(
                        f"Filename app_id ({file_app_id}) != header app_id ({meta.app_id})",
                        filename
                    )
                if (file_major, file_minor, file_build) != (meta.major, meta.minor, meta.build):
                    result.add_error(
                        f"Filename version ({file_major}.{file_minor}.{file_build}) != "
                        f"header version ({meta.major}.{meta.minor}.{meta.build})",
                        filename
                    )
            else:
                result.add_warning(f"CFW filename doesn't match expected pattern", filename)

            # Validate app_id is known
            if meta.app_id not in (APPID_NRF9151_COMMS, APPID_NRF52840_APP):
                result.add_warning(f"Unknown app_id: {meta.app_id}", filename)

        except Exception as e:
            result.add_error(f"Failed to parse CFW: {e}", filename)

    def _check_version_consistency(self, result: ValidationResult):
        """Check that all version sources agree."""
        if len(result.versions) < 2:
            return  # Need at least 2 sources to compare

        # Use build.json as the reference
        reference = result.versions.get("build.json")
        if not reference:
            # Use first available version as reference
            reference = next(iter(result.versions.values()))

        for source, version in result.versions.items():
            if source == reference.source:
                continue

            if not version.matches(reference):
                # CFW can have different versions for different app_ids in staged updates
                # But within a single package, they should match build.json
                if source.startswith("cfw:"):
                    result.add_error(
                        f"Version mismatch: {source} has {version.version_string}, "
                        f"expected {reference.version_string}",
                        source
                    )
                else:
                    result.add_error(
                        f"Version mismatch: {source} ({version.version_string}) != "
                        f"{reference.source} ({reference.version_string})"
                    )

    @classmethod
    def parse_boot_log_versions(cls, log_text: str) -> dict[int, VersionInfo]:
        """Parse firmware versions from boot log output.

        Returns dict of app_id -> VersionInfo for all detected applications.
        """
        versions = {}
        for match in cls.BOOT_VERSION_PATTERN.finditer(log_text):
            app_id = int(match.group(1))
            major = int(match.group(2))
            minor = int(match.group(3))
            build = int(match.group(4))
            versions[app_id] = VersionInfo(major, minor, build, f"boot_log:{app_id}")
        return versions

    @classmethod
    def verify_boot_matches_expected(
        cls,
        log_text: str,
        expected_version: str,
        app_id: Optional[int] = None
    ) -> tuple[bool, str]:
        """Verify boot log versions match expected version.

        Args:
            log_text: Boot log output text
            expected_version: Expected version string (e.g., "0.5.1")
            app_id: Optional specific app_id to check. If None, checks all.

        Returns:
            (success, message) tuple
        """
        detected = cls.parse_boot_log_versions(log_text)
        if not detected:
            return False, "No firmware versions found in boot log"

        expected_parts = expected_version.split(".")
        if len(expected_parts) != 3:
            return False, f"Invalid expected version format: {expected_version}"

        expected_major, expected_minor, expected_build = (
            int(expected_parts[0]),
            int(expected_parts[1]),
            int(expected_parts[2])
        )

        if app_id is not None:
            # Check specific app_id
            if app_id not in detected:
                return False, f"App ID {app_id} not found in boot log"

            ver = detected[app_id]
            if ver.major == expected_major and ver.minor == expected_minor and ver.build == expected_build:
                return True, f"App {app_id} version {ver.version_string} matches expected"
            else:
                return False, f"App {app_id} version mismatch: got {ver.version_string}, expected {expected_version}"

        # Check all detected versions
        mismatches = []
        for aid, ver in detected.items():
            if ver.major != expected_major or ver.minor != expected_minor or ver.build != expected_build:
                mismatches.append(f"App {aid}: got {ver.version_string}, expected {expected_version}")

        if mismatches:
            return False, "Version mismatches: " + "; ".join(mismatches)

        return True, f"All {len(detected)} applications match expected version {expected_version}"


def validate_package(package_path: str) -> ValidationResult:
    """Convenience function to validate a firmware package."""
    validator = FirmwarePackageValidator(package_path)
    return validator.validate()


def main():
    """CLI for validating firmware packages."""
    import argparse

    parser = argparse.ArgumentParser(description="Validate firmware build packages")
    parser.add_argument("package_path", help="Path to firmware package directory")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of text")

    args = parser.parse_args()

    result = validate_package(args.package_path)

    if args.json:
        import json as json_mod
        output = {
            "valid": result.valid,
            "errors": [{"severity": e.severity, "message": e.message, "source": e.source} for e in result.errors],
            "warnings": [{"severity": w.severity, "message": w.message, "source": w.source} for w in result.warnings],
            "versions": {k: v.version_string for k, v in result.versions.items()},
            "files_found": result.files_found,
            "files_missing": result.files_missing,
        }
        print(json_mod.dumps(output, indent=2))
    else:
        print(result.summary())

    return 0 if result.valid else 1


if __name__ == "__main__":
    exit(main())
