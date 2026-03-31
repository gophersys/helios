"""Build worker — poll loop and job orchestration."""

import logging
import re
import shutil
import time
from pathlib import Path
from typing import Dict, Optional

from src.clients.concord import ConcordClient
from src.config import BuildServiceConfig
from src.worker.executor import BuildExecutor, BuildJob, _extract_version_override
from src.worker.git_ops import GitOps

log = logging.getLogger("build-service")


class BuildWorkerLoop:
    """Firmware build worker that processes jobs from the Concord API.

    Each worker instance handles jobs for a specific NCS version.
    Multiple workers with different NCS versions can run in parallel.

    Repo configs are fetched from the API at startup from the Product model
    in DB. New products are discovered automatically.
    """

    def __init__(self, config: BuildServiceConfig, client: ConcordClient,
                 shutdown_event=None):
        self.config = config
        self.client = client
        self.shutdown_event = shutdown_event
        self.workspace_dir = Path(config.workspace_dir)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

        self.git_ops = GitOps(config.ssh_key_path, self.client)
        self.builder = BuildExecutor(self.client)

        # NCS version cache: product -> ncs_version (learned from devcontainer)
        self._product_ncs_cache: Dict[str, str] = {}

        # Register worker in local DB
        self._register_worker()

    def _register_worker(self):
        """Register or update this worker in the local database."""
        try:
            from src.db.client import get_db
            db = get_db()
            db.worker.upsert(
                where={"id": self.config.worker_id},
                data={
                    "create": {
                        "id": self.config.worker_id,
                        "ncsVersion": self.config.ncs_version or "",
                        "status": "ONLINE",
                        "lastHeartbeat": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    },
                    "update": {
                        "ncsVersion": self.config.ncs_version or "",
                        "status": "ONLINE",
                        "lastHeartbeat": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    },
                },
            )
            log.info("Worker registered in local DB: %s", self.config.worker_id)
        except Exception as e:
            log.debug("Local DB worker registration skipped: %s", e)

    def _update_worker_heartbeat(self):
        """Update worker heartbeat in local database."""
        try:
            from src.db.client import get_db
            db = get_db()
            db.worker.update(
                where={"id": self.config.worker_id},
                data={"lastHeartbeat": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
            )
        except Exception:
            pass  # Local tracking is best-effort

    def _update_local_job(self, external_job_id: str, **kwargs):
        """Update local job tracking. Fire-and-forget — don't fail the build if local DB is down."""
        try:
            from src.db.client import get_db
            db = get_db()
            db.localjob.update(
                where={"externalJobId": external_job_id},
                data=kwargs,
            )
        except Exception:
            pass  # Local tracking is best-effort

    def fetch_queued_job(self) -> Optional[BuildJob]:
        """Fetch the next QUEUED build job matching this worker's NCS version."""
        result = self.client.api_get("/v2/builds?status=QUEUED&limit=20")
        if not result or not result.get("data"):
            return None

        # API returns { "data": { "data": [...], "total": N } } envelope
        inner = result["data"]
        jobs = inner.get("data", inner) if isinstance(inner, dict) else inner
        if not jobs:
            return None

        for j in jobs:
            product = j["product"]
            # Skip products we already know need a different NCS version
            if self.config.ncs_version and product in self._product_ncs_cache:
                cached_ncs = self._product_ncs_cache[product]
                if cached_ncs != self.config.ncs_version:
                    continue

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
                version_override=_extract_version_override(j),
                config_flags=j.get("configFlags") or {},
                product_id=j.get("productId"),
            )

        return None  # All queued jobs are for incompatible NCS versions

    def claim_job(self, job_id: str) -> bool:
        """Claim a job by setting status to CLONING (first phase of processing)."""
        result = self.client.api_patch(f"/v2/builds/{job_id}", {
            "status": "CLONING",
            "workerId": self.config.worker_id,
            "startedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })
        if result is not None and not result.get("errors"):
            # Track in local DB
            try:
                from src.db.client import get_db
                db = get_db()
                db.localjob.create(
                    data={
                        "externalJobId": job_id,
                        "workerId": self.config.worker_id,
                        "status": "CLONING",
                        "step": "clone",
                        "startedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    },
                )
                db.worker.update(
                    where={"id": self.config.worker_id},
                    data={"currentJobId": job_id},
                )
            except Exception:
                pass  # Local tracking is best-effort
            return True
        return False

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

        result = self.client.api_patch(f"/v2/builds/{job_id}", data)

        # Update local DB tracking
        local_data = {"status": status}
        if status in ("SUCCESS", "FAILED", "CANCELLED"):
            local_data["finishedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            # Clear current job on worker
            try:
                from src.db.client import get_db
                db = get_db()
                db.worker.update(
                    where={"id": self.config.worker_id},
                    data={"currentJobId": None},
                )
            except Exception:
                pass
        self._update_local_job(job_id, **local_data)

        return result is not None

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
            self._update_local_job(job.id, step="clone")
            script_content = self.git_ops.fetch_build_script(job.product)
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
            self.git_ops.fetch_overlays(job.product, overlays_dir)  # Optional, don't fail if missing

            # 3. Clone production firmware repo (e.g., alpha_fw)
            # Status is already CLONING from claim_job()
            main_fw = f"{product_base}_fw"
            main_fw_dir = work_dir / main_fw
            # For mfg target builds, the commitSha belongs to the mfg repo — clone main fw at latest
            main_commit = job.commit_sha if job.target != "mfg" else None
            log.info("Cloning %s (branch=%s, commit=%s)...", main_fw, job.branch, (main_commit or "latest")[:8])
            self.client.heartbeat(job.id)  # Keep alive during clone
            if not self.git_ops.clone_repo(main_fw, main_fw_dir, main_commit, branch=job.branch, job_id=job.id):
                self.update_job(job.id, "FAILED", f"Failed to clone {main_fw} (branch={job.branch})")
                return False

            # 3.5. Check NCS version compatibility from repo's devcontainer
            repo_ncs = self.git_ops.check_ncs_version(main_fw_dir)
            if repo_ncs:
                self._product_ncs_cache[job.product] = repo_ncs
                if self.config.ncs_version and repo_ncs != self.config.ncs_version:
                    log.warning("NCS version mismatch: repo requires %s, worker has %s — releasing job", repo_ncs, self.config.ncs_version)
                    self.update_job(job.id, "QUEUED")  # Release back for correct worker
                    return False

            # 4. Clone manufacturing firmware repo (e.g., alpha_mfg_fw)
            mfg_fw = f"{product_base}_mfg_fw"
            mfg_fw_dir = work_dir / mfg_fw
            # For mfg target builds, the commitSha belongs to the mfg repo
            mfg_commit = job.commit_sha if job.target == "mfg" else None
            log.info("Cloning %s (branch=%s, commit=%s)...", mfg_fw, job.branch, (mfg_commit or "latest")[:8] if mfg_commit else "latest")
            self.client.heartbeat(job.id)  # Keep alive during second clone
            if not self.git_ops.clone_repo(mfg_fw, mfg_fw_dir, mfg_commit, branch=job.branch, job_id=job.id):
                log.warning("Failed to clone %s - mfg builds may fail", mfg_fw)
                # Don't fail here, mfg repo might not exist for all products

            # 5. Copy MCUboot signing keys into cloned repos
            # Always overwrite — repos may ship different keys per-branch but
            # FUOTA requires both alpha_fw and alpha_mfg_fw to use the SAME
            # shared boot key so MCUboot can decrypt OTA images.
            keys_dir = Path(f"/keys/{product_base}")
            if keys_dir.is_dir():
                for key_file in keys_dir.glob("*.pem"):
                    for target_dir in [main_fw_dir, mfg_fw_dir]:
                        if target_dir.is_dir():
                            dest = target_dir / key_file.name
                            shutil.copy2(key_file, dest)
                            log.info("Copied shared key %s to %s", key_file.name, target_dir.name)

            # 6. Run build (writes log to output_dir/build.log during execution)
            self.update_job(job.id, "BUILDING")
            self._update_local_job(job.id, step="cmake_configure")
            log_file = output_dir / "build.log"
            self._update_local_job(job.id, step="compile")
            success, log_output = self.builder.run_build(job, work_dir, output_dir)
            duration = int(time.time() - start_time)

            if not success:
                log.error("Build failed for %s", job.id[:8])
                # Store truncated error in DB, full log goes to MinIO as artifact
                error_summary = log_output[-4000:] if len(log_output) > 4000 else log_output
                self.update_job(job.id, "FAILED", error_summary, duration=duration)
                # Upload full log as artifact
                self.client.upload_file(f"/v2/builds/{job.id}/artifacts", log_file, "build.log")
                return False

            # 6. Extract version from build script output (needed for manifest)
            # Build script prints "Resolved version: X.Y.Z" — use that, not greedy regex
            # (greedy regex picks up NCS container versions like "2.7.0" first)
            version_string = None
            ver_match = re.search(r"Resolved version:\s*(\d+\.\d+\.\d+)", log_output)
            if ver_match:
                version_string = ver_match.group(1)
            else:
                # Fallback: last occurrence of X.Y.Z in output (most likely the firmware version)
                all_versions = re.findall(r"(\d+\.\d+\.\d+)", log_output)
                if all_versions:
                    version_string = all_versions[-1]

            # 6.1. Collect artifacts (final hex/cfw only, no intermediates)
            self._update_local_job(job.id, step="packaging")
            artifacts = self.builder.collect_artifacts(output_dir)
            artifacts.append(log_file)  # Include build log

            # 6.3. Fetch Product.buildConfig for manifest generation
            build_config = None
            product_id = job.product_id or (job.config_flags.get("productId") if job.config_flags else None)
            if product_id:
                product_data = self.client.get_product(product_id)
                if product_data:
                    build_config = product_data.get("buildConfig")

            # 6.4. Generate build.json manifest (if buildConfig available)
            if build_config and build_config.get("targets"):
                keys_dir = Path(f"/keys/{product_base}")
                manifest_path = self.builder.write_manifest(
                    build_config=build_config,
                    output_dir=output_dir,
                    product=product_base,
                    board=job.board,
                    version=version_string or "0.0.0",
                    variant=job.variant or "release",
                    commit_sha=job.commit_sha,
                    branch=job.branch,
                    key_dir=keys_dir if keys_dir.is_dir() else None,
                )
                if manifest_path and manifest_path not in artifacts:
                    artifacts.append(manifest_path)
            else:
                log.info("No buildConfig available — skipping build.json manifest generation")

            # 6.5. Verify artifacts before upload
            valid, verify_msg = self.builder.verify_artifacts(output_dir, job.version_override)
            if not valid:
                log.error("Artifact verification failed: %s", verify_msg)
                self.update_job(job.id, "FAILED", f"Verification failed: {verify_msg}", duration=duration)
                # Still upload artifacts for debugging
                self.client.upload_file(f"/v2/builds/{job.id}/artifacts", log_file, "build.log")
                return False

            # 7. Upload artifacts with metadata from buildConfig
            self._update_local_job(job.id, step="uploading")
            artifact_count = self.builder.upload_artifacts(job.id, artifacts, build_config=build_config)
            log.info("Uploaded %d artifacts", artifact_count)

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
        ncs_info = f", ncs={self.config.ncs_version}" if self.config.ncs_version else ", ncs=all"
        log.info("Build worker starting (id=%s, poll=%ds%s)", self.config.worker_id, self.config.poll_interval, ncs_info)

        while not (self.shutdown_event and self.shutdown_event.is_set()):
            try:
                # Update heartbeat
                self._update_worker_heartbeat()

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

            # Use shutdown event for interruptible sleep
            if self.shutdown_event:
                self.shutdown_event.wait(timeout=self.config.poll_interval)
            else:
                time.sleep(self.config.poll_interval)
