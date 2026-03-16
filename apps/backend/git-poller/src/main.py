"""Git-based repo poller — polls for new commits via SSH and triggers CI.

Lightweight alternative to webhooks. Polls every N seconds using git ls-remote.
Uses SSH key auth, no API tokens needed.

Repo configs are fetched from the Product catalog (/v2/catalog/products).
Products define their repos via repoSlug, repoSshUrl, repoBranch fields.
This allows adding new products without changing poller code.

Usage:
    python -m src.services.git_poller

Environment:
    GIT_SSH_KEY_PATH: Path to SSH private key (default: /root/.ssh/keys/bitbucket)
    POLL_INTERVAL: Seconds between polls (default: 15)
    CONCORD_API_URL: Concord API base URL
    CONCORD_API_KEY: API key for triggering builds
"""

import json
import logging
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import requests

# Suppress SSL warnings for self-signed certs
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("git_poller")


@dataclass
class RepoConfig:
    """Configuration for a watched repository."""
    name: str           # repo slug (e.g. "alpha_fw")
    ssh_url: str        # git SSH URL
    branch: str         # branch to watch
    product_id: str     # Concord product ID for triggering builds
    build_board: str = ""     # board variant (e.g. "alpha_b0")
    mfg_repo_slug: str = ""   # manufacturing firmware repo slug
    mfg_ssh_url: str = ""     # manufacturing firmware SSH URL


class GitPoller:
    """Polls git repos for new commits and triggers CI builds.

    Fetches repo configs from the Concord API, so new products can be
    added to REPO_PRODUCT_MAP without changing this code.
    """

    def __init__(
        self,
        ssh_key_path: str = "/root/.ssh/keys/bitbucket",
        poll_interval: int = 15,
        state_file: str = "/tmp/git_poller_state.json",
        api_url: str = "https://staging.concord.local",
        api_key: str = "",
    ):
        self.ssh_key_path = ssh_key_path
        self.poll_interval = poll_interval
        self.state_file = Path(state_file)
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.state: Dict[str, str] = {}  # repo_name -> last_commit_sha
        self._repos: List[RepoConfig] = []
        self._repos_loaded_at: float = 0
        self._repos_cache_ttl: float = 300  # Refresh repo list every 5 minutes
        self._load_state()

    def _load_state(self) -> None:
        """Load last known commit SHAs from state file."""
        if self.state_file.exists():
            try:
                self.state = json.loads(self.state_file.read_text())
                log.info("Loaded state: %d repos tracked", len(self.state))
            except Exception as e:
                log.warning("Failed to load state: %s", e)
                self.state = {}

    def _save_state(self) -> None:
        """Save current state to file."""
        try:
            self.state_file.write_text(json.dumps(self.state, indent=2))
        except Exception as e:
            log.warning("Failed to save state: %s", e)

    def _fetch_repo_configs(self) -> List[RepoConfig]:
        """Fetch repo configs from the Product catalog.

        Products define their repos via:
          - repoSlug: short name (e.g. "alpha_fw")
          - repoSshUrl: git SSH URL
          - repoBranch: branch to watch (default: concord-main)
          - mfgRepoSlug: manufacturing firmware repo (built with main)

        Only active products with repoSshUrl are polled.
        """
        if not self.api_key:
            log.warning("No API key configured, cannot fetch repo configs")
            return []

        try:
            url = f"{self.api_url}/v2/products"
            headers = {
                "Authorization": f"ApiKey {self.api_key}",
                "Content-Type": "application/json",
            }
            resp = requests.get(url, headers=headers, timeout=30, verify=False)

            if resp.status_code >= 400:
                log.error("Failed to fetch products: %d %s", resp.status_code, resp.text[:200])
                return []

            data = resp.json()
            products = data.get("data", [])

            repos = []
            for p in products:
                # Skip inactive products
                if not p.get("active", True):
                    continue

                # Get repo config from product fields
                ssh_url = p.get("repoSshUrl", "")
                if not ssh_url:
                    continue  # Skip products without SSH URL configured

                repo_slug = p.get("repoSlug") or p.get("slug", "")
                branch = p.get("repoBranch", "concord-main") or "concord-main"

                repos.append(RepoConfig(
                    name=repo_slug,
                    ssh_url=ssh_url,
                    branch=branch,
                    product_id=p.get("id", ""),
                    build_board=p.get("buildBoard", ""),
                    mfg_repo_slug=p.get("mfgRepoSlug", ""),
                    mfg_ssh_url=p.get("mfgRepoSshUrl", ""),
                ))

            return repos

        except Exception as e:
            log.error("Failed to fetch products: %s", e)
            return []

    def _get_repos(self) -> List[RepoConfig]:
        """Get repos, refreshing from API if cache is stale."""
        now = time.time()
        if not self._repos or (now - self._repos_loaded_at) > self._repos_cache_ttl:
            self._repos = self._fetch_repo_configs()
            self._repos_loaded_at = now
            if self._repos:
                log.info("Loaded %d repos from API: %s", len(self._repos), [r.name for r in self._repos])
        return self._repos

    def get_remote_sha(self, repo: RepoConfig) -> Optional[str]:
        """Get latest commit SHA from remote branch via git ls-remote."""
        try:
            env = os.environ.copy()
            env["GIT_SSH_COMMAND"] = f"ssh -i {self.ssh_key_path} -o StrictHostKeyChecking=no -o BatchMode=yes"

            result = subprocess.run(
                ["git", "ls-remote", repo.ssh_url, f"refs/heads/{repo.branch}"],
                capture_output=True,
                text=True,
                timeout=30,
                env=env,
            )

            if result.returncode != 0:
                log.error("git ls-remote failed for %s: %s", repo.name, result.stderr)
                return None

            # Output format: "sha\trefs/heads/branch"
            line = result.stdout.strip()
            if not line:
                log.warning("Branch %s not found in %s", repo.branch, repo.name)
                return None

            sha = line.split()[0]
            return sha

        except subprocess.TimeoutExpired:
            log.error("git ls-remote timed out for %s", repo.name)
            return None
        except Exception as e:
            log.error("Failed to get SHA for %s: %s", repo.name, e)
            return None

    def trigger_build(self, repo: RepoConfig, commit_sha: str) -> bool:
        """Trigger a CI pipeline via Concord API.

        Creates a PipelineRun with build jobs for:
          1. Production firmware (repo.name)
          2. Manufacturing firmware (repo.mfg_repo_slug) if configured
        """
        if not self.api_key:
            log.warning("No API key configured, skipping trigger for %s", repo.name)
            return False

        try:
            url = f"{self.api_url}/v2/builds/pipelines"
            headers = {
                "Authorization": f"ApiKey {self.api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "productId": repo.product_id,
                "repoSlug": repo.name,
                "branch": repo.branch,
                "commitSha": commit_sha,
                "board": repo.build_board,
                "triggerType": "poller",
                # Include mfg repo info if configured
                "mfgRepoSlug": repo.mfg_repo_slug or None,
                "mfgSshUrl": repo.mfg_ssh_url or None,
            }

            log.info("Triggering pipeline for %s @ %s (board=%s)", repo.name, commit_sha[:8], repo.build_board)
            resp = requests.post(url, json=payload, headers=headers, timeout=30, verify=False)

            if resp.status_code >= 400:
                log.error("Pipeline trigger failed for %s: %d %s", repo.name, resp.status_code, resp.text[:200])
                return False

            data = resp.json()
            if data.get("errors"):
                log.error("Pipeline trigger error for %s: %s", repo.name, data["errors"])
                return False

            pipeline_id = data.get("data", {}).get("id", "?")
            log.info("Pipeline triggered for %s: %s", repo.name, pipeline_id[:8] if len(pipeline_id) > 8 else pipeline_id)
            return True

        except Exception as e:
            log.error("Failed to trigger pipeline for %s: %s", repo.name, e)
            return False

    def poll_once(self) -> None:
        """Poll all repos once and trigger builds for new commits."""
        repos = self._get_repos()
        if not repos:
            log.debug("No repos configured")
            return

        for repo in repos:
            sha = self.get_remote_sha(repo)
            if not sha:
                continue

            last_sha = self.state.get(repo.name)

            if last_sha is None:
                # First time seeing this repo
                log.info("[%s] Initial SHA: %s", repo.name, sha[:8])
                self.state[repo.name] = sha
                self._save_state()
            elif sha != last_sha:
                # New commit detected!
                log.info("[%s] New commit: %s -> %s", repo.name, last_sha[:8], sha[:8])
                if self.trigger_build(repo, sha):
                    self.state[repo.name] = sha
                    self._save_state()
            else:
                # No change
                log.debug("[%s] No change (%s)", repo.name, sha[:8])

    def run(self) -> None:
        """Main polling loop."""
        log.info("Git poller starting (interval=%ds)", self.poll_interval)

        # Initial fetch to log what we're watching
        repos = self._get_repos()
        if repos:
            log.info("Watching: %s", ", ".join(r.name for r in repos))
        else:
            log.warning("No repos loaded from API — will retry")

        while True:
            try:
                self.poll_once()
            except Exception as e:
                log.exception("Poll cycle failed: %s", e)

            time.sleep(self.poll_interval)


def main():
    """Entry point."""
    poller = GitPoller(
        ssh_key_path=os.environ.get("GIT_SSH_KEY_PATH", "/root/.ssh/keys/bitbucket"),
        poll_interval=int(os.environ.get("POLL_INTERVAL", "15")),
        api_url=os.environ.get("CONCORD_API_URL", "https://staging.concord.local"),
        api_key=os.environ.get("CONCORD_API_KEY", ""),
    )
    poller.run()


if __name__ == "__main__":
    main()
