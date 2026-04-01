"""Bitbucket REST API client — reads PRs, branches, commits.

Used by the Bitbucket poller to detect PR changes with rich metadata.
Authenticates via API token (Basic auth: email + token).

Bitbucket deprecated App Passwords in Sept 2025 in favor of API tokens.
API tokens use Basic auth: (email, token).
"""

import logging
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

API_BASE = "https://api.bitbucket.org/2.0"


class BitbucketClient:
    """Client for Bitbucket REST API v2."""

    def __init__(self, api_token: str, email: str = "", workspace: str = "corekinect"):
        self._auth = (email, api_token) if api_token else None
        self._workspace = workspace

    @property
    def is_configured(self) -> bool:
        return self._auth is not None and bool(self._auth[1])

    def _get(self, path: str, params: Optional[Dict] = None) -> Optional[Dict]:
        if not self._auth:
            return None
        url = f"{API_BASE}{path}"
        try:
            resp = requests.get(url, auth=self._auth, params=params, timeout=15)
            if resp.status_code == 200:
                return resp.json()
            logger.warning("Bitbucket API %s returned %d", path, resp.status_code)
            return None
        except Exception as e:
            logger.warning("Bitbucket API error: %s", e)
            return None

    def list_open_prs(self, repo_slug: str) -> List[Dict[str, Any]]:
        """List open pull requests for a repo."""
        data = self._get(
            f"/repositories/{self._workspace}/{repo_slug}/pullrequests",
            params={"state": "OPEN", "pagelen": 50},
        )
        return data.get("values", []) if data else []

    def get_pr(self, repo_slug: str, pr_id: int) -> Optional[Dict]:
        return self._get(f"/repositories/{self._workspace}/{repo_slug}/pullrequests/{pr_id}")

    def list_branches(self, repo_slug: str) -> List[Dict]:
        """List branches with latest commit."""
        data = self._get(
            f"/repositories/{self._workspace}/{repo_slug}/refs/branches",
            params={"pagelen": 100},
        )
        return data.get("values", []) if data else []

    def get_branch_head(self, repo_slug: str, branch: str) -> Optional[str]:
        """Get the latest commit SHA for a branch."""
        branches = self.list_branches(repo_slug)
        for b in branches:
            if b.get("name") == branch:
                return b.get("target", {}).get("hash")
        return None

    def list_commits(self, repo_slug: str, branch: str, limit: int = 5) -> List[Dict]:
        """List recent commits on a branch."""
        data = self._get(
            f"/repositories/{self._workspace}/{repo_slug}/commits/{branch}",
            params={"pagelen": limit},
        )
        return data.get("values", []) if data else []


def parse_pr_metadata(pr: Dict) -> Dict[str, Any]:
    """Extract useful metadata from a Bitbucket PR object."""
    source = pr.get("source", {})
    destination = pr.get("destination", {})
    author = pr.get("author", {})

    return {
        "pr_id": pr.get("id"),
        "pr_title": pr.get("title", ""),
        "pr_author": author.get("display_name") or author.get("nickname", ""),
        "pr_state": pr.get("state", "OPEN"),
        "source_branch": source.get("branch", {}).get("name", ""),
        "target_branch": destination.get("branch", {}).get("name", ""),
        "source_commit": source.get("commit", {}).get("hash", ""),
        "pr_url": pr.get("links", {}).get("html", {}).get("href", ""),
    }
