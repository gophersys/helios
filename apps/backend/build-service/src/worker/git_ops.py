"""Git operations — repo cloning, NCS version check, build script/overlay fetching."""

import json
import logging
import os
import re
import subprocess
import tarfile
from io import BytesIO
from pathlib import Path
from typing import Dict, Optional

import requests

from src.clients.concord import ConcordClient

log = logging.getLogger("build-service")


class GitOps:
    """Git operations and source artifact fetching."""

    def __init__(self, ssh_key_path: str, api_client: ConcordClient):
        self.ssh_key_path = ssh_key_path
        self.api_client = api_client

        # Repo configs fetched from API (populated by _load_repo_configs)
        self._repo_configs: Dict[str, dict] = {}
        self._configs_loaded = False

    def _load_repo_configs(self) -> bool:
        """Fetch repo configs from API. Called once at startup and on cache miss."""
        result = self.api_client.api_get("/v2/builds/settings/repos")
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

    def fetch_build_script(self, product: str) -> Optional[str]:
        """Fetch build script content from API."""
        # Map product names to script keys (alpha_fw -> alpha)
        script_key = product.lower().replace("_fw", "").replace("_mfg", "")
        result = self.api_client.api_get(f"/v2/builds/scripts/{script_key}")
        if not result or not result.get("data"):
            log.error("Failed to fetch build script for %s", product)
            return None
        return result["data"].get("content")

    def fetch_overlays(self, product: str, dest_dir: Path) -> bool:
        """Fetch and extract overlay files from API."""
        script_key = product.lower().replace("_fw", "").replace("_mfg", "")
        try:
            resp = requests.get(
                f"{self.api_client.api_url}/v2/builds/overlays/{script_key}",
                headers=self.api_client._headers(),
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

    def clone_repo(self, repo_slug: str, dest_dir: Path, commit_sha: str = None,
                   branch: str = None, job_id: str = None) -> bool:
        """Clone a repo to a specific directory.

        Args:
            repo_slug: The repo identifier (e.g., "alpha_fw")
            dest_dir: Where to clone the repo
            commit_sha: Optional commit to checkout
            branch: Optional branch to clone (default: repo default branch)
            job_id: Optional job ID for log streaming
        """
        config = self._get_repo_config(repo_slug)
        if not config or not config.get("ssh_url"):
            log.error("No SSH URL configured for repo: %s", repo_slug)
            return False

        repo_url = config["ssh_url"]
        env = os.environ.copy()
        env["GIT_SSH_COMMAND"] = f"ssh -i {self.ssh_key_path} -o StrictHostKeyChecking=no -o BatchMode=yes"

        def _log(msg: str):
            log.info(msg)
            if job_id:
                self.api_client.stream_log_chunk(job_id, msg + "\n")

        try:
            # Clone — use specific branch if provided
            clone_cmd = ["git", "clone", "--depth", "50", "--progress"]
            if branch:
                clone_cmd.extend(["-b", branch])
            clone_cmd.extend([repo_url, str(dest_dir)])

            _log(f"[clone] git clone {repo_slug} (branch={branch or 'default'})...")
            result = subprocess.run(
                clone_cmd,
                env=env, check=True, capture_output=True, timeout=120,
            )
            # Git clone progress goes to stderr
            if result.stderr:
                clone_output = result.stderr.decode("utf-8", errors="replace").strip()
                if job_id and clone_output:
                    self.api_client.stream_log_chunk(job_id, clone_output + "\n")

            # Checkout specific commit if provided
            if commit_sha:
                _log(f"[clone] Checking out {commit_sha[:8]}...")
                subprocess.run(
                    ["git", "checkout", commit_sha],
                    cwd=dest_dir, check=True, capture_output=True, timeout=30,
                )

            # Initialize submodules (must pass env for SSH key)
            _log(f"[clone] Initializing submodules...")
            result = subprocess.run(
                ["git", "submodule", "update", "--init", "--recursive", "--progress", "--jobs", "8"],
                cwd=dest_dir, env=env, check=True, capture_output=True, timeout=300,
            )
            if result.stderr:
                sub_output = result.stderr.decode("utf-8", errors="replace").strip()
                if job_id and sub_output:
                    self.api_client.stream_log_chunk(job_id, sub_output + "\n")

            _log(f"[clone] {repo_slug} ready")
            return True

        except subprocess.CalledProcessError as e:
            log.error("Git failed: %s", e.stderr.decode() if e.stderr else str(e))
            return False
        except Exception as e:
            log.error("Clone failed: %s", e)
            return False

    def check_ncs_version(self, repo_dir: Path) -> Optional[str]:
        """Read NCS version from repo's .devcontainer/devcontainer.json.

        Returns the NCS version string (e.g., '2.7.0') or None if not found.
        """
        devcontainer = repo_dir / ".devcontainer" / "devcontainer.json"
        if not devcontainer.exists():
            return None
        try:
            text = devcontainer.read_text()
            # Remove JSON comments (// style)
            text = re.sub(r'//.*$', '', text, flags=re.MULTILINE)
            data = json.loads(text)
            image = data.get("image", "")
            # Extract version from image tag like "containers.ad.corekinect.com/ncs-fw-dev:2.7.0"
            match = re.search(r'ncs.*?:(\d+\.\d+\.\d+)', image)
            if match:
                return match.group(1)
        except Exception as e:
            log.warning("Could not parse devcontainer.json: %s", e)
        return None
