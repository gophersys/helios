"""Build execution, artifact collection, and verification."""

import logging
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from src.api_client import ConcordApiClient

# Firmware validation - try to import, fallback if not available in container
try:
    from corekinect.firmware.validator import FirmwarePackageValidator, ValidationResult
    HAS_VALIDATOR = True
except ImportError:
    HAS_VALIDATOR = False
    ValidationResult = None  # type: ignore

log = logging.getLogger("build-worker")


@dataclass
class BuildJob:
    """A build job from the API."""
    id: str
    product: str
    board: str
    target: str
    variant: str
    mtib_rev: str
    branch: str
    commit_sha: str
    status: str
    version_bump: bool = False
    base_job_id: str = None
    matrix_label: str = None
    version_override: str = None  # Explicit version override (e.g., "0.5.0")
    config_flags: dict = None  # Extra build flags (e.g., {"forceLog": true})


def _extract_version_override(job_data: dict) -> Optional[str]:
    """Extract version override from job data (configFlags or direct field)."""
    config_flags = job_data.get("configFlags") or {}
    if isinstance(config_flags, dict) and config_flags.get("versionOverride"):
        return config_flags["versionOverride"]
    return job_data.get("versionOverride") or job_data.get("firmwareVersion")


class BuildExecutor:
    """Executes firmware builds and handles artifacts."""

    def __init__(self, api_client: ConcordApiClient):
        self.api_client = api_client

    def get_base_build_version(self, base_job_id: str) -> Optional[int]:
        """Fetch the build number from a completed base build."""
        if not base_job_id:
            return None

        result = self.api_client.api_get(f"/v2/builds/{base_job_id}")
        if not result or not result.get("data"):
            return None

        version_string = result["data"].get("versionString", "")
        if not version_string:
            return None

        # Parse version string like "0.8.3" or "v0.8.3" -> extract build number (3)
        match = re.search(r"(\d+)\.(\d+)\.(\d+)", version_string)
        if match:
            return int(match.group(3))  # build number
        return None

    def run_build(self, job: BuildJob, work_dir: Path, output_dir: Path) -> Tuple[bool, str]:
        """Run the build script with real-time log streaming.

        Streams output line-by-line to:
        1. Local log file (build.log)
        2. API endpoint for WebSocket broadcast

        The workspace structure is:
            work_dir/
                scripts/build.sh   # Build script
                overlays/          # DTS overlays
                alpha_fw/          # Production firmware repo
                alpha_mfg_fw/      # Manufacturing firmware repo (optional)
        """
        script_path = work_dir / "scripts" / "build.sh"

        if not script_path.exists():
            return False, f"Build script not found: {script_path}"

        # Determine build target based on product name
        # alpha_fw -> app, alpha_mfg_fw -> mfg
        if "_mfg_" in job.product or "_mfg" in job.product:
            build_target = "mfg"
        else:
            build_target = "app"

        # Prepare environment for build script
        env = os.environ.copy()

        # Determine firmware repo directory (REPO_DIR enables CI_MODE in build.sh)
        if "_mfg_" in job.product or "_mfg" in job.product:
            product_base = job.product.replace("_mfg_fw", "").replace("_mfg", "")
            repo_dir = str(work_dir / f"{product_base}_mfg_fw")
        else:
            repo_dir = str(work_dir / job.product)

        env.update({
            "BUILD_DIR": str(output_dir),
            "OUTPUT_DIR": str(output_dir),
            "REPO_DIR": repo_dir,
            "VARIANT": job.variant if job.variant != "mfg" else "",
            "MTIB_REV": job.mtib_rev,
            "COMMIT_SHA": job.commit_sha or "",
            "BRANCH": job.branch,
            "TARGET": build_target,
            "FIRMWARE_TYPE": build_target,
            "BOARD": job.board,
            # Zephyr/NCS paths (assuming ncs-build container)
            "ZEPHYR_BASE": os.environ.get("ZEPHYR_BASE", "/workdir/zephyr"),
            "ZEPHYR_TOOLCHAIN_VARIANT": "zephyr",
            "ZEPHYR_SDK_INSTALL_DIR": os.environ.get("ZEPHYR_SDK_INSTALL_DIR", "/workdir/zephyr-sdk"),
        })

        # Handle explicit version override (e.g., "0.5.0" -> BUILD_NUM=0)
        if job.version_override:
            # Parse version string to extract build number (last component)
            parts = job.version_override.strip().split(".")
            if len(parts) >= 3:
                try:
                    build_num = int(parts[2])
                    env["VERSION_BUILD_OVERRIDE"] = str(build_num)
                    log.info("Version override: %s -> BUILD_NUM=%d", job.version_override, build_num)
                except ValueError:
                    log.warning("Could not parse build number from version_override: %s", job.version_override)

        # Handle version bumping for N+1 builds (same code, incremented version)
        elif job.version_bump and job.base_job_id:
            base_version = self.get_base_build_version(job.base_job_id)
            if base_version is not None:
                bumped_version = base_version + 1
                env["VERSION_BUILD_OVERRIDE"] = str(bumped_version)
                log.info("Version bump: %d -> %d (base job: %s)", base_version, bumped_version, job.base_job_id[:8])
            else:
                log.warning("Could not get base build version for bump, using default")

        # Build command: bash scripts/build.sh <target> --mtib-rev <rev> [--variant <variant>] [--force-log]
        cmd = ["bash", str(script_path), build_target, "--mtib-rev", job.mtib_rev, "-b", job.board]
        if job.variant and job.variant not in ("mfg", "release"):
            cmd.extend(["--variant", job.variant])

        # Pass --force-log if configFlags.forceLog is set (release + UART logging)
        config_flags = getattr(job, "config_flags", None) or {}
        if isinstance(config_flags, dict) and config_flags.get("forceLog"):
            cmd.append("--force-log")
            log.info("Force-log mode: release CFW flags with UART logging")

        log_file = output_dir / "build.log"
        log_lines: List[str] = []
        log_buffer: List[str] = []  # Buffer for batching API calls

        try:
            log.info("Running: %s", " ".join(cmd))

            # Use Popen for real-time streaming
            process = subprocess.Popen(
                cmd,
                cwd=work_dir,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Merge stderr into stdout
                text=True,
                bufsize=1,  # Line buffered
            )

            with open(log_file, "w") as f:
                while True:
                    line = process.stdout.readline()
                    if not line and process.poll() is not None:
                        break

                    if line:
                        # Write to local file
                        f.write(line)
                        f.flush()

                        # Collect for full output
                        log_lines.append(line)

                        # Buffer for API streaming (batch every 10 lines or 1KB)
                        log_buffer.append(line)
                        buffer_size = sum(len(l) for l in log_buffer)
                        if len(log_buffer) >= 10 or buffer_size >= 1024:
                            self.api_client.stream_log_chunk(job.id, "".join(log_buffer))
                            log_buffer = []

                # Flush remaining buffer
                if log_buffer:
                    self.api_client.stream_log_chunk(job.id, "".join(log_buffer))

            return_code = process.wait(timeout=1800)
            output = "".join(log_lines)

            if return_code != 0:
                return False, output

            return True, output

        except subprocess.TimeoutExpired:
            process.kill()
            return False, "".join(log_lines) + "\n\nBuild timed out after 30 minutes"
        except Exception as e:
            return False, "".join(log_lines) + f"\n\nBuild failed: {e}"

    def collect_artifacts(self, output_dir: Path) -> List[Path]:
        """Find final build artifacts only — no intermediates.

        Final artifacts:
          - {appId}.{version}.hex (e.g. 109.0.8.1.hex, 108.0.8.1.hex)
          - {appId}.{version}.cfw (e.g. 109.0.8.1.cfw, 108.0.8.1.cfw)
          - build.json (build metadata)
          - build.log (added separately by caller)

        Hex and CFW files share the same naming scheme: {appId}.{major}.{minor}.{build}
        """
        artifacts = []
        # CFW files
        artifacts.extend(output_dir.glob("**/*.cfw"))
        # Versioned hex files (109.0.8.1.hex, 108.0.8.1.hex)
        for f in output_dir.glob("**/*.hex"):
            # Only include hex files named with appId prefix (digits.digits.digits.digits.hex)
            name = f.name
            if name[0].isdigit() and name.endswith(".hex"):
                artifacts.append(f)
        # Build metadata
        artifacts.extend(output_dir.glob("**/build.json"))
        return artifacts

    def verify_artifacts(self, output_dir: Path, expected_version: Optional[str] = None) -> Tuple[bool, str]:
        """Verify firmware artifacts for consistency and correctness.

        Checks:
        1. Required files present (hex, build.json)
        2. Version consistency across build.json and CFW headers
        3. CFW header integrity
        4. Version matches expected (if provided)

        Returns (success, message) tuple.
        """
        if not HAS_VALIDATOR:
            log.warning("Firmware validator not available, skipping verification")
            return True, "Validator not available"

        # Find artifact directory (may be nested)
        artifact_dirs = list(output_dir.glob("**/build.json"))
        if not artifact_dirs:
            # No build.json, check if we have hex files directly
            hex_files = list(output_dir.glob("**/*.hex"))
            if not hex_files:
                return False, "No artifacts found (no build.json or hex files)"
            log.warning("No build.json found, skipping package validation")
            return True, "No build.json, skipping validation"

        # Use the directory containing build.json
        package_dir = artifact_dirs[0].parent

        try:
            validator = FirmwarePackageValidator(str(package_dir))
            result = validator.validate()

            # Log the validation result
            if result.valid:
                log.info("Firmware validation PASSED: %s", result.summary().split('\n')[0])
            else:
                log.error("Firmware validation FAILED:\n%s", result.summary())

            # If expected version provided, verify it matches
            if expected_version and result.valid:
                build_version = result.versions.get("build.json")
                if build_version and build_version.version_string != expected_version:
                    return False, f"Version mismatch: built {build_version.version_string}, expected {expected_version}"

            return result.valid, result.summary()

        except Exception as e:
            log.exception("Verification error: %s", e)
            return False, f"Verification error: {e}"

    def upload_artifacts(self, job_id: str, artifacts: List[Path]) -> int:
        """Upload all artifacts for a job. Returns count of successful uploads."""
        count = 0
        for artifact in artifacts:
            log.info("Uploading %s...", artifact.name)
            if self.api_client.upload_file(f"/v2/builds/{job_id}/artifacts", artifact, artifact.name):
                count += 1
        return count
