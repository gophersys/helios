"""PR watcher — polls Bitbucket Cloud REST API for open pull requests.

Uses Basic auth (``email:api_token``) as required by Bitbucket Cloud.
Handles pagination automatically by following the ``next`` link in each
response page until no more pages remain.

The HTTP session is injectable so tests can provide a mock without network
access.
"""

import logging
from dataclasses import dataclass
from typing import Callable, Optional

import requests  # type: ignore[import-untyped]
from requests.auth import HTTPBasicAuth  # type: ignore[import-untyped]

from models import PRInfo

log = logging.getLogger("git-poller")

# Type alias for the session factory so tests can inject a fake.
SessionFactory = Callable[[], requests.Session]


def _default_session_factory() -> requests.Session:
    """Create a plain requests.Session used as the default session factory.

    Returns:
        A new requests.Session instance with no extra configuration.
    """
    s = requests.Session()
    return s


_BITBUCKET_API_BASE = "https://api.bitbucket.org/2.0"


class PRWatcher:
    """Fetch open pull requests from Bitbucket Cloud."""

    def __init__(
        self,
        workspace: str,
        email: str,
        api_token: str,
        session_factory: SessionFactory = _default_session_factory,
    ) -> None:
        self._workspace = workspace
        self._auth = HTTPBasicAuth(email, api_token)
        self._session_factory = session_factory

    def get_open_prs(
        self, repo_slug: str, target_branch: str
    ) -> list[PRInfo]:
        """Return all open PRs targeting *target_branch* in *repo_slug*.

        Follows pagination automatically.  Returns an empty list on any error.
        """
        url = (
            f"{_BITBUCKET_API_BASE}/repositories"
            f"/{self._workspace}/{repo_slug}/pullrequests"
            "?state=OPEN"
        )
        session = self._session_factory()
        results: list[PRInfo] = []

        while url:
            try:
                resp = session.get(url, auth=self._auth, timeout=30)
            except requests.RequestException as exc:
                log.error("PRWatcher: request error for %s: %s", repo_slug, exc)
                break

            if resp.status_code == 401:
                log.error(
                    "PRWatcher: 401 Unauthorized for %s — check BITBUCKET_EMAIL "
                    "and BITBUCKET_API_TOKEN",
                    repo_slug,
                )
                break
            if resp.status_code >= 400:
                log.error(
                    "PRWatcher: Bitbucket API %d for %s: %s",
                    resp.status_code,
                    repo_slug,
                    resp.text[:200],
                )
                break

            try:
                data = resp.json()
            except Exception as exc:
                log.error("PRWatcher: failed to parse JSON for %s: %s", repo_slug, exc)
                break

            for pr in data.get("values", []):
                info = _parse_pr(pr)
                if info is None:
                    continue
                if info.target_branch != target_branch:
                    continue
                results.append(info)

            # Follow pagination link if present
            url = data.get("next")  # type: ignore[assignment]

        return results


# ------------------------------------------------------------------
# Private helpers
# ------------------------------------------------------------------

def _parse_pr(pr: dict) -> Optional[PRInfo]:
    """Parse a single PR object from the Bitbucket API response."""
    try:
        source = pr.get("source") or {}
        destination = pr.get("destination") or {}
        author = pr.get("author") or {}

        pr_id = int(pr["id"])
        title = pr.get("title", "")
        source_branch = (source.get("branch") or {}).get("name", "")
        target_branch = (destination.get("branch") or {}).get("name", "")
        head_sha = (source.get("commit") or {}).get("hash", "")
        author_display = author.get("display_name", "")

        return PRInfo(
            pr_id=pr_id,
            title=title,
            source_branch=source_branch,
            target_branch=target_branch,
            head_sha=head_sha,
            author=author_display,
        )
    except (KeyError, TypeError, ValueError) as exc:
        log.warning("PRWatcher: could not parse PR object: %s — %s", exc, pr)
        return None
