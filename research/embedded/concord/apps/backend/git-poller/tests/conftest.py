"""Shared fixtures for git-poller tests."""

import pytest

from models import WatchTarget, PRInfo


@pytest.fixture
def watch_target():
    return WatchTarget(
        product_id="prod_abc123",
        repo_slug="alpha_fw",
        ssh_url="git@bitbucket.org:corekinect/alpha_fw.git",
        board="alpha_b0",
        stage=5,
        watch_branch="concord-main",
        trigger_types=["pr_merge", "pr_push"],
    )


@pytest.fixture
def pr_info():
    return PRInfo(
        pr_id=42,
        title="feat: new sensor support",
        source_branch="feature/new-sensor",
        target_branch="concord-main",
        head_sha="def456789abc",
        author="developer",
    )
