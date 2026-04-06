"""Git-based repo poller -- polls for new commits via SSH and triggers CI.

Polls every N seconds using git ls-remote. Uses SSH key auth.
Repo configs come from the Product catalog (/v2/catalog/products).
"""

import atexit
import json
import os
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import requests

# Suppress SSL warnings for self-signed certs
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from corekinect.utils import Logger, print_banner

log = Logger(log_name="git-poller")


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

    Fetches repo configs from the Concord API, so new products are
    discovered automatically from the Product model in DB.
    """

    def __init__(
        self,
        config,
        shutdown_event: threading.Event,
        state_file: str = "/tmp/git_poller_state.json",
    ):
        self.config = config
        self.shutdown = shutdown_event
        self.state_file = Path(state_file)
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
        if not self.config.api_key:
            log.warning("No API key configured, cannot fetch repo configs")
            return []

        try:
            url = f"{self.config.api_url}/v2/products"
            headers = {
                "Authorization": f"ApiKey {self.config.api_key}",
                "Content-Type": "application/json",
            }
            resp = requests.get(url, headers=headers, timeout=30, verify=False)

            if resp.status_code >= 400:
                log.error("Failed to fetch products: %d %s", resp.status_code, resp.text[:200])
                return []

            data = resp.json()
            # Paginated response: {"data": {"data": [...], "pagination": {...}}}
            inner = data.get("data", {})
            products = inner.get("data", []) if isinstance(inner, dict) else inner

            repos = []
            for p in products:
                if not p.get("active", True):
                    continue

                ssh_url = p.get("repoSshUrl", "")
                if not ssh_url:
                    continue

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
            if os.environ.get("SSH_AUTH_SOCK"):
                env["GIT_SSH_COMMAND"] = "ssh -o StrictHostKeyChecking=no -o BatchMode=yes"
            else:
                env["GIT_SSH_COMMAND"] = f"ssh -i {self.config.ssh_key_path} -o StrictHostKeyChecking=no -o BatchMode=yes"

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
        """Trigger a CI pipeline via Concord API."""
        if not self.config.api_key:
            log.warning("No API key configured, skipping trigger for %s", repo.name)
            return False

        try:
            url = f"{self.config.api_url}/v2/builds/trigger"
            headers = {
                "Authorization": f"ApiKey {self.config.api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "productId": repo.product_id,
                "repoSlug": repo.name,
                "branch": repo.branch,
                "commitSha": commit_sha,
                "board": repo.build_board,
                "triggerType": "poller",
                "matrixMode": "fuota",
                "mfgRepoSlug": repo.mfg_repo_slug or None,
                "mfgSshUrl": repo.mfg_ssh_url or None,
                "validationConfig": {"stage": 5},
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
                log.info("[%s] Initial SHA: %s", repo.name, sha[:8])
                self.state[repo.name] = sha
                self._save_state()
            elif sha != last_sha:
                log.info("[%s] New commit: %s -> %s", repo.name, last_sha[:8], sha[:8])
                if self.trigger_build(repo, sha):
                    self.state[repo.name] = sha
                    self._save_state()
            else:
                log.debug("[%s] No change (%s)", repo.name, sha[:8])

    def run(self) -> None:
        """Main polling loop. Blocks until shutdown event is set."""
        repos = self._get_repos()
        if repos:
            log.info("Watching: %s", ", ".join(r.name for r in repos))
        else:
            log.warning("No repos loaded from API -- will retry")

        while not self.shutdown.is_set():
            try:
                self.poll_once()
            except Exception as e:
                log.exception("Poll cycle failed: %s", e)

            self.shutdown.wait(timeout=self.config.poll_interval)


def _setup_ssh_key(config) -> None:
    """Decode base64 SSH key to file if provided via env var."""
    import base64
    import stat

    # If SSH_AUTH_SOCK is set and the socket exists, use agent
    sock = os.environ.get("SSH_AUTH_SOCK", "")
    if sock and os.path.exists(sock):
        log.info("Using SSH agent at %s", sock)
        return

    # If BITBUCKET_SSH_KEY is set (base64-encoded), write to key file
    if config.bitbucket_ssh_key:
        key_dir = Path(config.ssh_key_path).parent
        key_dir.mkdir(parents=True, exist_ok=True)
        key_path = Path(config.ssh_key_path)
        key_data = base64.b64decode(config.bitbucket_ssh_key)
        key_path.write_bytes(key_data)
        key_path.chmod(stat.S_IRUSR)
        log.info("SSH key written to %s (%d bytes)", config.ssh_key_path, len(key_data))
    elif not Path(config.ssh_key_path).exists():
        log.warning("No SSH key available -- git operations will fail")


def _run_health_server(port: int) -> None:
    """Minimal health endpoint for K8s probes."""
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import json as _json

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = _json.dumps({"status": "healthy", "service": "git-poller"})
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body.encode())
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, format, *args):
            pass  # Suppress access logs

    HTTPServer(("0.0.0.0", port), Handler).serve_forever()


def main():
    """Entry point."""
    from src.config import GitPollerConfig

    config = GitPollerConfig()

    # ── Banner ──────────────────────────────────────────────────────────────
    print_banner(
        "concord-git-poller",
        Port=str(config.service_port),
        Interval=f"{config.poll_interval}s",
    )

    # ── SSH ──────────────────────────────────────────────────────────────────
    _setup_ssh_key(config)

    # ── Health endpoint (daemon thread) ──────────────────────────────────────
    health_thread = threading.Thread(
        target=_run_health_server,
        args=(config.service_port,),
        daemon=True,
        name="health-server",
    )
    health_thread.start()
    log.info(f"Health server started on :{config.service_port}")

    # ── Graceful shutdown ────────────────────────────────────────────────────
    shutdown = threading.Event()

    def handle_signal(signum, _frame):
        name = signal.Signals(signum).name
        log.info(f"Received {name}, shutting down...")
        shutdown.set()

    def cleanup():
        log.info("Graceful shutdown initiated (atexit)")
        log.info("Git poller stopped")

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)
    atexit.register(cleanup)

    # ── Poller loop (blocks until shutdown) ───────────────────────────────────
    poller = GitPoller(config=config, shutdown_event=shutdown)
    poller.run()


if __name__ == "__main__":
    main()
