"""ck_boards git service — manages its own bare clone, worktree checkout, board parsing.

Self-contained service: clones the repo on init, fetches periodically,
creates ephemeral worktrees per request, parses board.yml for SoC topology.

Board directories follow {family}_{rev} naming convention:
  alpha_a0, alpha_b0  → family "alpha", revisions "a0", "b0"
  sigma5_b0, sigma5_c0 → family "sigma5", revisions "b0", "c0"
"""

import base64
import logging
import os
import re
import shutil
import stat
import subprocess
import threading
import uuid
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

import yaml

logger = logging.getLogger(__name__)


def _split_board_name(dir_name: str) -> Tuple[str, str]:
    """Split a board directory name into (family, revision).

    Splits on the LAST underscore followed by a letter+digit pattern.
    Examples:
        alpha_a0   → ("alpha", "a0")
        sigma5_c0  → ("sigma5", "c0")
        iwsck_a1   → ("iwsck", "a1")
    """
    match = re.match(r'^(.+)_([a-zA-Z]\d+)$', dir_name)
    if match:
        return match.group(1), match.group(2)
    return dir_name, ""


def _parse_board_yml(content: str) -> Dict[str, Any]:
    """Parse a Zephyr board.yml file.

    Format: top-level 'board:' key with name, vendor, socs, revision.
    """
    raw = yaml.safe_load(content)
    if not isinstance(raw, dict):
        raise ValueError("board.yml must be a YAML mapping")
    data = raw.get("board", raw)
    socs = data.get("socs", [])
    revision_block = data.get("revision", {})
    revisions = revision_block.get("revisions", []) if isinstance(revision_block, dict) else []
    return {
        "name": data.get("name", ""),
        "vendor": data.get("vendor", ""),
        "socs": [s.get("name", "") for s in socs if isinstance(s, dict)],
        "revisions": [r.get("name", "") for r in revisions if isinstance(r, dict)],
        "variants": [v.get("name", "") for s in socs if isinstance(s, dict) for v in s.get("variants", []) if isinstance(v, dict)],
    }


class CkBoardsService:
    """Self-contained git service for ck_boards board discovery.

    Manages its own bare clone, SSH credentials, periodic fetch, and
    ephemeral worktrees for reading board definitions.
    """

    def __init__(
        self,
        repo_url: str,
        base_path: str,
        ssh_key_b64: str = "",
        fetch_interval: int = 60,
        environment: str = "development",
    ):
        self._repo_url = repo_url
        self._bare_repo = os.path.join(base_path, "ck_boards.git")
        self._worktree_base = os.path.join(base_path, "worktrees")
        self._ssh_key_path: Optional[str] = None
        self._git_env: Dict[str, str] = {}
        self._fetch_interval = fetch_interval
        self._environment = environment
        self._ready = False
        self._lock = threading.Lock()

        os.makedirs(self._worktree_base, exist_ok=True)

        # Write SSH key if provided
        if ssh_key_b64:
            self._setup_ssh_key(ssh_key_b64)

        # Clone or fetch
        self._init_repo()
        self._ready = True

        # Start periodic fetch
        if fetch_interval > 0:
            self._start_fetch_timer()

    @property
    def is_ready(self) -> bool:
        return self._ready

    # ------------------------------------------------------------------
    # SSH key management
    # ------------------------------------------------------------------

    def _setup_ssh_key(self, key_b64: str) -> None:
        """Write base64-encoded SSH key to temp file and configure git to use it."""
        key_dir = os.path.join(os.path.dirname(self._bare_repo), "ssh")
        os.makedirs(key_dir, exist_ok=True)
        self._ssh_key_path = os.path.join(key_dir, "bitbucket_key")

        key_bytes = base64.b64decode(key_b64)
        with open(self._ssh_key_path, "wb") as f:
            f.write(key_bytes)
        os.chmod(self._ssh_key_path, stat.S_IRUSR)

        self._git_env = {
            "GIT_SSH_COMMAND": f"ssh -i {self._ssh_key_path} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null",
        }

    # ------------------------------------------------------------------
    # Repo management
    # ------------------------------------------------------------------

    def _init_repo(self) -> None:
        """Clone bare repo if missing, otherwise fetch."""
        if os.path.isdir(self._bare_repo):
            logger.info("Fetching ck_boards updates...")
            self._run_git(["fetch", "--prune", "origin"])
        else:
            logger.info("Cloning ck_boards bare repo to %s ...", self._bare_repo)
            env = {**os.environ, **self._git_env}
            subprocess.run(
                ["git", "clone", "--bare", self._repo_url, self._bare_repo],
                timeout=120, check=True, capture_output=True, env=env,
            )
            logger.info("ck_boards clone complete (%s)", self._bare_repo)

    def _start_fetch_timer(self) -> None:
        """Periodic background fetch."""
        def _fetch_loop():
            while True:
                threading.Event().wait(self._fetch_interval)
                try:
                    self._run_git(["fetch", "--prune", "origin"])
                except Exception as e:
                    logger.warning("ck_boards fetch failed: %s", e)

        t = threading.Thread(target=_fetch_loop, daemon=True)
        t.start()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_refs(self) -> Dict[str, List[str]]:
        """List all branches and tags."""
        branches = self._git_list_branches()
        tags = self._git_list_tags()

        # Production: only show master/main
        if self._environment == "production":
            branches = [b for b in branches if b in ("main", "master")]

        return {"branches": branches, "tags": tags}

    def fetch(self) -> None:
        self._run_git(["fetch", "--prune", "origin"])

    def discover_boards(self, branch: str) -> List[Dict[str, Any]]:
        """Scan all board directories on a branch, grouped by product family.

        Returns a list of families, each with vendor and revisions:
        [
          {
            "family": "alpha",
            "vendor": "corekinect",
            "revisions": [
              {"version": "a0", "ckBoardsName": "alpha_a0", "socs": ["nrf9160", "nrf52840"]},
              {"version": "b0", "ckBoardsName": "alpha_b0", "socs": ["nrf9151", "nrf52840"]}
            ]
          }
        ]
        """
        self._validate_ref(branch)
        worktree_path = self._checkout_worktree(branch)
        try:
            return self._scan_boards(worktree_path)
        finally:
            self._remove_worktree(worktree_path)

    def discover_board_detail(self, family_name: str, branch: str) -> Dict[str, Any]:
        """Get full details for a product family — all revisions with SoCs."""
        self._validate_ref(branch)
        worktree_path = self._checkout_worktree(branch)
        try:
            boards_dir = self._find_boards_dir(worktree_path)
            families = self._scan_boards_in_dir(boards_dir)
            family = families.get(family_name)
            if not family:
                raise ValueError(f"Board '{family_name}' not found on this branch")
            return family
        finally:
            self._remove_worktree(worktree_path)

    # ------------------------------------------------------------------
    # Git operations
    # ------------------------------------------------------------------

    def _run_git(self, args: List[str], cwd: Optional[str] = None) -> str:
        env = {**os.environ, **self._git_env}
        cmd = ["git", "--git-dir", self._bare_repo] + args
        result = subprocess.run(
            cmd, capture_output=True, text=True, cwd=cwd, timeout=30, env=env,
        )
        if result.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
        return result.stdout.strip()

    def _git_list_branches(self) -> List[str]:
        output = self._run_git(["for-each-ref", "--format=%(refname:short)", "refs/heads/"])
        return [line for line in output.splitlines() if line]

    def _git_list_tags(self) -> List[str]:
        output = self._run_git(["for-each-ref", "--format=%(refname:short)", "refs/tags/"])
        return [line for line in output.splitlines() if line]

    def _validate_ref(self, ref: str) -> None:
        branches = self._git_list_branches()
        tags = self._git_list_tags()
        if ref not in branches and ref not in tags:
            raise ValueError(f"Ref '{ref}' not found in ck_boards repository")

    def _checkout_worktree(self, ref: str) -> str:
        worktree_id = f"{ref.replace('/', '_')}_{uuid.uuid4().hex[:8]}"
        worktree_path = os.path.join(self._worktree_base, worktree_id)
        self._run_git(["worktree", "add", "--detach", worktree_path, ref])
        return worktree_path

    def _remove_worktree(self, worktree_path: str) -> None:
        try:
            self._run_git(["worktree", "remove", "--force", worktree_path])
        except RuntimeError:
            if os.path.exists(worktree_path):
                shutil.rmtree(worktree_path, ignore_errors=True)
            try:
                self._run_git(["worktree", "prune"])
            except RuntimeError:
                pass

    # ------------------------------------------------------------------
    # Board scanning
    # ------------------------------------------------------------------

    def _find_boards_dir(self, worktree_path: str) -> str:
        """Find boards at current/boards/<vendor>/ (ck_boards layout)."""
        current_boards = os.path.join(worktree_path, "current", "boards")
        if os.path.isdir(current_boards):
            for vendor in os.listdir(current_boards):
                vendor_dir = os.path.join(current_boards, vendor)
                if os.path.isdir(vendor_dir):
                    return vendor_dir
            return current_boards
        boards_dir = os.path.join(worktree_path, "boards")
        if os.path.isdir(boards_dir):
            return boards_dir
        return worktree_path

    def _scan_boards_in_dir(self, boards_dir: str) -> Dict[str, Dict[str, Any]]:
        """Scan board directories and group by product family.

        Returns a dict keyed by family name, each containing:
        {
          "family": "alpha",
          "vendor": "corekinect",
          "revisions": [
            {"version": "a0", "ckBoardsName": "alpha_a0", "socs": [...]},
            ...
          ]
        }
        """
        families: Dict[str, Dict[str, Any]] = {}
        for entry in sorted(os.listdir(boards_dir)):
            board_dir = os.path.join(boards_dir, entry)
            board_yml = os.path.join(board_dir, "board.yml")
            if os.path.isdir(board_dir) and os.path.isfile(board_yml):
                try:
                    with open(board_yml) as f:
                        board_data = _parse_board_yml(f.read())

                    family, version = _split_board_name(entry)
                    if not version:
                        # Fallback: use directory name as family, no version
                        family = entry
                        version = ""

                    if family not in families:
                        families[family] = {
                            "family": family,
                            "vendor": board_data["vendor"],
                            "revisions": [],
                        }

                    families[family]["revisions"].append({
                        "version": version,
                        "ckBoardsName": entry,
                        "socs": board_data["socs"],
                    })
                except Exception as e:
                    logger.warning("Failed to parse board %s: %s", entry, e)
        return families

    def _scan_boards(self, worktree_path: str) -> List[Dict[str, Any]]:
        boards_dir = self._find_boards_dir(worktree_path)
        families = self._scan_boards_in_dir(boards_dir)
        return sorted(families.values(), key=lambda f: f["family"])
