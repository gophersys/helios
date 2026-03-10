#!/usr/bin/env python3
"""Build Worker — picks up QUEUED jobs, compiles firmware, uploads artifacts.

Architecture:
  - Worker polls Concord API for QUEUED BuildJobs
  - Claims a job by setting status to BUILDING
  - Fetches build script and overlays from API
  - Clones firmware repos (alpha_fw, alpha_mfg_fw) as subdirectories
  - Runs the build script with proper directory structure
  - Uploads artifacts (hex, cfw, logs) to MinIO via API
  - Updates job status to SUCCESS/FAILED

Directory structure created for each build:
  /tmp/builds/<job_id>/
    scripts/build.sh      # Fetched from API
    overlays/             # Fetched from API (tarball extracted)
    alpha_fw/             # Cloned from Bitbucket
    alpha_mfg_fw/         # Cloned from Bitbucket (if building mfg)

Environment:
  CONCORD_API_URL:  https://staging.concord.local
  CONCORD_API_KEY:  API key for auth
  WORKER_ID:        Unique worker identifier (default: hostname)
  POLL_INTERVAL:    Seconds between polls (default: 5)
  WORKSPACE_DIR:    Where to clone repos (default: /tmp/builds)
  SSH_KEY_PATH:     SSH key for git clone (default: /root/.ssh/id_rsa)

The build script receives env vars:
  BUILD_DIR:        Where to output artifacts
  VARIANT:          debug/release/mfg
  MTIB_REV:         1.1/1.2
  COMMIT_SHA:       Full commit hash
  BRANCH:           Branch name
"""

import json
import logging
import os
import shutil
import socket
import subprocess
import tarfile
import time
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("build-worker")

# Suppress SSL warnings for self-signed certs
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


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


class BuildWorker:
    """Firmware build worker that processes jobs from the Concord API.

    Each worker instance handles jobs for a specific NCS version.
    Multiple workers with different NCS versions can run in parallel.

    Repo configs are fetched from the API at startup instead of hardcoded.
    This allows adding new products via REPO_PRODUCT_MAP in types.py
    without changing the worker code.
    """

    def __init__(
        self,
        api_url: str,
        api_key: str,
        worker_id: str = None,
        poll_interval: int = 5,
        workspace_dir: str = "/tmp/builds",
        ssh_key_path: str = "/root/.ssh/id_rsa",
        ncs_version: str = None,
    ):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.worker_id = worker_id or socket.gethostname()
        self.poll_interval = poll_interval
        self.workspace_dir = Path(workspace_dir)
        self.ssh_key_path = ssh_key_path
        self.ncs_version = ncs_version  # Filter jobs by NCS version (None = all)

        self.workspace_dir.mkdir(parents=True, exist_ok=True)

        # Repo configs fetched from API (populated by _load_repo_configs)
        self._repo_configs: Dict[str, dict] = {}
        self._configs_loaded = False

    def _load_repo_configs(self) -> bool:
        """Fetch repo configs from API. Called once at startup and on cache miss."""
        result = self._api_get("/v2/ci/settings/repos")
        if not result or not result.get("data"):
            log.error("Failed to fetch repo configs from API")
            return False

        repos = result["data"]
        for repo in repos:
            slug = repo.get("id") or repo.get("name")
            if slug:
                self._repo_configs[slug] = {
                    "ssh_url": repo.get("sshUrl", ""),
                    "build_script": repo.get("buildScript", "scripts/build.sh"),
                    "board": repo.get("board", ""),
                    "targets": repo.get("targets", []),
                    "ncs_version": repo.get("ncsVersion", ""),
                }

        self._configs_loaded = True
        log.info("Loaded %d repo configs from API: %s", len(self._repo_configs), list(self._repo_configs.keys()))
        return True

    def _get_repo_config(self, product: str) -> Optional[dict]:
        """Get repo config for a product, fetching from API if needed."""
        if not self._configs_loaded:
            self._load_repo_configs()

        config = self._repo_configs.get(product)
        if not config:
            # Try refreshing configs in case new product was added
            self._load_repo_configs()
            config = self._repo_configs.get(product)

        return config

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"ApiKey {self.api_key}",
            "Content-Type": "application/json",
        }

    def _api_get(self, path: str) -> Optional[dict]:
        """GET request to API."""
        try:
            resp = requests.get(
                f"{self.api_url}{path}",
                headers=self._headers(),
                timeout=30,
                verify=False,
            )
            if resp.status_code >= 400:
                log.error("API GET %s: %d %s", path, resp.status_code, resp.text[:200])
                return None
            return resp.json()
        except Exception as e:
            log.error("API GET %s failed: %s", path, e)
            return None

    def _api_post(self, path: str, data: dict) -> Optional[dict]:
        """POST request to API."""
        try:
            resp = requests.post(
                f"{self.api_url}{path}",
                json=data,
                headers=self._headers(),
                timeout=30,
                verify=False,
            )
            if resp.status_code >= 400:
                log.error("API POST %s: %d %s", path, resp.status_code, resp.text[:200])
                return None
            return resp.json()
        except Exception as e:
            log.error("API POST %s failed: %s", path, e)
            return None

    def _api_patch(self, path: str, data: dict) -> Optional[dict]:
        """PATCH request to API."""
        try:
            resp = requests.patch(
                f"{self.api_url}{path}",
                json=data,
                headers=self._headers(),
                timeout=30,
                verify=False,
            )
            if resp.status_code >= 400:
                log.error("API PATCH %s: %d %s", path, resp.status_code, resp.text[:200])
                return None
            return resp.json()
        except Exception as e:
            log.error("API PATCH %s failed: %s", path, e)
            return None

    def _upload_file(self, path: str, file_path: Path, name: str) -> bool:
        """Upload a file as multipart form data."""
        try:
            with open(file_path, "rb") as f:
                resp = requests.post(
                    f"{self.api_url}{path}",
                    files={"file": (name, f)},
                    headers={"Authorization": f"ApiKey {self.api_key}"},
                    timeout=120,
                    verify=False,
                )
            if resp.status_code >= 400:
                log.error("Upload %s: %d %s", name, resp.status_code, resp.text[:200])
                return False
            return True
        except Exception as e:
            log.error("Upload %s failed: %s", name, e)
            return False

    def fetch_build_script(self, product: str) -> Optional[str]:
        """Fetch build script content from API."""
        # Map product names to script keys (alpha_fw -> alpha)
        script_key = product.lower().replace("_fw", "").replace("_mfg", "")
        result = self._api_get(f"/v2/ci/scripts/{script_key}")
        if not result or not result.get("data"):
            log.error("Failed to fetch build script for %s", product)
            return None
        return result["data"].get("content")

    def fetch_overlays(self, product: str, dest_dir: Path) -> bool:
        """Fetch and extract overlay files from API."""
        script_key = product.lower().replace("_fw", "").replace("_mfg", "")
        try:
            resp = requests.get(
                f"{self.api_url}/v2/ci/overlays/{script_key}",
                headers=self._headers(),
                timeout=30,
                verify=False,
            )
            if resp.status_code >= 400:
                log.warning("No overlays for %s: %d", product, resp.status_code)
                return False

            # Extract tarball
            dest_dir.mkdir(parents=True, exist_ok=True)
            tar_buffer = BytesIO(resp.content)
            with tarfile.open(fileobj=tar_buffer, mode="r:gz") as tar:
                tar.extractall(path=dest_dir)

            log.info("Extracted overlays to %s", dest_dir)
            return True

        except Exception as e:
            log.warning("Failed to fetch overlays for %s: %s", product, e)
            return False

    def fetch_queued_job(self) -> Optional[BuildJob]:
        """Fetch the next QUEUED build job matching this worker's NCS version."""
        # Build query params
        params = "status=QUEUED&limit=1"
        if self.ncs_version:
            params += f"&ncsVersion={self.ncs_version}"

        result = self._api_get(f"/v2/ci/builds?{params}")
        if not result or not result.get("data"):
            return None

        jobs = result["data"]
        if not jobs:
            return None

        j = jobs[0]
        return BuildJob(
            id=j["id"],
            product=j["product"],
            board=j["board"],
            target=j["target"],
            variant=j["variant"],
            mtib_rev=j["mtibRev"],
            branch=j["branch"],
            commit_sha=j["commitSha"] or "",
            status=j["status"],
            version_bump=j.get("versionBump", False),
            base_job_id=j.get("baseJobId"),
            matrix_label=j.get("matrixLabel"),
        )

    def claim_job(self, job_id: str) -> bool:
        """Claim a job by setting status to BUILDING."""
        result = self._api_patch(f"/v2/ci/builds/{job_id}", {
            "status": "BUILDING",
            "workerId": self.worker_id,
            "startedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })
        return result is not None and not result.get("errors")

    def update_job(self, job_id: str, status: str, error: str = None,
                   version_string: str = None, duration: int = None) -> bool:
        """Update job status."""
        data = {"status": status}
        if error:
            data["errorMessage"] = error[:2000]  # Truncate long errors
        if version_string:
            data["versionString"] = version_string
        if duration is not None:
            data["durationSeconds"] = duration
        if status in ("SUCCESS", "FAILED", "CANCELLED"):
            data["finishedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        result = self._api_patch(f"/v2/ci/builds/{job_id}", data)
        return result is not None

    def clone_repo(self, repo_slug: str, dest_dir: Path, commit_sha: str = None) -> bool:
        """Clone a repo to a specific directory.

        Args:
            repo_slug: The repo identifier (e.g., "alpha_fw")
            dest_dir: Where to clone the repo
            commit_sha: Optional commit to checkout
        """
        config = self._get_repo_config(repo_slug)
        if not config or not config.get("ssh_url"):
            log.error("No SSH URL configured for repo: %s", repo_slug)
            return False

        repo_url = config["ssh_url"]
        env = os.environ.copy()
        env["GIT_SSH_COMMAND"] = f"ssh -i {self.ssh_key_path} -o StrictHostKeyChecking=no -o BatchMode=yes"

        try:
            # Clone
            log.info("Cloning %s to %s...", repo_url, dest_dir.name)
            subprocess.run(
                ["git", "clone", "--depth", "50", repo_url, str(dest_dir)],
                env=env, check=True, capture_output=True, timeout=120,
            )

            # Checkout specific commit if provided
            if commit_sha:
                log.info("Checking out %s...", commit_sha[:8])
                subprocess.run(
                    ["git", "checkout", commit_sha],
                    cwd=dest_dir, check=True, capture_output=True, timeout=30,
                )

            # Initialize submodules
            log.info("Initializing submodules...")
            subprocess.run(
                ["git", "submodule", "update", "--init", "--recursive"],
                cwd=dest_dir, check=True, capture_output=True, timeout=300,
            )

            return True

        except subprocess.CalledProcessError as e:
            log.error("Git failed: %s", e.stderr.decode() if e.stderr else str(e))
            return False
        except Exception as e:
            log.error("Clone failed: %s", e)
            return False

    def _get_base_build_version(self, base_job_id: str) -> Optional[int]:
        """Fetch the build number from a completed base build."""
        if not base_job_id:
            return None

        result = self._api_get(f"/v2/ci/builds/{base_job_id}")
        if not result or not result.get("data"):
            return None

        version_string = result["data"].get("versionString", "")
        if not version_string:
            return None

        # Parse version string like "0.8.3" or "v0.8.3" -> extract build number (3)
        import re
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
        env.update({
            "BUILD_DIR": str(output_dir),
            "VARIANT": job.variant if job.variant != "mfg" else "",
            "MTIB_REV": job.mtib_rev,
            "COMMIT_SHA": job.commit_sha or "",
            "BRANCH": job.branch,
            "TARGET": job.target,
            "BOARD": job.board,
            # Zephyr/NCS paths (assuming ncs-build container)
            "ZEPHYR_BASE": os.environ.get("ZEPHYR_BASE", "/workdir/zephyr"),
            "ZEPHYR_TOOLCHAIN_VARIANT": "zephyr",
            "ZEPHYR_SDK_INSTALL_DIR": os.environ.get("ZEPHYR_SDK_INSTALL_DIR", "/workdir/zephyr-sdk"),
        })

        # Handle version bumping for N+1 builds (same code, incremented version)
        if job.version_bump and job.base_job_id:
            base_version = self._get_base_build_version(job.base_job_id)
            if base_version is not None:
                bumped_version = base_version + 1
                env["VERSION_BUILD_OVERRIDE"] = str(bumped_version)
                log.info("Version bump: %d -> %d (base job: %s)", base_version, bumped_version, job.base_job_id[:8])
            else:
                log.warning("Could not get base build version for bump, using default")

        # Build command: bash scripts/build.sh <target> --mtib-rev <rev> [--variant <variant>]
        cmd = ["bash", str(script_path), build_target, "--mtib-rev", job.mtib_rev, "-b", job.board]
        if job.variant and job.variant not in ("mfg", "release"):
            cmd.extend(["--variant", job.variant])

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
                            self._stream_log_chunk(job.id, "".join(log_buffer))
                            log_buffer = []

                # Flush remaining buffer
                if log_buffer:
                    self._stream_log_chunk(job.id, "".join(log_buffer))

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

    def _stream_log_chunk(self, job_id: str, chunk: str) -> None:
        """Stream a log chunk to the API for WebSocket broadcast."""
        try:
            # Fire and forget - don't block build on API calls
            requests.post(
                f"{self.api_url}/v2/ci/builds/{job_id}/log",
                json={"chunk": chunk},
                headers=self._headers(),
                timeout=5,
                verify=False,
            )
        except Exception:
            pass  # Don't fail build if streaming fails

    def collect_artifacts(self, output_dir: Path) -> List[Path]:
        """Find all build artifacts in the output directory."""
        artifacts = []
        for pattern in ["*.hex", "*.bin", "*.cfw", "*.elf", "*.map"]:
            artifacts.extend(output_dir.glob(f"**/{pattern}"))
        return artifacts

    def upload_artifacts(self, job_id: str, artifacts: List[Path]) -> int:
        """Upload all artifacts for a job. Returns count of successful uploads."""
        count = 0
        for artifact in artifacts:
            log.info("Uploading %s...", artifact.name)
            if self._upload_file(f"/v2/ci/builds/{job_id}/artifacts", artifact, artifact.name):
                count += 1
        return count

    def process_job(self, job: BuildJob) -> bool:
        """Process a single build job.

        Sets up workspace with:
            work_dir/
                scripts/build.sh   # Fetched from API
                overlays/          # Fetched from API
                alpha_fw/          # Cloned from Bitbucket
                alpha_mfg_fw/      # Cloned from Bitbucket
                artifacts/         # Build outputs
        """
        log.info("=" * 60)
        log.info("Processing job %s: %s/%s (%s)", job.id[:8], job.product, job.variant, job.branch)

        start_time = time.time()
        work_dir = self.workspace_dir / job.id
        output_dir = work_dir / "artifacts"

        try:
            # Clean workspace
            if work_dir.exists():
                shutil.rmtree(work_dir)
            work_dir.mkdir(parents=True)
            output_dir.mkdir(parents=True)

            # Determine product base (alpha_fw -> alpha)
            product_base = job.product.lower().replace("_fw", "").replace("_mfg", "")  # "alpha"

            # 1. Fetch build script from API
            log.info("Fetching build script...")
            script_content = self.fetch_build_script(job.product)
            if not script_content:
                self.update_job(job.id, "FAILED", f"Failed to fetch build script for {job.product}")
                return False

            scripts_dir = work_dir / "scripts"
            scripts_dir.mkdir(parents=True)
            script_file = scripts_dir / "build.sh"
            script_file.write_text(script_content)
            script_file.chmod(0o755)

            # 2. Fetch overlays from API
            log.info("Fetching overlays...")
            overlays_dir = work_dir / "overlays"
            self.fetch_overlays(job.product, overlays_dir)  # Optional, don't fail if missing

            # 3. Clone production firmware repo (e.g., alpha_fw)
            main_fw = f"{product_base}_fw"
            main_fw_dir = work_dir / main_fw
            log.info("Cloning %s...", main_fw)
            if not self.clone_repo(main_fw, main_fw_dir, job.commit_sha):
                self.update_job(job.id, "FAILED", f"Failed to clone {main_fw}")
                return False

            # 4. Clone manufacturing firmware repo (e.g., alpha_mfg_fw)
            mfg_fw = f"{product_base}_mfg_fw"
            mfg_fw_dir = work_dir / mfg_fw
            log.info("Cloning %s...", mfg_fw)
            # For mfg builds, use same commit; for production builds, just get latest
            mfg_commit = job.commit_sha if "_mfg" in job.product else None
            if not self.clone_repo(mfg_fw, mfg_fw_dir, mfg_commit):
                log.warning("Failed to clone %s - mfg builds may fail", mfg_fw)
                # Don't fail here, mfg repo might not exist for all products

            # 5. Run build (writes log to output_dir/build.log during execution)
            log_file = output_dir / "build.log"
            success, log_output = self.run_build(job, work_dir, output_dir)
            duration = int(time.time() - start_time)

            if not success:
                log.error("Build failed for %s", job.id[:8])
                # Store truncated error in DB, full log goes to MinIO as artifact
                error_summary = log_output[-4000:] if len(log_output) > 4000 else log_output
                self.update_job(job.id, "FAILED", error_summary, duration=duration)
                # Upload full log as artifact
                self._upload_file(f"/v2/ci/builds/{job.id}/artifacts", log_file, "build.log")
                return False

            # 6. Collect and upload artifacts
            # Artifacts are in work_dir/artifacts/<fw_type>/<board>/*.hex
            artifacts = self.collect_artifacts(output_dir)
            # Also check the build directories in the firmware repos
            for fw_dir in [main_fw_dir, mfg_fw_dir]:
                if fw_dir.exists():
                    artifacts.extend(self.collect_artifacts(fw_dir))
            artifacts.append(log_file)  # Include build log

            artifact_count = self.upload_artifacts(job.id, artifacts)
            log.info("Uploaded %d artifacts", artifact_count)

            # Extract version from output (look for pattern like "v0.8.1")
            version_string = None
            import re
            match = re.search(r"v?(\d+\.\d+\.\d+)", log_output)
            if match:
                version_string = match.group(0)

            self.update_job(job.id, "SUCCESS", version_string=version_string, duration=duration)
            log.info("Build %s completed in %ds", job.id[:8], duration)
            return True

        except Exception as e:
            log.exception("Unexpected error processing job %s", job.id[:8])
            self.update_job(job.id, "FAILED", str(e))
            return False

        finally:
            # Cleanup workspace
            try:
                if work_dir.exists():
                    shutil.rmtree(work_dir)
            except Exception:
                pass

    def run(self):
        """Main worker loop."""
        ncs_info = f", ncs={self.ncs_version}" if self.ncs_version else ", ncs=all"
        log.info("Build worker starting (id=%s, poll=%ds%s)", self.worker_id, self.poll_interval, ncs_info)

        while True:
            try:
                # Fetch next job
                job = self.fetch_queued_job()

                if job:
                    # Try to claim it
                    if self.claim_job(job.id):
                        self.process_job(job)
                    else:
                        log.debug("Failed to claim job %s (maybe taken by another worker)", job.id[:8])
                else:
                    log.debug("No jobs in queue")

            except Exception as e:
                log.exception("Worker loop error: %s", e)

            time.sleep(self.poll_interval)


def main():
    worker = BuildWorker(
        api_url=os.environ.get("CONCORD_API_URL", "https://staging.concord.local"),
        api_key=os.environ.get("CONCORD_API_KEY", ""),
        worker_id=os.environ.get("WORKER_ID"),
        poll_interval=int(os.environ.get("POLL_INTERVAL", "5")),
        workspace_dir=os.environ.get("WORKSPACE_DIR", "/tmp/builds"),
        ssh_key_path=os.environ.get("SSH_KEY_PATH", "/root/.ssh/id_rsa"),
        ncs_version=os.environ.get("NCS_VERSION"),  # Filter for specific NCS version (e.g., "2.7.0")
    )
    worker.run()


if __name__ == "__main__":
    main()
