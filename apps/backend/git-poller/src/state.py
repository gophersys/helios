"""Persistent poller state — branch SHAs and tracked PR metadata.

State is stored in the Concord HTTP API (PostgreSQL via PollCache model)
and cached in-memory for fast reads. Writes are synchronous (write-through).

The in-memory cache mirrors the on-disk structure of the old file-based
implementation so all callers remain unchanged:

    {
        "alpha_fw": {
            "branches": {
                "concord-main": "abc123def456"
            },
            "prs": {
                "42": {"sha": "def456789", "source": "feature/new-sensor"},
                "43": {"sha": "ghi789abc", "source": "fix/power-issue"}
            }
        }
    }
"""

import logging
from typing import Optional

import requests

log = logging.getLogger("git-poller")

_POLLER_STATE_PATH = "/v2/system/poller-state"


class PollerState:
    """API-backed poller state with in-memory write-through cache."""

    def __init__(
        self,
        api_url: str,
        api_key: str,
        session: Optional[requests.Session] = None,
    ) -> None:
        self._api_url = api_url.rstrip("/")
        self._api_key = api_key
        self._session = session or requests.Session()
        # Nested dict: repo_slug -> {"branches": {...}, "prs": {...}}
        self._data: dict = {}
        self.load()

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _headers(self) -> dict:
        return {"Authorization": f"ApiKey {self._api_key}"}

    def _url(self, path: str = "") -> str:
        return f"{self._api_url}{_POLLER_STATE_PATH}{path}"

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Load all cache entries from the API into memory.

        Silent no-op if the API is unreachable — starts with empty state.
        """
        try:
            resp = self._session.get(self._url(), headers=self._headers(), timeout=10)
            resp.raise_for_status()
            entries = resp.json().get("data", [])
            self._data = {}
            for entry in entries:
                repo = entry["repoSlug"]
                if repo not in self._data:
                    self._data[repo] = {"branches": {}, "prs": {}}
                if entry["type"] == "branch":
                    self._data[repo]["branches"][entry["refId"]] = entry["commitSha"]
                elif entry["type"] == "pr":
                    meta = entry.get("metadata") or {}
                    self._data[repo]["prs"][entry["refId"]] = {
                        "sha": entry["commitSha"],
                        "source": meta.get("source_branch", ""),
                    }
            log.debug("State loaded from API (%d entries)", len(entries))
        except Exception as exc:
            log.warning("Failed to load state from API: %s — starting fresh", exc)
            self._data = {}

    def save(self) -> None:
        """No-op: writes are immediate (write-through to API)."""

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _repo(self, repo_slug: str) -> dict:
        if repo_slug not in self._data:
            self._data[repo_slug] = {"branches": {}, "prs": {}}
        return self._data[repo_slug]

    def _api_upsert(
        self,
        repo_slug: str,
        entry_type: str,
        ref_id: str,
        commit_sha: str,
        metadata: Optional[dict] = None,
    ) -> None:
        """PUT a single entry to the API. Logs a warning on failure."""
        try:
            resp = self._session.put(
                self._url(),
                headers=self._headers(),
                json={
                    "repoSlug": repo_slug,
                    "type": entry_type,
                    "refId": ref_id,
                    "commitSha": commit_sha,
                    "metadata": metadata,
                },
                timeout=10,
            )
            resp.raise_for_status()
        except Exception as exc:
            log.warning(
                "Failed to persist state for %s/%s/%s: %s",
                repo_slug,
                entry_type,
                ref_id,
                exc,
            )

    def _api_delete(self, repo_slug: str, entry_type: str, ref_id: str) -> None:
        """DELETE a single entry from the API. Logs a warning on failure."""
        try:
            resp = self._session.delete(
                self._url(),
                headers=self._headers(),
                params={"repoSlug": repo_slug, "type": entry_type, "refId": ref_id},
                timeout=10,
            )
            # 404 is acceptable — entry may have already been removed
            if resp.status_code not in (200, 404):
                resp.raise_for_status()
        except Exception as exc:
            log.warning(
                "Failed to delete state for %s/%s/%s: %s",
                repo_slug,
                entry_type,
                ref_id,
                exc,
            )

    # ------------------------------------------------------------------
    # Branch tracking
    # ------------------------------------------------------------------

    def get_branch_sha(self, repo_slug: str, branch: str) -> Optional[str]:
        return self._repo(repo_slug)["branches"].get(branch)

    def set_branch_sha(self, repo_slug: str, branch: str, sha: str) -> None:
        self._repo(repo_slug)["branches"][branch] = sha
        self._api_upsert(repo_slug, "branch", branch, sha)

    # ------------------------------------------------------------------
    # PR tracking
    # ------------------------------------------------------------------

    def get_pr_sha(self, repo_slug: str, pr_id: int) -> Optional[str]:
        entry = self._repo(repo_slug)["prs"].get(str(pr_id))
        return entry["sha"] if entry else None

    def get_pr_source_branch(self, repo_slug: str, pr_id: int) -> Optional[str]:
        entry = self._repo(repo_slug)["prs"].get(str(pr_id))
        return entry["source"] if entry else None

    def set_pr_sha(
        self,
        repo_slug: str,
        pr_id: int,
        sha: str,
        source_branch: str,
    ) -> None:
        self._repo(repo_slug)["prs"][str(pr_id)] = {
            "sha": sha,
            "source": source_branch,
        }
        self._api_upsert(
            repo_slug,
            "pr",
            str(pr_id),
            sha,
            metadata={"source_branch": source_branch},
        )

    def get_tracked_pr_ids(self, repo_slug: str) -> set[int]:
        return {int(k) for k in self._repo(repo_slug)["prs"]}

    def remove_pr(self, repo_slug: str, pr_id: int) -> None:
        self._repo(repo_slug)["prs"].pop(str(pr_id), None)
        self._api_delete(repo_slug, "pr", str(pr_id))
