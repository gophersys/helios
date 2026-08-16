"""Shared data types for the git poller."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class WatchTarget:
    """One enabled stage config to be polled.

    A single repo may yield multiple WatchTargets — one per enabled stage
    that has at least one trigger type configured.
    """

    product_id: str
    repo_slug: str
    ssh_url: str
    board: str          # ckBoardsName from the stage's boardRevision
    stage: int          # stage number (1-5)
    watch_branch: str
    trigger_types: list[str]  # subset of ["pr_push", "pr_merge"]


@dataclass
class PRInfo:
    """Metadata for a single open Bitbucket pull request."""

    pr_id: int
    title: str
    source_branch: str
    target_branch: str
    head_sha: str
    author: str = ""
