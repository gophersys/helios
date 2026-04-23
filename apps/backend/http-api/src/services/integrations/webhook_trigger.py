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

from config.env import env_config
from src.services.database.prisma import get_db_client
from src.services.builds.trigger import trigger_stage_build
from src.services.integrations.bitbucket_client import BitbucketClient, parse_pr_metadata

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

    # Find enabled stages matching the trigger type (only BUILD_SERVICE stages)
    stages = db.productstageconfig.find_many(
        where={
            "productId": product.id,
            "enabled": True,
            "assetSources": {"has": "BUILD_SERVICE"},
            "triggerTypes": {"hasSome": trigger_types},
        },
    )
    if not stages:
        logger.debug("No matching stages for %s trigger %s", product.name, trigger_types)
        return []

    # Filter by branch — for PR events, match against the TARGET branch
    # (the branch the PR aims to merge into, e.g. "concord-main")
    match_branch = event.branch  # default: source branch
    if event.metadata and event.metadata.get("target_branch"):
        match_branch = event.metadata["target_branch"]

    matching = []
    for stage in stages:
        if not stage.watchBranch or stage.watchBranch == "*":
            matching.append(stage)
        elif stage.watchBranch == match_branch:
            matching.append(stage)
        elif stage.watchBranch.endswith("*") and match_branch.startswith(stage.watchBranch[:-1]):
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
    """Poll Bitbucket for non-draft PRs targeting watched branches.

    For each product with pr_push-triggered stages:
    1. List open PRs via Bitbucket REST API
    2. Skip draft PRs
    3. Match PR target branch to stage watchBranch
    4. Detect new commits (compare with cached SHA)
    5. Fire RepoEvent with PR metadata → triggers matching stages
    """
    bb = BitbucketClient(
        api_token=env_config.BITBUCKET_API_TOKEN,
        email=env_config.BITBUCKET_EMAIL,
        workspace=env_config.BITBUCKET_WORKSPACE,
    )
    if not bb.is_configured:
        return []

    db = get_db_client()

    # Find all enabled stages with pr_push trigger, grouped by product
    stages = db.productstageconfig.find_many(
        where={"enabled": True, "triggerTypes": {"has": "pr_push"}},
        include={"product": True},
    )
    if not stages:
        return []

    # Build a map: repo_slug → { product, watched_branches }
    repo_stages: Dict[str, Dict] = {}
    for stage in stages:
        product = stage.product
        if not product or not product.fwRepoSlug:
            continue
        slug = product.fwRepoSlug
        if slug not in repo_stages:
            repo_stages[slug] = {"product": product, "watched_branches": set()}
        branch = stage.watchBranch or "*"
        repo_stages[slug]["watched_branches"].add(branch)

    results = []

    for repo_slug, info in repo_stages.items():
        watched = info["watched_branches"]

        try:
            prs = bb.list_open_prs(repo_slug)
        except Exception as e:
            logger.warning("Poller: failed to list PRs for %s: %s", repo_slug, e)
            continue

        for pr in prs:
            # Skip draft PRs
            if pr.get("draft", False):
                continue

            pr_meta = parse_pr_metadata(pr)
            target_branch = pr_meta["target_branch"]
            source_branch = pr_meta["source_branch"]
            commit_sha = pr_meta["source_commit"]

            if not commit_sha or not target_branch:
                continue

            # Match PR target branch against watched branches
            matched = False
            if "*" in watched:
                matched = True
            elif target_branch in watched:
                matched = True
            else:
                for pattern in watched:
                    if pattern.endswith("*") and target_branch.startswith(pattern[:-1]):
                        matched = True
                        break

            if not matched:
                continue

            # Check if this PR has a new commit since last poll (DB-backed cache)
            pr_id = pr_meta["pr_id"]
            cached = db.pollcache.find_first(
                where={"repoSlug": repo_slug, "prId": pr_id},
            )
            if cached and cached.commitSha == commit_sha:
                continue  # No new commits

            logger.info("Poller: PR #%d '%s' on %s (%s → %s) new commit %s",
                        pr_meta["pr_id"], pr_meta["pr_title"][:40],
                        repo_slug, source_branch, target_branch, commit_sha[:7])

            event = RepoEvent(
                repo_slug=repo_slug,
                branch=source_branch,
                commit_sha=commit_sha,
                event_type="push",
                source="poller",
                metadata=pr_meta,
            )
            triggered = handle_repo_event(event)
            results.extend(triggered)

            # Cache the SHA in database (survives pod restarts)
            try:
                db.pollcache.upsert(
                    where={"repoSlug_prId": {"repoSlug": repo_slug, "prId": pr_id}},
                    data={
                        "create": {"repoSlug": repo_slug, "prId": pr_id, "commitSha": commit_sha},
                        "update": {"commitSha": commit_sha},
                    },
                )
            except Exception as e:
                logger.warning("Failed to update poll cache for %s PR #%d: %s", repo_slug, pr_id, e)

    return results




# ── Auto-progress — triggers next stage when current passes ──────────


def handle_auto_progress(product_id: str, completed_stage: int) -> Optional[Dict[str, Any]]:
    """Trigger the next stage if it has "auto" in triggerTypes.

    Called when a validation run passes.
    """
    return None  # Disabled: auto-progress turned off (not deleted)

    db = get_db_client()

    next_stage_num = completed_stage + 1
    if next_stage_num > 5:
        return None

    next_config = db.productstageconfig.find_first(
        where={
            "productId": product_id,
            "stage": next_stage_num,
            "enabled": True,
            "triggerTypes": {"has": "auto"},  # Prisma array contains query
        },
    )
    if not next_config:
        return None

    logger.info("Auto-progress: stage %d → %d for product %s",
                completed_stage, next_stage_num, product_id)

    return trigger_stage_build(product_id, next_config.id)
