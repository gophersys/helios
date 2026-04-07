"""Build trigger dispatcher — posts RepoEvents to ``POST /v2/builds/events``.

The HTTP API routes events through handle_repo_event() which matches
enabled stages by trigger type + watch branch, then creates BuildRuns
with the proper recipe, build matrix, and pipeline context.

The HTTP session is injectable for testing.
"""

import logging
from typing import Callable, Optional

import requests

from models import PRInfo, WatchTarget

log = logging.getLogger("git-poller")

SessionFactory = Callable[[], requests.Session]


def _default_session_factory() -> requests.Session:
    """Create a requests.Session with SSL warnings suppressed.

    Suppression is needed for self-signed certificates used in dev and staging
    environments.

    Returns:
        A new requests.Session instance.
    """
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    return requests.Session()


class BuildTrigger:
    """Dispatch repo events to the Concord HTTP API."""

    def __init__(
        self,
        api_url: str,
        api_key: str,
        session_factory: SessionFactory = _default_session_factory,
    ) -> None:
        self._api_url = api_url.rstrip("/")
        self._api_key = api_key
        self._session_factory = session_factory

    def trigger_build(
        self,
        target: WatchTarget,
        commit_sha: str,
        trigger_type: str,
        pr_info: Optional[PRInfo] = None,
    ) -> bool:
        """POST a RepoEvent for *target*.

        Returns True on success, False on any error.
        """
        if not self._api_key:
            log.warning(
                "BuildTrigger: CONCORD_API_KEY not set, skipping trigger for %s",
                target.repo_slug,
            )
            return False

        payload = self._build_event_payload(target, commit_sha, trigger_type, pr_info)
        url = f"{self._api_url}/v2/builds/events"
        headers = {
            "Authorization": f"ApiKey {self._api_key}",
            "Content-Type": "application/json",
        }

        log.info(
            "BuildTrigger: %s @ %s (stage=%d type=%s board=%s)",
            target.repo_slug,
            commit_sha[:8],
            target.stage,
            trigger_type,
            target.board,
        )

        session = self._session_factory()
        try:
            resp = session.post(url, json=payload, headers=headers, timeout=30, verify=False)
        except requests.RequestException as exc:
            log.error(
                "BuildTrigger: request error for %s: %s",
                target.repo_slug,
                exc,
            )
            return False

        if resp.status_code >= 400:
            log.error(
                "BuildTrigger: %d for %s: %s",
                resp.status_code,
                target.repo_slug,
                resp.text[:200],
            )
            return False

        try:
            data = resp.json()
        except Exception:
            log.info("BuildTrigger: triggered %s (no JSON body)", target.repo_slug)
            return True

        if data.get("errors") and any(e.get("message") for e in data["errors"]):
            log.error("BuildTrigger: API error for %s: %s", target.repo_slug, data["errors"])
            return False

        triggered = (data.get("data") or {}).get("triggered", 0)
        stages = (data.get("data") or {}).get("stages", [])
        stage_names = ", ".join(s.get("name", "?") for s in stages) if stages else "none"
        log.info("BuildTrigger: %d stage(s) triggered for %s: %s", triggered, target.repo_slug, stage_names)
        return True

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    @staticmethod
    def _build_event_payload(
        target: WatchTarget,
        commit_sha: str,
        trigger_type: str,
        pr_info: Optional[PRInfo],
    ) -> dict:
        """Build a RepoEvent-shaped payload for POST /v2/builds/events."""
        # Map poller trigger types to RepoEvent event_type
        event_type = "push" if trigger_type == "pr_push" else "merge"

        metadata: dict = {
            "target_branch": target.watch_branch,
            "source": "poller",
            "stage": target.stage,
            "board": target.board,
        }

        if pr_info is not None:
            metadata["pr_number"] = pr_info.pr_id
            metadata["pr_title"] = pr_info.title
            metadata["pr_author"] = pr_info.author

        return {
            "repoSlug": target.repo_slug,
            "branch": pr_info.source_branch if pr_info else target.watch_branch,
            "commitSha": commit_sha,
            "eventType": event_type,
            "source": "poller",
            "metadata": metadata,
        }
