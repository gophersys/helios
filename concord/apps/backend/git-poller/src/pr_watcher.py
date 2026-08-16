"""PR watcher — polls Bitbucket Cloud REST API for open pull requests.

Uses Basic auth (``email:api_token``) as required by Bitbucket Cloud.
Handles pagination automatically by following the ``next`` link in each
response page until no more pages remain.

The HTTP session is injectable so tests can provide a mock without network
access.
"""

import logging
import time
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

    # Shared backoff state — when rate-limited, skip API calls until cooldown expires
    _rate_limit_until: float = 0.0
    _backoff_seconds: float = 30.0

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
    ) -> Optional[list[PRInfo]]:
        """Return all open PRs targeting *target_branch* in *repo_slug*.

        Returns None when rate-limited or on transient errors — callers
        should preserve their previous state rather than treating None as
        "no PRs exist".  Returns an empty list only when the API confirms
        there are genuinely no matching PRs.
        """
        # If we're in a backoff window, skip the API call entirely
        if time.monotonic() < PRWatcher._rate_limit_until:
            remaining = PRWatcher._rate_limit_until - time.monotonic()
            log.debug("PRWatcher: rate-limit backoff active for %s (%.0fs remaining)", repo_slug, remaining)
            return None

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
                return None

            if resp.status_code == 401:
                log.error(
                    "PRWatcher: 401 Unauthorized for %s — check BITBUCKET_EMAIL "
                    "and BITBUCKET_API_TOKEN",
                    repo_slug,
                )
                return None
            if resp.status_code == 429:
                # Exponential backoff: 30s → 60s → 120s, capped at 300s
                PRWatcher._backoff_seconds = min(PRWatcher._backoff_seconds * 2, 300)
                PRWatcher._rate_limit_until = time.monotonic() + PRWatcher._backoff_seconds
                log.warning(
                    "PRWatcher: rate-limited for %s — backing off %.0fs",
                    repo_slug,
                    PRWatcher._backoff_seconds,
                )
                return None
            if resp.status_code >= 400:
                log.error(
                    "PRWatcher: Bitbucket API %d for %s: %s",
                    resp.status_code,
                    repo_slug,
                    resp.text[:200],
                )
                return None

            # Successful response — reset backoff
            PRWatcher._backoff_seconds = 30.0

            try:
                data = resp.json()
            except Exception as exc:
                log.error("PRWatcher: failed to parse JSON for %s: %s", repo_slug, exc)
                return None

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
