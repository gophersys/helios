"""ck_boards REST API service — fetches board definitions via Bitbucket HTTPS API.

No git clone, no SSH, no worktrees. Uses the Bitbucket 2.0 REST API to read
board.yml files directly. Works from any network that can reach HTTPS port 443.

Board directories follow {family}_{rev} naming convention:
  alpha_a0, alpha_b0  → family "alpha", revisions "a0", "b0"
  sigma5_b0, sigma5_c0 → family "sigma5", revisions "b0", "c0"
"""

import logging
import re
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

import requests
import yaml  # type: ignore[import-untyped]
from requests.auth import HTTPBasicAuth  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)

# Suppress SSL warnings for internal network
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_API_BASE = "https://api.bitbucket.org/2.0"


def _split_board_name(dir_name: str) -> Tuple[str, str]:
    """Split a board directory name into (family, revision).

    Examples:
        alpha_a0   → ("alpha", "a0")
        sigma5_c0  → ("sigma5", "c0")
    """
    match = re.match(r'^(.+)_([a-zA-Z]\d+)$', dir_name)
    if match:
        return match.group(1), match.group(2)
    return dir_name, ""


def _parse_board_yml(content: str) -> Dict[str, Any]:
    """Parse a Zephyr board.yml file."""
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
    """Board discovery via Bitbucket REST API (HTTPS, no SSH/git required)."""

    def __init__(
        self,
        workspace: str,
        repo_slug: str,
        email: str,
        api_token: str,
        fetch_interval: int = 60,
        environment: str = "development",
    ):
        if not email or not api_token:
            raise RuntimeError("CkBoards requires BITBUCKET_EMAIL and BITBUCKET_API_TOKEN")

        self._workspace = workspace
        self._repo_slug = repo_slug
        self._auth = HTTPBasicAuth(email, api_token)
        self._environment = environment
        self._fetch_interval = fetch_interval

        # Cache
        self._cache: Dict[str, List[Dict[str, Any]]] = {}
        self._cache_time: Dict[str, float] = {}
        self._cache_ttl = max(fetch_interval, 60)
        self._lock = threading.Lock()
        self._ready = False

        # Verify connectivity
        self._verify_access()
        self._ready = True
        logger.info("CkBoards service ready (REST API, workspace=%s, repo=%s)", workspace, repo_slug)

    @property
    def is_ready(self) -> bool:
        return self._ready

    # ------------------------------------------------------------------
    # Bitbucket API
    # ------------------------------------------------------------------

    def _api_get(self, path: str, **kwargs) -> requests.Response:
        """GET from Bitbucket API with auth."""
        url = f"{_API_BASE}/repositories/{self._workspace}/{self._repo_slug}/{path}"
        resp = requests.get(url, auth=self._auth, timeout=15, **kwargs)
        resp.raise_for_status()
        return resp

    def _verify_access(self):
        """Verify we can reach the repo."""
        try:
            resp = requests.get(
                f"{_API_BASE}/repositories/{self._workspace}/{self._repo_slug}",
                auth=self._auth, timeout=10,
            )
            if resp.status_code == 404:
                raise RuntimeError(f"Repository {self._workspace}/{self._repo_slug} not found")
            if resp.status_code == 401:
                raise RuntimeError("Bitbucket authentication failed — check BITBUCKET_EMAIL and BITBUCKET_API_TOKEN")
            resp.raise_for_status()
        except requests.ConnectionError as e:
            raise RuntimeError(f"Cannot reach Bitbucket API: {e}") from e

    def _list_directory(self, branch: str, path: str = "") -> List[Dict[str, Any]]:
        """List files/dirs at a path on a branch."""
        entries = []
        url_path = f"src/{branch}/{path}" if path else f"src/{branch}/"
        page_url = f"{_API_BASE}/repositories/{self._workspace}/{self._repo_slug}/{url_path}"

        while page_url:
            resp = requests.get(page_url, auth=self._auth, timeout=15)
            if resp.status_code == 404:
                return []
            resp.raise_for_status()
            data = resp.json()
            entries.extend(data.get("values", []))
            page_url = data.get("next")

        return entries

    def _get_file(self, branch: str, path: str) -> str:
        """Get raw file content from a branch."""
        resp = self._api_get(f"src/{branch}/{path}")
        return resp.text

    # ------------------------------------------------------------------
    # Public API (same interface as before)
    # ------------------------------------------------------------------

    def list_refs(self) -> Dict[str, List[str]]:
        """List branches and tags."""
        branches = []
        tags = []

        # Branches
        url = f"{_API_BASE}/repositories/{self._workspace}/{self._repo_slug}/refs/branches"
        while url:
            resp = requests.get(url, auth=self._auth, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            branches.extend(b["name"] for b in data.get("values", []))
            url = data.get("next")

        # Tags
        url = f"{_API_BASE}/repositories/{self._workspace}/{self._repo_slug}/refs/tags"
        while url:
            resp = requests.get(url, auth=self._auth, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            tags.extend(t["name"] for t in data.get("values", []))
            url = data.get("next")

        if self._environment == "production":
            branches = [b for b in branches if b in ("main", "master")]

        return {"branches": branches, "tags": tags}

    def fetch(self) -> None:
        """Clear cache to force fresh data on next query."""
        with self._lock:
            self._cache.clear()
            self._cache_time.clear()

    def discover_boards(self, branch: str) -> List[Dict[str, Any]]:
        """Scan all board directories on a branch, grouped by product family."""
        # Check cache
        with self._lock:
            if branch in self._cache and (time.time() - self._cache_time.get(branch, 0)) < self._cache_ttl:
                return self._cache[branch]

        boards = self._scan_boards(branch)

        with self._lock:
            self._cache[branch] = boards
            self._cache_time[branch] = time.time()

        return boards

    def discover_board_detail(self, family_name: str, branch: str) -> Dict[str, Any]:
        """Get full details for a product family."""
        boards = self.discover_boards(branch)
        for board in boards:
            if board["family"] == family_name:
                return board
        raise ValueError(f"Board '{family_name}' not found on branch '{branch}'")

    # ------------------------------------------------------------------
    # Board scanning via REST API
    # ------------------------------------------------------------------

    def _find_boards_path(self, branch: str) -> str:
        """Find the boards directory path (current/boards/<vendor>/ layout)."""
        # Try current/boards/
        entries = self._list_directory(branch, "current/boards")
        if entries:
            for entry in entries:
                if entry.get("type") == "commit_directory":
                    # First vendor subdirectory
                    return entry["path"]
            return "current/boards"

        # Fallback: boards/
        entries = self._list_directory(branch, "boards")
        if entries:
            return "boards"

        return ""

    def _scan_boards(self, branch: str) -> List[Dict[str, Any]]:
        """Scan board directories on a branch and group by family."""
        boards_path = self._find_boards_path(branch)
        if not boards_path:
            logger.warning("No boards directory found on branch %s", branch)
            return []

        entries = self._list_directory(branch, boards_path)
        families: Dict[str, Dict[str, Any]] = {}

        for entry in entries:
            if entry.get("type") != "commit_directory":
                continue

            dir_name = entry["path"].split("/")[-1]
            board_yml_path = f"{entry['path']}/board.yml"

            try:
                content = self._get_file(branch, board_yml_path)
                board_data = _parse_board_yml(content)

                family, version = _split_board_name(dir_name)
                if not version:
                    family = dir_name
                    version = ""

                if family not in families:
                    families[family] = {
                        "family": family,
                        "vendor": board_data["vendor"],
                        "revisions": [],
                    }

                families[family]["revisions"].append({
                    "version": version,
                    "ckBoardsName": dir_name,
                    "socs": board_data["socs"],
                })
            except requests.HTTPError:
                # No board.yml in this directory — skip
                continue
            except Exception as e:
                logger.warning("Failed to parse board %s: %s", dir_name, e)

        return sorted(families.values(), key=lambda f: f["family"])
