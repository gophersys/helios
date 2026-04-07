"""Stage-aware product discovery.

Queries ``GET /v2/products`` from the Concord API and converts the response
into a list of :class:`WatchTarget` objects — one per enabled stage config
that has at least one trigger type (``pr_push`` or ``pr_merge``).

The response is cached for ``cache_ttl`` seconds to avoid hammering the API
on every 5-second poll cycle.
"""

import logging
import time
from typing import Optional

import requests

from models import WatchTarget

# Suppress SSL warnings for self-signed certs in dev/staging
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

log = logging.getLogger("git-poller")

_VALID_TRIGGER_TYPES = {"pr_push", "pr_merge"}


def _parse_watch_targets(products: list[dict]) -> list[WatchTarget]:
    """Convert a list of product API objects into WatchTargets.

    Each product may have multiple stage configs.  Only stages that are
    *enabled* and carry at least one recognised trigger type are included.
    """
    targets: list[WatchTarget] = []

    for product in products:
        if not product.get("active", True):
            continue

        product_id = product.get("id", "")
        repo_slug = product.get("fwRepoSlug") or product.get("slug", "")
        ssh_url = product.get("repoSshUrl", "")

        if not ssh_url or not repo_slug:
            continue

        # Build revision lookup from product.revisions[]
        revisions = product.get("revisions") or []
        rev_map = {r.get("id", ""): r.get("ckBoardsName", "") for r in revisions if isinstance(r, dict) and r.get("id")}
        # Also build by version for fallback
        rev_by_version = {r.get("version", ""): r.get("ckBoardsName", "") for r in revisions if isinstance(r, dict)}
        # Default board from buildConfig
        default_board = ""
        build_config = product.get("buildConfig")
        if isinstance(build_config, dict):
            default_board = build_config.get("board", "")

        stage_configs: list[dict] = product.get("stageConfigs", []) or []

        for sc in stage_configs:
            if not sc.get("enabled", False):
                continue

            trigger_types: list[str] = [
                t for t in (sc.get("triggerTypes") or [])
                if t in _VALID_TRIGGER_TYPES
            ]
            if not trigger_types:
                continue

            watch_branch = sc.get("watchBranch") or "concord-main"

            # Resolve board name: boardRevision object → revisionId lookup → buildConfig fallback
            board_revision = sc.get("boardRevision") or {}
            board = board_revision.get("ckBoardsName", "")
            if not board:
                rev_id = sc.get("boardRevisionId", "")
                board = rev_map.get(rev_id, "")
            if not board:
                board = default_board

            stage_number = sc.get("stage") or sc.get("stageNumber") or 0

            targets.append(
                WatchTarget(
                    product_id=product_id,
                    repo_slug=repo_slug,
                    ssh_url=ssh_url,
                    board=board,
                    stage=int(stage_number),
                    watch_branch=watch_branch,
                    trigger_types=trigger_types,
                )
            )

    return targets


class ProductDiscovery:
    """Fetch and cache watch targets from the Concord products API."""

    def __init__(self, api_url: str, api_key: str, cache_ttl: int = 60) -> None:
        self._api_url = api_url.rstrip("/")
        self._api_key = api_key
        self._cache_ttl = cache_ttl
        self._cached: list[WatchTarget] = []
        self._cached_at: float = 0.0

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def get_watch_targets(self) -> list[WatchTarget]:
        """Return watch targets, refreshing from API when cache is stale."""
        now = time.monotonic()
        if self._cached and (now - self._cached_at) < self._cache_ttl:
            return self._cached

        targets = self._fetch()
        if targets is not None:
            self._cached = targets
            self._cached_at = now
            log.info(
                "Discovery: %d watch target(s) loaded from API",
                len(self._cached),
            )
        elif not self._cached:
            log.warning("Discovery: no watch targets available")

        return self._cached

    def invalidate_cache(self) -> None:
        """Force a fresh fetch on the next call."""
        self._cached = []
        self._cached_at = 0.0

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _fetch(self) -> Optional[list[WatchTarget]]:
        """Fetch and parse watch targets from GET /v2/products.

        Returns:
            A list of WatchTarget objects on success, or None if the request
            fails or the API key is not configured.
        """
        if not self._api_key:
            log.warning("Discovery: CONCORD_API_KEY not set, skipping fetch")
            return None

        url = f"{self._api_url}/v2/products"
        headers = {
            "Authorization": f"ApiKey {self._api_key}",
            "Content-Type": "application/json",
        }

        try:
            resp = requests.get(url, headers=headers, timeout=30, verify=False)

            if resp.status_code >= 400:
                log.error(
                    "Discovery: GET /v2/products returned %d: %s",
                    resp.status_code,
                    resp.text[:200],
                )
                return None

            data = resp.json()
            # Concord API wraps: {"data": {"data": [...], "pagination": {...}}}
            inner = data.get("data", {})
            products: list[dict] = (
                inner.get("data", []) if isinstance(inner, dict) else inner
            )

            return _parse_watch_targets(products)

        except requests.RequestException as exc:
            log.error("Discovery: request failed: %s", exc)
            return None
        except Exception as exc:
            log.exception("Discovery: unexpected error: %s", exc)
            return None
