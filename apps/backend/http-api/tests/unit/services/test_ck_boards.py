"""Tests for the ck_boards git service — bare clone, worktree, board parsing."""

import os
import subprocess
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.services.ck_boards.service import CkBoardsService, _split_board_name, _parse_board_yml


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_repo(tmp_path):
    """Create a real bare git repo with board.yml files for integration tests.

    Directory layout mirrors the real ck_boards repo:
        current/boards/corekinect/alpha_a0/board.yml
        current/boards/corekinect/alpha_b0/board.yml
        current/boards/corekinect/sigma5_c0/board.yml
    """
    src = tmp_path / "src_repo"
    src.mkdir()
    subprocess.run(["git", "init", str(src)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(src), "config", "user.email", "test@test.com"],
        check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(src), "config", "user.name", "Test"],
        check=True, capture_output=True,
    )

    vendor_dir = src / "current" / "boards" / "corekinect"
    vendor_dir.mkdir(parents=True)

    # alpha_a0
    (vendor_dir / "alpha_a0").mkdir()
    (vendor_dir / "alpha_a0" / "board.yml").write_text(textwrap.dedent("""\
        board:
          name: alpha_a0
          vendor: corekinect
          socs:
            - name: nrf9160
            - name: nrf52840
          revision:
            revisions: []
    """))

    # alpha_b0
    (vendor_dir / "alpha_b0").mkdir()
    (vendor_dir / "alpha_b0" / "board.yml").write_text(textwrap.dedent("""\
        board:
          name: alpha_b0
          vendor: corekinect
          socs:
            - name: nrf9151
            - name: nrf52840
          revision:
            revisions: []
    """))

    # sigma5_c0
    (vendor_dir / "sigma5_c0").mkdir()
    (vendor_dir / "sigma5_c0" / "board.yml").write_text(textwrap.dedent("""\
        board:
          name: sigma5_c0
          vendor: corekinect
          socs:
            - name: nrf52840
          revision:
            revisions: []
    """))

    # Commit everything
    subprocess.run(["git", "-C", str(src), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(src), "commit", "-m", "initial"],
        check=True, capture_output=True,
    )

    # Create a second branch
    subprocess.run(
        ["git", "-C", str(src), "branch", "release/v2.1"],
        check=True, capture_output=True,
    )

    # Create a tag
    subprocess.run(
        ["git", "-C", str(src), "tag", "v1.0.0"],
        check=True, capture_output=True,
    )

    # Clone as bare
    bare = tmp_path / "ck_boards.git"
    subprocess.run(
        ["git", "clone", "--bare", str(src), str(bare)],
        check=True, capture_output=True,
    )

    return bare


@pytest.fixture
def service(tmp_repo, tmp_path):
    """Create a CkBoardsService pointed at the test bare repo."""
    base_path = tmp_path / "service_base"
    base_path.mkdir()

    # Symlink the bare repo to where the service expects it
    ck_boards_git = base_path / "ck_boards.git"
    ck_boards_git.symlink_to(tmp_repo)

    return CkBoardsService(
        repo_url=str(tmp_repo),
        base_path=str(base_path),
        ssh_key_b64="",
        fetch_interval=0,  # Don't start background fetch
    )


# ---------------------------------------------------------------------------
# _split_board_name helper
# ---------------------------------------------------------------------------

def test_split_board_name_standard():
    """Standard {family}_{rev} names split correctly."""
    assert _split_board_name("alpha_a0") == ("alpha", "a0")
    assert _split_board_name("alpha_b0") == ("alpha", "b0")
    assert _split_board_name("sigma5_c0") == ("sigma5", "c0")
    assert _split_board_name("iwsck_a1") == ("iwsck", "a1")


def test_split_board_name_no_revision():
    """Names without revision pattern return full name as family."""
    assert _split_board_name("standalone") == ("standalone", "")
    assert _split_board_name("no_match_here") == ("no_match_here", "")


def test_split_board_name_underscore_in_family():
    """Family names with underscores still split on the last letter+digit pattern."""
    assert _split_board_name("my_board_b0") == ("my_board", "b0")


# ---------------------------------------------------------------------------
# _parse_board_yml
# ---------------------------------------------------------------------------

def test_parse_board_yml_zephyr_format():
    """Parses Zephyr-style board.yml with nested 'board:' key."""
    content = textwrap.dedent("""\
        board:
          name: alpha_b0
          vendor: corekinect
          socs:
            - name: nrf9151
            - name: nrf52840
          revision:
            revisions:
              - name: rev1.2
    """)
    result = _parse_board_yml(content)
    assert result["name"] == "alpha_b0"
    assert result["vendor"] == "corekinect"
    assert result["socs"] == ["nrf9151", "nrf52840"]
    assert result["revisions"] == ["rev1.2"]


def test_parse_board_yml_flat_format():
    """Parses flat-style board.yml without 'board:' wrapper."""
    content = textwrap.dedent("""\
        name: theta_c0
        vendor: corekinect
        socs:
          - name: nrf52840
    """)
    result = _parse_board_yml(content)
    assert result["name"] == "theta_c0"
    assert result["socs"] == ["nrf52840"]
    assert result["revisions"] == []


def test_parse_board_yml_with_variants():
    """Variants are extracted from socs[].variants[]."""
    content = textwrap.dedent("""\
        board:
          name: alpha_b0
          vendor: corekinect
          socs:
            - name: nrf52840
              variants:
                - name: debug
                - name: release
    """)
    result = _parse_board_yml(content)
    assert result["variants"] == ["debug", "release"]


# ---------------------------------------------------------------------------
# Branch / tag listing
# ---------------------------------------------------------------------------

def test_list_branches(service):
    """list_refs returns branches and tags from the bare repo."""
    refs = service.list_refs()
    assert "main" in refs["branches"] or "master" in refs["branches"]
    assert "release/v2.1" in refs["branches"]
    assert "v1.0.0" in refs["tags"]


# ---------------------------------------------------------------------------
# Board scanning — returns grouped families
# ---------------------------------------------------------------------------

def test_discover_boards(service):
    """discover_boards returns family-grouped list of boards."""
    refs = service.list_refs()
    branch = "main" if "main" in refs["branches"] else "master"

    families = service.discover_boards(branch)
    family_names = [f["family"] for f in families]
    assert "alpha" in family_names
    assert "sigma5" in family_names

    alpha = next(f for f in families if f["family"] == "alpha")
    assert alpha["vendor"] == "corekinect"
    assert len(alpha["revisions"]) == 2

    rev_names = [r["ckBoardsName"] for r in alpha["revisions"]]
    assert "alpha_a0" in rev_names
    assert "alpha_b0" in rev_names

    # Check SoCs on a revision
    b0 = next(r for r in alpha["revisions"] if r["ckBoardsName"] == "alpha_b0")
    assert set(b0["socs"]) == {"nrf9151", "nrf52840"}

    sigma = next(f for f in families if f["family"] == "sigma5")
    assert len(sigma["revisions"]) == 1
    assert sigma["revisions"][0]["socs"] == ["nrf52840"]


def test_discover_boards_invalid_branch(service):
    """discover_boards raises ValueError for a nonexistent branch."""
    with pytest.raises(ValueError, match="not found"):
        service.discover_boards("nonexistent-branch")


# ---------------------------------------------------------------------------
# Single board detail
# ---------------------------------------------------------------------------

def test_discover_board_detail(service):
    """discover_board_detail returns detail for a single product family."""
    refs = service.list_refs()
    branch = "main" if "main" in refs["branches"] else "master"

    detail = service.discover_board_detail("alpha", branch)
    assert detail["family"] == "alpha"
    assert detail["vendor"] == "corekinect"
    assert len(detail["revisions"]) == 2


def test_discover_board_detail_not_found(service):
    """discover_board_detail raises ValueError for unknown family."""
    refs = service.list_refs()
    branch = "main" if "main" in refs["branches"] else "master"

    with pytest.raises(ValueError, match="not found"):
        service.discover_board_detail("nonexistent-board", branch)


# ---------------------------------------------------------------------------
# Worktree cleanup
# ---------------------------------------------------------------------------

def test_worktree_cleanup(service):
    """Worktrees are cleaned up after use."""
    refs = service.list_refs()
    branch = "main" if "main" in refs["branches"] else "master"

    service.discover_boards(branch)
    # After the call, worktree directory should be cleaned up
    worktree_entries = list(Path(service._worktree_base).iterdir()) if Path(service._worktree_base).exists() else []
    assert len(worktree_entries) == 0
