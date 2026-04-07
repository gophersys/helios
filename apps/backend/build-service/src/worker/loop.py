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

        # Docker build runner (if builder_mode == "docker")
        self.docker_runner = None
        if config.builder_mode == "docker":
            from src.worker.docker_runner import DockerBuildRunner
            self.docker_runner = DockerBuildRunner(
                workspace_volume=config.workspace_volume,
                ccache_volume=config.ccache_volume,
                builder_network=config.builder_network,
                builder_timeout=config.builder_timeout,
                default_image=config.default_builder_image,
            )
            log.info("Docker build mode enabled (default image: %s)", config.default_builder_image)

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
                        "ncsVersion": "",
                        "status": "ONLINE",
                        "lastHeartbeat": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    },
                    "update": {
                        "ncsVersion": "",
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
            # In docker mode, any NCS version is supported — skip version check
            # In local mode, we'd need to check NCS compatibility here

            return BuildJob(
                id=j["id"],
                product=j["product"],
                board=j["board"],
                target=j["target"],
                variant=j["variant"],
                branch=j["branch"],
                commit_sha=j["commitSha"] or "",
                status=j["status"],
                version_bump=j.get("versionBump", False),
                base_job_id=j.get("baseJobId"),
                matrix_label=j.get("matrixLabel"),
                version_override=_extract_version_override(j),
                config_flags=j.get("configFlags") or {},
                product_id=j.get("productId"),
                recipe_version_id=j.get("recipeVersionId"),
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

            # ── Resolve repos from webhookData ──
            # Each BuildJob carries both repo URLs so the worker doesn't guess.
            # repoUrl = the PRIMARY source (where the build script lives)
            # The other repo is SECONDARY (cloned at mainline for shared assets)
            webhook = job.config_flags  # webhookData is parsed into the job
            # Try to get repo info from the API response's webhookData
            _webhook_data = {}
            try:
                result = self.client.api_get(f"/v2/builds/{job.id}")
                if result and result.get("data"):
                    _webhook_data = result["data"].get("webhookData") or {}
            except Exception:
                pass

            fw_slug = _webhook_data.get("fwRepoSlug") or f"{job.product.lower()}_fw"
            mfg_slug = _webhook_data.get("mfgRepoSlug") or f"{job.product.lower()}_mfg_fw"
            product_base = job.product.lower().replace("_fw", "").replace("_mfg", "")

            # Determine primary/secondary based on build target
            # The PR branch only exists on the fw repo. The mfg repo always uses "main".
            # Both repo types are cloned — primary is the one being built,
            # secondary provides shared assets (signing keys, etc).
            if job.target == "mfg":
                primary_slug = mfg_slug
                primary_branch = "main"     # mfg repo always uses mainline
                primary_commit = None       # latest on main
                secondary_slug = fw_slug
                secondary_branch = job.branch
                secondary_commit = job.commit_sha
            else:
                primary_slug = fw_slug
                primary_branch = job.branch
                primary_commit = job.commit_sha
                secondary_slug = mfg_slug
                secondary_branch = "main"
                secondary_commit = None

            # 1. Fetch overlays from API (optional)
            self._update_local_job(job.id, step="clone")
            overlays_dir = work_dir / "overlays"
            self.git_ops.fetch_overlays(job.product, overlays_dir)

            # 2. Clone PRIMARY repo (contains the build script + source to compile)
            primary_dir = work_dir / primary_slug
            log.info("Cloning PRIMARY %s (branch=%s, commit=%s)...",
                     primary_slug, primary_branch, (primary_commit or "latest")[:8])
            self.client.heartbeat(job.id)
            if not self.git_ops.clone_repo(primary_slug, primary_dir, primary_commit,
                                           branch=primary_branch, job_id=job.id):
                self.update_job(job.id, "FAILED",
                               f"Failed to clone {primary_slug} (branch={primary_branch})")
                return False

            # 2.5. NCS version detection (informational — docker mode uses correct image)
            repo_ncs = self.git_ops.check_ncs_version(primary_dir)
            if repo_ncs:
                self._product_ncs_cache[job.product] = repo_ncs
                log.info("Detected NCS version: %s", repo_ncs)

            # 3. Clone SECONDARY repo (shared assets, signing keys, mfg firmware)
            secondary_dir = work_dir / secondary_slug
            log.info("Cloning SECONDARY %s (branch=%s)...", secondary_slug, secondary_branch)
            self.client.heartbeat(job.id)
            if not self.git_ops.clone_repo(secondary_slug, secondary_dir, secondary_commit,
                                           branch=secondary_branch, job_id=job.id):
                log.warning("Failed to clone %s — secondary repo unavailable", secondary_slug)

            # 4. Fetch build recipe
            # Priority: API recipe (Concord-managed) → repo script → fail
            scripts_dir = work_dir / "scripts"
            scripts_dir.mkdir(parents=True, exist_ok=True)
            recipe_path = scripts_dir / "build.sh"

            recipe_found = False
            product_id = job.product_id or (_webhook_data.get("productId"))

            # Try API recipe first (stored in MinIO via Products → Build Config)
            # Recipes: firmware/recipes/{slug}/{board}/{domain}/{stage}/build.sh
            if product_id:
                # If a pinned recipe version exists, fetch that specific version
                recipe_version_id = job.recipe_version_id
                if recipe_version_id:
                    result = self.client.api_get(
                        f"/v2/products/{product_id}/recipe/versions/by-id/{recipe_version_id}"
                    )
                    if result and result.get("data"):
                        content = result["data"].get("content")
                        if content:
                            recipe_path.write_text(content)
                            recipe_path.chmod(0o755)
                            recipe_found = True
                            log.info("Build recipe loaded from pinned version %s", recipe_version_id)

                # Fall back to stage-specific or product-level recipe
                if not recipe_found:
                    job_stage = _webhook_data.get("stage")
                    if not job_stage:
                        build_run_id = getattr(job, 'buildRunId', None) or getattr(job, 'build_run_id', None)
                        if build_run_id:
                            run_result = self.client.api_get(f"/v2/builds/runs/{build_run_id}")
                            if run_result and run_result.get("data"):
                                job_stage = run_result["data"].get("stage")

                    recipe_url = f"/v2/products/{product_id}/recipe"
                    if job_stage:
                        recipe_url += f"?stage={job_stage}"

                    result = self.client.api_get(recipe_url)
                    if result and result.get("data"):
                        content = result["data"].get("content")
                        if content:
                            recipe_path.write_text(content)
                            recipe_path.chmod(0o755)
                            recipe_found = True
                            stage_label = f"stage {job_stage}" if job_stage else "product-level"
                            log.info("Build recipe loaded from API (%s)", stage_label)

            # Fall back to repo's own build script
            if not recipe_found:
                for candidate in [
                    primary_dir / "scripts" / "build.sh",
                    primary_dir / "build_all.sh",
                    primary_dir / "build.sh",
                ]:
                    if candidate.exists():
                        shutil.copy2(candidate, recipe_path)
                        recipe_path.chmod(0o755)
                        recipe_found = True
                        log.info("Using repo build script: %s", candidate.name)
                        break

            if not recipe_found:
                self.update_job(job.id, "FAILED",
                               f"No build recipe found — upload one via Products → Build Config")
                return False

            # 4.5. Fetch product targets for SDK env vars (appId, role, processor)
            # Only include targets from the revision matching the job's board name
            import json as _json
            targets_json = "[]"
            if product_id:
                prod_result = self.client.api_get(f"/v2/products/{product_id}")
                if prod_result and prod_result.get("data"):
                    prod_data = prod_result["data"]
                    job_board = job.board  # e.g., "alpha_b0"
                    targets = []
                    for board in (prod_data.get("boards") or []):
                        for rev in (board.get("revisions") or []):
                            # Only include targets from the matching board revision
                            if rev.get("ckBoardsName") == job_board:
                                for t in (rev.get("targets") or []):
                                    targets.append({
                                        "role": t.get("role", ""),
                                        "appId": t.get("appId", 0),
                                        "processor": t.get("processor") or t.get("soc", ""),
                                    })
                    if targets:
                        targets_json = _json.dumps(targets)
                        log.info("Product targets for %s: %s", job_board, targets_json)
                    else:
                        log.warning("No targets found for board %s — check product revision config", job_board)
            if not job.config_flags:
                job.config_flags = {}
            job.config_flags["_targets_json"] = targets_json

            # 4.6. Copy SDK into workspace (needed for DinD — can't bind-mount from container)
            sdk_src = Path("/app/sdk")
            sdk_dest = work_dir / "sdk"
            if sdk_src.is_dir() and not sdk_dest.exists():
                shutil.copytree(sdk_src, sdk_dest)
                log.info("Copied Concord Build SDK to workspace")
                # Update the recipe to source from workspace-relative path
                if recipe_path.exists():
                    content = recipe_path.read_text()
                    content = content.replace(
                        "source /app/sdk/concord-build.sh",
                        f"source /workspace/{job.id}/sdk/concord-build.sh"
                    )
                    recipe_path.write_text(content)

            # 5. Deploy signing key from Concord Secrets
            #
            # The stage config's signingKeyId points to a Secret in Concord.
            # The build trigger embeds the key value (base64) in webhookData
            # so the orchestrator doesn't need direct DB access.
            #
            # This key is the MCUboot encryption key — critical for FUOTA.
            # Both repos MUST use the SAME key so MCUboot can decrypt OTA images.
            # The SDK's _concord_fix_sysbuild_paths handles writing the key to
            # the paths that sysbuild.conf references.
            import base64 as _b64
            signing_key_b64 = _webhook_data.get("signingKeyValue")
            signing_key_deployed = False

            if signing_key_b64:
                try:
                    key_bytes = _b64.b64decode(signing_key_b64)
                    # Deploy to BOTH repos — every path that sysbuild.conf might reference
                    for target_dir in [primary_dir, secondary_dir]:
                        if not target_dir.is_dir():
                            continue
                        for key_name in ["encryption_key.pem", "comms_encryption_key.pem"]:
                            dest = target_dir / key_name
                            dest.write_bytes(key_bytes)
                            dest.chmod(0o600)
                        # Also into comm_coproc_mfg subdirectory
                        comms_subdir = target_dir / "comm_coproc_mfg"
                        if comms_subdir.is_dir():
                            (comms_subdir / "comms_encryption_key.pem").write_bytes(key_bytes)
                            (comms_subdir / "comms_encryption_key.pem").chmod(0o600)
                        log.info("Signing key deployed to %s (from Concord Secrets)", target_dir.name)
                    signing_key_deployed = True
                except Exception as e:
                    log.error("Failed to decode signing key: %s", e)

            # Fallback: check /keys/{product} mount (K8s secret volume, staging/production)
            if not signing_key_deployed:
                keys_dir = Path(f"/keys/{product_base}")
                if keys_dir.is_dir():
                    for key_file in keys_dir.glob("*.pem"):
                        for target_dir in [primary_dir, secondary_dir]:
                            if target_dir.is_dir():
                                for key_name in ["encryption_key.pem", "comms_encryption_key.pem"]:
                                    shutil.copy2(key_file, target_dir / key_name)
                                comms_subdir = target_dir / "comm_coproc_mfg"
                                if comms_subdir.is_dir():
                                    shutil.copy2(key_file, comms_subdir / "comms_encryption_key.pem")
                        log.info("Signing key from K8s mount: %s", key_file.name)
                        signing_key_deployed = True
                        break

            if not signing_key_deployed:
                log.warning("No signing key configured — encrypted builds will fail. "
                           "Add a signing key in Products → Stage Config → Signing Key")

            # 6. Resolve builder image from devcontainer.json
            builder_image = None
            if self.docker_runner:
                builder_image = self.git_ops.get_builder_image(primary_dir)
                if not builder_image:
                    builder_image = self.config.default_builder_image
                    log.info("No devcontainer.json — using default: %s", builder_image)

                if not self.docker_runner.ensure_image(builder_image):
                    self.update_job(job.id, "FAILED",
                                   f"Failed to pull builder image: {builder_image}")
                    return False

                # Store builder image and primary slug in config_flags
                if not job.config_flags:
                    job.config_flags = {}
                job.config_flags["_primary_slug"] = primary_slug
                job.config_flags["_builder_image"] = builder_image

                # Write builder image to the job record so the UI can display it
                self.client.api_patch(f"/v2/builds/{job.id}", {
                    "configFlags": job.config_flags,
                })
                log.info("Builder image: %s", builder_image)

            # 7. Run build
            self.update_job(job.id, "BUILDING")
            self._update_local_job(job.id, step="compile")
            log_file = output_dir / "build.log"
            success, log_output = self.builder.run_build(
                job, work_dir, output_dir,
                docker_runner=self.docker_runner,
                builder_image=builder_image,
            )
            duration = int(time.time() - start_time)

            # Write build log to file (for upload even on failure)
            if log_output:
                log_file.write_text(log_output)
                log.info("Build output: %d lines, %d chars", log_output.count('\n'), len(log_output))
                # Log last 20 lines for debugging
                for line in log_output.strip().split('\n')[-20:]:
                    log.info("  | %s", line)

            if not success:
                log.error("Build failed for %s", job.id[:8])
                error_summary = log_output[-4000:] if len(log_output) > 4000 else log_output
                self.update_job(job.id, "FAILED", error_summary, duration=duration)
                if log_file.exists():
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
        ncs_info = f", mode={self.config.builder_mode}"
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
