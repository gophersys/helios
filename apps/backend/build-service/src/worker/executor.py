"""Build execution, artifact collection, and verification."""

import json
import logging
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.clients.concord import ConcordClient
from src.worker.manifest import generate_build_manifest, classify_artifact

# Firmware validation - try to import, fallback if not available in container
try:
    from corekinect.firmware.validator import FirmwarePackageValidator, ValidationResult
    HAS_VALIDATOR = True
except ImportError:
    HAS_VALIDATOR = False
    ValidationResult = None  # type: ignore

log = logging.getLogger("build-service")


@dataclass
class BuildJob:
    """A build job from the API."""
    id: str
    product: str
    board: str
    target: str
    variant: str
    branch: str
    commit_sha: str
    status: str
    version_bump: bool = False
    base_job_id: str = None
    matrix_label: str = None
    version_override: str = None  # Explicit version override (e.g., "0.5.0")
    config_flags: dict = None  # Extra build flags (e.g., {"forceLog": true})
    product_id: str = None  # DB product ID for fetching buildConfig
    recipe_version_id: str = None  # Pinned recipe version for reproducibility


def _extract_version_override(job_data: dict) -> Optional[str]:
    """Extract version override from job data (configFlags or direct field)."""
    config_flags = job_data.get("configFlags") or {}
    if isinstance(config_flags, dict) and config_flags.get("versionOverride"):
        return config_flags["versionOverride"]
    return job_data.get("versionOverride") or job_data.get("firmwareVersion")


class BuildExecutor:
    """Executes firmware builds and handles artifacts."""

    def __init__(self, api_client: ConcordClient):
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

    def prepare_build_env(self, job: BuildJob, work_dir: Path, output_dir: Path,
                          docker_mode: bool = False) -> Tuple[Dict[str, str], List[str], str]:
        """Prepare environment variables and build command.

        Returns (env_dict, cmd_list, build_target) for use by either
        local subprocess or DockerBuildRunner.
        """
        script_path = work_dir / "scripts" / "build.sh"
        if not script_path.exists():
            raise FileNotFoundError(f"Build script not found: {script_path}")

        build_target = job.target if job.target in ("app", "mfg") else "app"

        # Build environment
        env: Dict[str, str] = {}

        # Repo directory paths — in Docker mode these are container-internal paths
        if docker_mode:
            # Inside the builder container, workspace is at /workspace/{job_id}
            container_work = f"/workspace/{job.id}"
            primary_slug = job.config_flags.get("_primary_slug", f"{job.product}_fw") if job.config_flags else f"{job.product}_fw"
            env["BUILD_DIR"] = f"{container_work}/artifacts"
            env["OUTPUT_DIR"] = f"{container_work}/artifacts"
            env["REPO_DIR"] = f"{container_work}/{primary_slug}"
        else:
            # Local mode — use real filesystem paths
            product_base = job.product.lower().replace("_fw", "").replace("_mfg", "")
            if job.target == "mfg":
                repo_dir = str(work_dir / f"{product_base}_mfg_fw")
            else:
                repo_dir = str(work_dir / f"{product_base}_fw")
            env["BUILD_DIR"] = str(output_dir)
            env["OUTPUT_DIR"] = str(output_dir)
            env["REPO_DIR"] = repo_dir

        # Legacy env vars (backward compat with existing build scripts)
        env.update({
            "VARIANT": job.variant if job.variant != "mfg" else "",
            "COMMIT_SHA": job.commit_sha or "",
            "BRANCH": job.branch,
            "TARGET": build_target,
            "FIRMWARE_TYPE": build_target,
            "BOARD": job.board,
        })

        # Concord SDK env vars (used by concord-build.sh)
        config_flags = job.config_flags or {}
        targets_json = config_flags.get("_targets_json", "[]")
        env.update({
            "CONCORD_BOARD": job.board,
            "CONCORD_VARIANT": job.variant or "release",
            "CONCORD_FW_TYPE": build_target,
            "CONCORD_CONFIG_LOG": "y" if config_flags.get("config_log", True) else "n",
            "CONCORD_PRODUCES_HEX": "true" if config_flags.get("produces_hex", True) else "false",
            "CONCORD_PRODUCES_CFW": "true" if config_flags.get("produces_cfw", False) else "false",
            "CONCORD_COMMIT_SHA": job.commit_sha or "",
            "CONCORD_BRANCH": job.branch,
            "CONCORD_MATRIX_LABEL": job.matrix_label or "",
            "CONCORD_PRODUCT": job.product,
            "CONCORD_TARGETS": targets_json,
        })
        if docker_mode:
            env["CONCORD_REPO_DIR"] = env.get("REPO_DIR", "")
            env["CONCORD_BUILD_DIR"] = f"{env.get('REPO_DIR', '')}/build"
            env["CONCORD_OUTPUT_DIR"] = env.get("OUTPUT_DIR", "")
        else:
            env["CONCORD_REPO_DIR"] = env.get("REPO_DIR", "")
            env["CONCORD_BUILD_DIR"] = f"{env.get('REPO_DIR', '')}/build"
            env["CONCORD_OUTPUT_DIR"] = env.get("OUTPUT_DIR", "")

        if not docker_mode:
            # Local mode needs Zephyr paths from the host environment
            env["ZEPHYR_BASE"] = os.environ.get("ZEPHYR_BASE", "/workdir/zephyr")
            env["ZEPHYR_TOOLCHAIN_VARIANT"] = "zephyr"
            env["ZEPHYR_SDK_INSTALL_DIR"] = os.environ.get("ZEPHYR_SDK_INSTALL_DIR", "/workdir/zephyr-sdk")

        # Version override — set BOTH legacy and SDK env vars
        _version_override = None
        if job.version_override:
            parts = job.version_override.strip().split(".")
            if len(parts) >= 3:
                try:
                    _version_override = str(int(parts[2]))
                    log.info("Version override: %s → BUILD_NUM=%s", job.version_override, parts[2])
                except ValueError:
                    pass
        elif job.version_bump and job.base_job_id:
            base_version = self.get_base_build_version(job.base_job_id)
            if base_version is not None:
                _version_override = str(base_version + 1)
                log.info("Version bump: %d → %d (base: %s)", base_version, base_version + 1, job.base_job_id[:8])

        if _version_override:
            env["VERSION_BUILD_OVERRIDE"] = _version_override
            env["CONCORD_VERSION_OVERRIDE"] = _version_override

        # Build command
        if docker_mode:
            script = f"/workspace/{job.id}/scripts/build.sh"
        else:
            script = str(script_path)
        cmd = ["bash", script, build_target, "-b", job.board]
        if job.variant and job.variant not in ("mfg", "release"):
            cmd.extend(["--variant", job.variant])

        config_flags = getattr(job, "config_flags", None) or {}
        if isinstance(config_flags, dict) and config_flags.get("forceLog"):
            cmd.append("--force-log")

        return env, cmd, build_target

    def run_build(self, job: BuildJob, work_dir: Path, output_dir: Path,
                  docker_runner=None, builder_image: str = None) -> Tuple[bool, str]:
        """Run the build script with real-time log streaming.

        If docker_runner is provided, delegates to a dynamically-spawned container.
        Otherwise runs the build locally via subprocess (legacy mode).
        """
        try:
            docker_mode = docker_runner is not None and builder_image is not None
            env, cmd, build_target = self.prepare_build_env(job, work_dir, output_dir, docker_mode)
        except FileNotFoundError as e:
            return False, str(e)

        # Log streaming callback
        def _stream_log(chunk: str):
            self.api_client.stream_log_chunk(job.id, chunk)

        # ── Docker mode: delegate to dynamic container ──
        if docker_mode:
            log.info("Docker build: image=%s cmd=%s", builder_image, " ".join(cmd))
            return docker_runner.run_build(
                image=builder_image,
                job_id=job.id,
                work_dir=work_dir,
                output_dir=output_dir,
                env=env,
                cmd=cmd,
                log_callback=_stream_log,
            )

        # ── Local mode: subprocess (legacy) ──
        script_path = work_dir / "scripts" / "build.sh"

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

        # Build command: bash scripts/build.sh <target> [--variant <variant>] [--force-log]
        cmd = ["bash", str(script_path), build_target, "-b", job.board]
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

    def write_manifest(
        self,
        build_config: Dict[str, Any],
        output_dir: Path,
        product: str,
        board: str,
        version: str,
        variant: str,
        commit_sha: str,
        branch: str,
        key_dir: Optional[Path] = None,
    ) -> Optional[Path]:
        """Generate and write build.json manifest to output directory.

        Returns the path to the written manifest, or None on failure.
        """
        try:
            manifest = generate_build_manifest(
                build_config=build_config,
                output_dir=output_dir,
                product=product,
                board=board,
                version=version,
                variant=variant,
                commit_sha=commit_sha,
                branch=branch,
                key_dir=key_dir,
            )
            manifest_path = output_dir / "build.json"
            manifest_path.write_text(json.dumps(manifest, indent=2))
            log.info("Wrote build.json manifest to %s", manifest_path)
            return manifest_path
        except Exception as e:
            log.error("Failed to generate build manifest: %s", e)
            return None

    def upload_artifacts(self, job_id: str, artifacts: List[Path],
                         build_config: Optional[Dict[str, Any]] = None) -> int:
        """Upload all artifacts for a job with structured metadata.

        Uses buildConfig.targets to map artifacts to roles/processors.
        Returns count of successful uploads.
        """
        # Build appId -> target metadata lookup from buildConfig
        target_lookup: Dict[int, Dict[str, str]] = {}
        if build_config:
            raw_targets = build_config.get("targets", [])
            # Normalize dict format {"app": {...}} -> list
            if isinstance(raw_targets, dict):
                target_list = list(raw_targets.values())
            else:
                target_list = raw_targets
            for t in target_list:
                app_id = t.get("appId")
                if app_id:
                    target_lookup[app_id] = {
                        "role": t.get("role", ""),
                        "processor": t.get("processor") or t.get("soc", ""),
                    }

        count = 0
        for artifact in artifacts:
            metadata = {}

            # Classify by filename
            classification = classify_artifact(artifact.name)
            if classification:
                artifact_type, app_id = classification
                metadata["artifactType"] = artifact_type  # "plaintextHex" or "encryptedCfw"
                # Look up role/processor from buildConfig
                target_meta = target_lookup.get(app_id, {})
                if target_meta:
                    metadata["role"] = target_meta["role"]
                    metadata["processor"] = target_meta["processor"]
            elif artifact.name == "build.json":
                metadata = {"role": "manifest", "artifactType": "manifest"}
            elif artifact.name == "build.log":
                metadata = {"role": "log", "artifactType": "log"}

            log.info("Uploading %s (metadata=%s)...", artifact.name, metadata or "none")
            if self.api_client.upload_file(
                f"/v2/builds/{job_id}/artifacts", artifact, artifact.name, metadata=metadata
            ):
                count += 1
        return count
