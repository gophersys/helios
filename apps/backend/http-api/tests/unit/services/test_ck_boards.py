"""Tests for the ck_boards git service — bare clone, worktree, board parsing."""

import os
import subprocess
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.services.ck_boards.service import CkBoardsService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_repo(tmp_path):
    """Create a real bare git repo with board.yml files for integration tests."""
    # Create a temporary normal repo, add board files, then clone as bare
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

    # Create alpha board
    alpha_dir = src / "boards" / "alpha"
    alpha_dir.mkdir(parents=True)
    (alpha_dir / "board.yml").write_text(textwrap.dedent("""\
        name: alpha
        socs:
          - nrf52840
          - nrf9151
        revisions:
          - rev1.1
          - rev1.2
        variants:
          - alpha_b0
    """))

    # Create alpha DTS file with compatible strings
    alpha_dts_dir = alpha_dir / "rev1.2"
    alpha_dts_dir.mkdir()
    (alpha_dts_dir / "alpha.dts").write_text(textwrap.dedent("""\
        / {
            bmi270: bmi270@0 {
                compatible = "bosch,bmi270";
                reg = <0>;
                spi-max-frequency = <8000000>;
            };
            bq25180: bq25180@6a {
                compatible = "ti,bq25180";
                reg = <0x6a>;
            };
        };
    """))

    # Create sigma5 board (single-processor)
    sigma_dir = src / "boards" / "sigma5"
    sigma_dir.mkdir(parents=True)
    (sigma_dir / "board.yml").write_text(textwrap.dedent("""\
        name: sigma5
        socs:
          - nrf52840
        revisions:
          - rev1.0
        variants:
          - sigma5_std
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
    worktree_dir = tmp_path / "worktrees"
    worktree_dir.mkdir()
    return CkBoardsService(
        bare_repo_path=str(tmp_repo),
        worktree_base_path=str(worktree_dir),
    )


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
# Board scanning (lightweight — no DTS parsing)
# ---------------------------------------------------------------------------

def test_discover_boards(service):
    """discover_boards returns summary list of all boards on a branch."""
    # Determine the default branch name
    refs = service.list_refs()
    branch = "main" if "main" in refs["branches"] else "master"

    boards = service.discover_boards(branch)
    names = [b["board"] for b in boards]
    assert "alpha" in names
    assert "sigma5" in names

    alpha = next(b for b in boards if b["board"] == "alpha")
    assert set(alpha["socs"]) == {"nrf52840", "nrf9151"}
    assert "rev1.2" in alpha["revisions"]
    assert "alpha_b0" in alpha["variants"]

    sigma = next(b for b in boards if b["board"] == "sigma5")
    assert sigma["socs"] == ["nrf52840"]


def test_discover_boards_invalid_branch(service):
    """discover_boards raises ValueError for a nonexistent branch."""
    with pytest.raises(ValueError, match="not found"):
        service.discover_boards("nonexistent-branch")


# ---------------------------------------------------------------------------
# Single board detail (with DTS parsing)
# ---------------------------------------------------------------------------

def test_discover_board_detail(service):
    """discover_board_detail parses DTS files for peripheral manifest."""
    refs = service.list_refs()
    branch = "main" if "main" in refs["branches"] else "master"

    detail = service.discover_board_detail("alpha", branch)
    assert detail["board"] == "alpha"
    assert set(detail["socs"]) == {"nrf52840", "nrf9151"}
    assert len(detail["revisions"]) > 0

    rev12 = next((r for r in detail["revisions"] if r["name"] == "rev1.2"), None)
    assert rev12 is not None
    peripherals = rev12["peripherals"]
    compatibles = [p["compatible"] for p in peripherals]
    assert "bosch,bmi270" in compatibles
    assert "ti,bq25180" in compatibles


def test_discover_board_detail_not_found(service):
    """discover_board_detail raises ValueError for unknown board."""
    refs = service.list_refs()
    branch = "main" if "main" in refs["branches"] else "master"

    with pytest.raises(ValueError, match="not found"):
        service.discover_board_detail("nonexistent-board", branch)


# ---------------------------------------------------------------------------
# DTS compatible string parser
# ---------------------------------------------------------------------------

def test_parse_dts_compatible_strings():
    """_parse_dts_compatibles extracts compatible strings from DTS content."""
    from src.services.ck_boards.service import _parse_dts_compatibles

    dts = textwrap.dedent("""\
        / {
            bmi270: bmi270@0 {
                compatible = "bosch,bmi270";
                reg = <0>;
            };
            bq35100: bq35100@55 {
                compatible = "ti,bq35100";
                reg = <0x55>;
            };
        };
    """)
    compatibles = _parse_dts_compatibles(dts)
    assert "bosch,bmi270" in compatibles
    assert "ti,bq35100" in compatibles


def test_parse_dts_no_compatibles():
    """_parse_dts_compatibles returns empty list for DTS without compatible."""
    from src.services.ck_boards.service import _parse_dts_compatibles

    dts = "/ { model = \"test\"; };"
    assert _parse_dts_compatibles(dts) == []


# ---------------------------------------------------------------------------
# Peripheral type classification
# ---------------------------------------------------------------------------

def test_classify_peripheral():
    """_classify_peripheral maps known compatible strings to type and bus."""
    from src.services.ck_boards.service import _classify_peripheral

    accel = _classify_peripheral("bosch,bmi270")
    assert accel["type"] == "accelerometer"
    assert accel["bus"] == "spi"

    charger = _classify_peripheral("ti,bq25180")
    assert charger["type"] == "charger"
    assert charger["bus"] == "i2c"

    unknown = _classify_peripheral("vendor,unknown-part")
    assert unknown["type"] == "unknown"


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


# ---------------------------------------------------------------------------
# board.yml parsing
# ---------------------------------------------------------------------------

def test_parse_board_yml():
    """_parse_board_yml extracts board metadata from YAML content."""
    from src.services.ck_boards.service import _parse_board_yml

    content = textwrap.dedent("""\
        name: alpha
        socs:
          - nrf52840
          - nrf9151
        revisions:
          - rev1.1
          - rev1.2
        variants:
          - alpha_b0
    """)
    result = _parse_board_yml(content)
    assert result["name"] == "alpha"
    assert result["socs"] == ["nrf52840", "nrf9151"]
    assert result["revisions"] == ["rev1.1", "rev1.2"]
    assert result["variants"] == ["alpha_b0"]


def test_parse_board_yml_minimal():
    """_parse_board_yml handles minimal board.yml with only name and socs."""
    from src.services.ck_boards.service import _parse_board_yml

    content = textwrap.dedent("""\
        name: theta
        socs:
          - nrf52840
    """)
    result = _parse_board_yml(content)
    assert result["name"] == "theta"
    assert result["socs"] == ["nrf52840"]
    assert result["revisions"] == []
    assert result["variants"] == []
