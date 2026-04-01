"""Repo event trigger service — maps repo events to stage builds.

Abstracted from the event source (webhook or poller). Both produce a RepoEvent,
and this service handles it identically. When webhooks become available, the
poller can be disabled with zero code changes to the trigger logic.

Event sources:
  - Git Poller (now): polls repos via git ls-remote, detects new commits
  - Bitbucket Webhook (future): receives POST from Bitbucket on PR/push events
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.services.database.prisma import get_db_client
from src.services.build_trigger import trigger_stage_build

logger = logging.getLogger(__name__)


# ── Event interface — both webhook and poller produce this ──────────


@dataclass
class RepoEvent:
    """A repo change event. Source-agnostic."""
    repo_slug: str          # "alpha_fw"
    branch: str             # "feature/new-sensor" or "main"
    commit_sha: str | None  # "abc1234"
    event_type: str         # "push" or "merge"
    source: str             # "webhook", "poller", "manual"
    metadata: dict | None = None  # Extra context (PR number, author, etc.)


# ── Core handler — doesn't care about the event source ──────────


def handle_repo_event(event: RepoEvent) -> List[Dict[str, Any]]:
    """Process a repo event and trigger matching stages.

    This is the SINGLE entry point for all trigger sources.
    Returns list of triggered stage results.
    """
    # Map event_type to stage trigger types
    trigger_types = []
    if event.event_type == "push":
        trigger_types = ["pr_push"]
    elif event.event_type == "merge":
        trigger_types = ["pr_merge"]

    if not trigger_types:
        logger.debug("Ignoring event type: %s", event.event_type)
        return []

    db = get_db_client()

    # Find product by repo slug
    product = db.product.find_first(
        where={
            "OR": [
                {"fwRepoSlug": event.repo_slug},
                {"mfgFwRepoSlug": event.repo_slug},
            ],
        },
    )
    if not product:
        logger.info("No product for repo: %s", event.repo_slug)
        return []

    # Find enabled stages matching the trigger type
    stages = db.productstageconfig.find_many(
        where={
            "productId": product.id,
            "enabled": True,
            "triggerTypes": {"hasSome": trigger_types},
        },
    )
    if not stages:
        logger.debug("No matching stages for %s trigger %s", product.name, trigger_types)
        return []

    # Filter by branch
    matching = []
    for stage in stages:
        if not stage.watchBranch or stage.watchBranch == "*":
            matching.append(stage)
        elif stage.watchBranch == event.branch:
            matching.append(stage)
        elif stage.watchBranch.endswith("*") and event.branch.startswith(stage.watchBranch[:-1]):
            matching.append(stage)

    results = []
    for stage in matching:
        logger.info("Triggering %s stage %d (%s) from %s event on %s/%s",
                     product.name, stage.stage, stage.name, event.source,
                     event.repo_slug, event.branch)
        result = trigger_stage_build(product.id, stage.id, event_metadata=event.metadata)
        if result:
            results.append({"stage": stage.stage, "name": stage.name, **result})

    return results


# ── Webhook adapter — parses Bitbucket payload into RepoEvent ──────────


def parse_bitbucket_webhook(event_key: str, payload: Dict[str, Any]) -> RepoEvent | None:
    """Parse a Bitbucket webhook payload into a RepoEvent."""
    event_map = {
        "pullrequest:created": "push",
        "pullrequest:updated": "push",
        "pullrequest:fulfilled": "merge",
        "repo:push": "push",
    }
    event_type = event_map.get(event_key)
    if not event_type:
        return None

    repo_slug = (payload.get("repository") or {}).get("slug")
    if not repo_slug:
        return None

    branch = None
    commit_sha = None

    if "pullrequest" in payload:
        pr = payload["pullrequest"]
        branch = pr.get("source", {}).get("branch", {}).get("name")
        commit_sha = pr.get("source", {}).get("commit", {}).get("hash")
    elif "push" in payload:
        changes = payload.get("push", {}).get("changes", [])
        if changes:
            branch = changes[0].get("new", {}).get("name")
            commit_sha = changes[0].get("new", {}).get("target", {}).get("hash")

    return RepoEvent(
        repo_slug=repo_slug,
        branch=branch or "unknown",
        commit_sha=commit_sha,
        event_type=event_type,
        source="webhook",
        metadata={"event_key": event_key},
    )


# ── Poller adapter — detects new commits via git ls-remote ──────────


def poll_for_changes() -> List[Dict[str, Any]]:
    """Poll repos for new PR commits via Bitbucket REST API.

    Uses Bitbucket API to list open PRs and detect new commits.
    Rich metadata: PR number, title, author, source/target branch.

    Falls back to git ls-remote if Bitbucket API not configured.
    """
    from config import env_config
    from src.services.bitbucket_client import BitbucketClient, parse_pr_metadata

    db = get_db_client()

    # Find products with active pr_push stages
    stages = db.productstageconfig.find_many(
        where={"enabled": True, "triggerTypes": {"has": "pr_push"}},
        include={"product": True},
    )
    if not stages:
        return []

    # Collect unique repo slugs to poll
    repos_to_poll: Dict[str, Any] = {}  # repo_slug → product
    for stage in stages:
        if stage.product and stage.product.fwRepoSlug:
            repos_to_poll[stage.product.fwRepoSlug] = stage.product

    bb = BitbucketClient(
        api_token=env_config.BITBUCKET_API_TOKEN,
        workspace=env_config.BITBUCKET_WORKSPACE,
    )

    results = []

    if bb.is_configured:
        # PR-aware polling via Bitbucket API
        for repo_slug, product in repos_to_poll.items():
            try:
                prs = bb.list_open_prs(repo_slug)
            except Exception as e:
                logger.warning("Failed to list PRs for %s: %s", repo_slug, e)
                continue

            for pr in prs:
                pr_meta = parse_pr_metadata(pr)
                branch = pr_meta["source_branch"]
                commit_sha = pr_meta["source_commit"]

                if not commit_sha:
                    continue

                # Check cache
                cache_key = f"{repo_slug}:pr:{pr_meta['pr_id']}"
                cache_file = f"/tmp/concord_poll_{cache_key.replace(':', '_')}.sha"
                last_sha = None
                try:
                    with open(cache_file) as f:
                        last_sha = f.read().strip()
                except FileNotFoundError:
                    pass

                if commit_sha == last_sha:
                    continue

                logger.info("Poller: PR #%s on %s has new commit %s (was %s)",
                             pr_meta["pr_id"], repo_slug, commit_sha[:7],
                             (last_sha or "none")[:7])

                event = RepoEvent(
                    repo_slug=repo_slug,
                    branch=branch,
                    commit_sha=commit_sha,
                    event_type="push",
                    source="poller",
                    metadata=pr_meta,
                )
                triggered = handle_repo_event(event)
                results.extend(triggered)

                # Update cache
                try:
                    with open(cache_file, "w") as f:
                        f.write(commit_sha)
                except Exception:
                    pass
    else:
        # Fallback: git ls-remote (no PR metadata)
        logger.debug("Bitbucket API not configured — using git ls-remote fallback")
        results = _poll_git_ls_remote(repos_to_poll)

    return results


def _poll_git_ls_remote(repos: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Fallback poller using git ls-remote (no PR metadata)."""
    import base64
    import os
    import stat
    import subprocess

    from config import env_config

    env = dict(os.environ)
    ssh_key_b64 = env_config.BITBUCKET_SSH_KEY
    key_path = None
    if ssh_key_b64:
        key_path = "/tmp/.ssh_poller"
        with open(key_path, "wb") as f:
            f.write(base64.b64decode(ssh_key_b64))
        os.chmod(key_path, stat.S_IRUSR)
        env["GIT_SSH_COMMAND"] = f"ssh -i {key_path} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"

    results = []
    db = get_db_client()

    # Get stages again for branch info
    stages = db.productstageconfig.find_many(
        where={"enabled": True, "triggerTypes": {"has": "pr_push"}},
        include={"product": True},
    )

    polled: Dict[str, str] = {}
    for stage in stages:
        product = stage.product
        if not product or not product.fwRepoSlug:
            continue
        repo_slug = product.fwRepoSlug
        branch = stage.watchBranch or "main"
        cache_key = f"{repo_slug}:{branch}"

        if cache_key not in polled:
            repo_url = f"git@bitbucket.org:corekinect/{repo_slug}.git"
            try:
                proc = subprocess.run(
                    ["git", "ls-remote", repo_url, f"refs/heads/{branch}"],
                    timeout=15, capture_output=True, text=True, env=env,
                )
                if proc.returncode == 0 and proc.stdout.strip():
                    polled[cache_key] = proc.stdout.strip().split()[0]
            except Exception:
                continue

        sha = polled.get(cache_key)
        if not sha:
            continue

        cache_file = f"/tmp/concord_poll_{cache_key.replace(':', '_')}.sha"
        last_sha = None
        try:
            with open(cache_file) as f:
                last_sha = f.read().strip()
        except FileNotFoundError:
            pass

        if sha == last_sha:
            continue

        event = RepoEvent(
            repo_slug=repo_slug, branch=branch, commit_sha=sha,
            event_type="push", source="poller",
        )
        triggered = handle_repo_event(event)
        results.extend(triggered)

        try:
            with open(cache_file, "w") as f:
                f.write(sha)
        except Exception:
            pass

    if key_path:
        try:
            os.unlink(key_path)
        except Exception:
            pass

    return results


# ── Auto-progress — triggers next stage when current passes ──────────


def handle_auto_progress(product_id: str, completed_stage: int) -> Optional[Dict[str, Any]]:
    """Trigger the next stage if it has triggerTypes="auto".

    Called when a validation run passes.
    """
    db = get_db_client()

    next_stage_num = completed_stage + 1
    if next_stage_num > 5:
        return None

    next_config = db.productstageconfig.find_first(
        where={
            "productId": product_id,
            "stage": next_stage_num,
            "enabled": True,
            "triggerTypes": {"has": "auto"},
        },
    )
    if not next_config:
        return None

    logger.info("Auto-progress: stage %d → %d for product %s",
                completed_stage, next_stage_num, product_id)

    return trigger_stage_build(product_id, next_config.id)
