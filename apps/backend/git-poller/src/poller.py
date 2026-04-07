"""Main poller — orchestrates one poll cycle.

``poll_once()`` groups watch targets by repo, checks branches and PRs,
deduplicates against seen commits, and dispatches build triggers.

``run()`` loops ``poll_once()`` every ``config.poll_interval`` seconds until
a shutdown event is set.
"""

import logging
import threading
from collections import defaultdict
from typing import Optional

from branch_watcher import BranchWatcher
from config import GitPollerConfig
from discovery import ProductDiscovery
from models import PRInfo, WatchTarget
from pr_watcher import PRWatcher
from state import PollerState
from trigger import BuildTrigger

log = logging.getLogger("git-poller")


class GitPoller:
    """Orchestrate polling cycles and build triggers."""

    def __init__(self, config: GitPollerConfig) -> None:
        self._config = config
        self._shutdown = threading.Event()

        self._discovery = ProductDiscovery(
            api_url=config.concord_api_url,
            api_key=config.concord_api_key,
            cache_ttl=config.product_cache_ttl,
        )
        self._branch_watcher = BranchWatcher(ssh_key_path=config.ssh_key_path)
        self._pr_watcher = PRWatcher(
            workspace=config.bitbucket_workspace,
            email=config.bitbucket_email,
            api_token=config.bitbucket_api_token,
        )
        self._trigger = BuildTrigger(
            api_url=config.concord_api_url,
            api_key=config.concord_api_key,
        )
        self._state = PollerState(
            api_url=config.concord_api_url,
            api_key=config.concord_api_key,
        )

        # Dedup set: (repo_slug, commit_sha, stage, trigger_type)
        self._triggered: set[tuple] = set()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def signal_shutdown(self) -> None:
        """Request a graceful stop."""
        self._shutdown.set()

    def poll_once(self) -> None:
        """Execute one full poll cycle across all watch targets."""
        targets = self._discovery.get_watch_targets()
        if not targets:
            log.debug("Poller: no watch targets, skipping cycle")
            return

        # Group by repo_slug so we can process branches and PRs repo-at-a-time
        by_repo: dict[str, list[WatchTarget]] = defaultdict(list)
        for t in targets:
            by_repo[t.repo_slug].append(t)

        for repo_slug, repo_targets in by_repo.items():
            self._process_repo(repo_slug, repo_targets)

        self._state.save()

    def run(self, on_first_success=None) -> None:
        """Main loop — calls ``poll_once()`` every ``poll_interval`` seconds.

        Args:
            on_first_success: Optional callable invoked after the first poll
                cycle completes without raising. Used to signal readiness.
        """
        log.info(
            "Poller: starting (interval=%ds, cache_ttl=%ds)",
            self._config.poll_interval,
            self._config.product_cache_ttl,
        )

        _first_success_fired = False
        while not self._shutdown.is_set():
            try:
                self.poll_once()
                if not _first_success_fired and on_first_success is not None:
                    on_first_success()
                    _first_success_fired = True
            except Exception as exc:
                log.exception("Poller: unhandled error in poll cycle: %s", exc)

            self._shutdown.wait(timeout=self._config.poll_interval)

        log.info("Poller: shutdown complete")

    # ------------------------------------------------------------------
    # Per-repo processing
    # ------------------------------------------------------------------

    def _process_repo(
        self,
        repo_slug: str,
        targets: list[WatchTarget],
    ) -> None:
        """Process all watch targets for a single repo in one pass."""

        # Partition targets by trigger type
        merge_targets = [t for t in targets if "pr_merge" in t.trigger_types]
        push_targets = [t for t in targets if "pr_push" in t.trigger_types]

        # ── Branch tracking (pr_merge) ────────────────────────────────
        # Collect the unique (ssh_url, branch) pairs we need to check
        checked_branches: dict[tuple[str, str], Optional[str]] = {}

        for target in merge_targets:
            key = (target.ssh_url, target.watch_branch)
            if key not in checked_branches:
                sha = self._branch_watcher.get_branch_sha(
                    target.ssh_url, target.watch_branch
                )
                checked_branches[key] = sha

        for target in merge_targets:
            key = (target.ssh_url, target.watch_branch)
            current_sha = checked_branches.get(key)
            if not current_sha:
                continue
            self._check_branch_merge(target, current_sha)

        # ── PR tracking (pr_push) ─────────────────────────────────────
        if push_targets:
            # All push targets for a repo share the same ssh_url / workspace
            # but may watch different branches.
            by_branch: dict[str, list[WatchTarget]] = defaultdict(list)
            for t in push_targets:
                by_branch[t.watch_branch].append(t)

            # Also grab the current branch SHA for merged-PR detection
            # (we need it per watch_branch)
            branch_shas: dict[str, Optional[str]] = {}
            for branch, branch_targets in by_branch.items():
                ssh_url = branch_targets[0].ssh_url
                key = (ssh_url, branch)
                if key in checked_branches:
                    branch_shas[branch] = checked_branches[key]
                else:
                    sha = self._branch_watcher.get_branch_sha(ssh_url, branch)
                    branch_shas[branch] = sha
                    checked_branches[key] = sha

            for branch, branch_targets in by_branch.items():
                open_prs = self._pr_watcher.get_open_prs(
                    repo_slug=repo_slug,
                    target_branch=branch,
                )
                for target in branch_targets:
                    self._check_prs(
                        target,
                        open_prs,
                        current_branch_sha=branch_shas.get(branch),
                    )

    # ------------------------------------------------------------------
    # Branch-merge logic
    # ------------------------------------------------------------------

    def _check_branch_merge(
        self,
        target: WatchTarget,
        current_sha: str,
    ) -> None:
        repo_slug = target.repo_slug
        branch = target.watch_branch
        stored_sha = self._state.get_branch_sha(repo_slug, branch)

        if stored_sha is None:
            # First time we've seen this branch — record SHA, no trigger
            log.info(
                "Poller: [%s/%s] initial SHA %s",
                repo_slug,
                branch,
                current_sha[:8],
            )
            self._state.set_branch_sha(repo_slug, branch, current_sha)
            return

        if current_sha == stored_sha:
            log.debug(
                "Poller: [%s/%s] no change (%s)",
                repo_slug,
                branch,
                current_sha[:8],
            )
            return

        log.info(
            "Poller: [%s/%s] new commit %s -> %s",
            repo_slug,
            branch,
            stored_sha[:8],
            current_sha[:8],
        )

        if self._fire_trigger(target, current_sha, "pr_merge", pr_info=None):
            self._state.set_branch_sha(repo_slug, branch, current_sha)

    # ------------------------------------------------------------------
    # PR-push logic
    # ------------------------------------------------------------------

    def _check_prs(
        self,
        target: WatchTarget,
        open_prs: list[PRInfo],
        current_branch_sha: Optional[str],
    ) -> None:
        repo_slug = target.repo_slug
        open_ids = {pr.pr_id for pr in open_prs}
        tracked_ids = self._state.get_tracked_pr_ids(repo_slug)

        # Detect newly closed PRs
        closed_ids = tracked_ids - open_ids
        for pr_id in closed_ids:
            stored_source = self._state.get_pr_source_branch(repo_slug, pr_id)
            log.info(
                "Poller: [%s] PR #%d closed (source=%s)",
                repo_slug,
                pr_id,
                stored_source,
            )
            self._state.remove_pr(repo_slug, pr_id)

        # Process open PRs
        for pr in open_prs:
            stored_sha = self._state.get_pr_sha(repo_slug, pr.pr_id)
            is_new = stored_sha is None
            is_updated = stored_sha is not None and stored_sha != pr.head_sha

            if is_new:
                log.info(
                    "Poller: [%s] new PR #%d (%s -> %s) @ %s",
                    repo_slug,
                    pr.pr_id,
                    pr.source_branch,
                    pr.target_branch,
                    pr.head_sha[:8] if pr.head_sha else "?",
                )
            elif is_updated:
                log.info(
                    "Poller: [%s] PR #%d updated (%s -> %s)",
                    repo_slug,
                    pr.pr_id,
                    stored_sha[:8] if stored_sha else "?",
                    pr.head_sha[:8] if pr.head_sha else "?",
                )

            if (is_new or is_updated) and pr.head_sha:
                if self._fire_trigger(target, pr.head_sha, "pr_push", pr_info=pr):
                    self._state.set_pr_sha(
                        repo_slug, pr.pr_id, pr.head_sha, pr.source_branch
                    )

    # ------------------------------------------------------------------
    # Deduplication + dispatch
    # ------------------------------------------------------------------

    def _fire_trigger(
        self,
        target: WatchTarget,
        commit_sha: str,
        trigger_type: str,
        pr_info: Optional[PRInfo],
    ) -> bool:
        dedup_key = (target.repo_slug, commit_sha, target.stage, trigger_type)
        if dedup_key in self._triggered:
            log.debug(
                "Poller: skipping duplicate trigger %s @ %s (stage=%d type=%s)",
                target.repo_slug,
                commit_sha[:8],
                target.stage,
                trigger_type,
            )
            return True  # Already sent — treat as success for state update

        success = self._trigger.trigger_build(
            target=target,
            commit_sha=commit_sha,
            trigger_type=trigger_type,
            pr_info=pr_info,
        )

        if success:
            self._triggered.add(dedup_key)

        return success
