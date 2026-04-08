"""Tests for services/ck_boards/service.py — board parsing, name splitting, scanning."""

from __future__ import annotations

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# _split_board_name
# ---------------------------------------------------------------------------

class TestSplitBoardName:
    """Tests for _split_board_name()."""

    def test_standard_format(self):
        """Splits alpha_b0 into family and revision."""
        from src.services.ck_boards.service import _split_board_name

        family, rev = _split_board_name("alpha_b0")
        assert family == "alpha"
        assert rev == "b0"

    def test_multi_part_family(self):
        """Splits sigma5_c0 preserving multi-part family name."""
        from src.services.ck_boards.service import _split_board_name

        family, rev = _split_board_name("sigma5_c0")
        assert family == "sigma5"
        assert rev == "c0"

    def test_complex_family_name(self):
        """Splits iwsck_a1 correctly."""
        from src.services.ck_boards.service import _split_board_name

        family, rev = _split_board_name("iwsck_a1")
        assert family == "iwsck"
        assert rev == "a1"

    def test_no_revision_pattern(self):
        """Returns full name as family with empty revision when no match."""
        from src.services.ck_boards.service import _split_board_name

        family, rev = _split_board_name("standalone")
        assert family == "standalone"
        assert rev == ""

    def test_multiple_underscores(self):
        """Handles names with multiple underscores."""
        from src.services.ck_boards.service import _split_board_name

        family, rev = _split_board_name("my_custom_board_a2")
        assert family == "my_custom_board"
        assert rev == "a2"


# ---------------------------------------------------------------------------
# _parse_board_yml
# ---------------------------------------------------------------------------

class TestParseBoardYml:
    """Tests for _parse_board_yml()."""

    def test_standard_board_yml(self):
        """Parses a standard board.yml with socs and revisions."""
        from src.services.ck_boards.service import _parse_board_yml

        content = """
board:
  name: alpha_b0
  vendor: corekinect
  socs:
    - name: nrf52840
    - name: nrf9151
  revision:
    revisions:
      - name: b0
"""
        result = _parse_board_yml(content)

        assert result["name"] == "alpha_b0"
        assert result["vendor"] == "corekinect"
        assert result["socs"] == ["nrf52840", "nrf9151"]
        assert result["revisions"] == ["b0"]

    def test_board_with_variants(self):
        """Parses board.yml with SoC variants."""
        from src.services.ck_boards.service import _parse_board_yml

        content = """
board:
  name: test_board
  vendor: testco
  socs:
    - name: nrf52840
      variants:
        - name: nrf52840dk
        - name: nrf52840dongle
"""
        result = _parse_board_yml(content)

        assert result["variants"] == ["nrf52840dk", "nrf52840dongle"]

    def test_board_without_revision(self):
        """Parses board.yml without revision block."""
        from src.services.ck_boards.service import _parse_board_yml

        content = """
board:
  name: simple
  vendor: acme
  socs:
    - name: esp32
"""
        result = _parse_board_yml(content)

        assert result["name"] == "simple"
        assert result["revisions"] == []

    def test_raises_on_non_dict(self):
        """Raises ValueError for non-dict YAML."""
        from src.services.ck_boards.service import _parse_board_yml

        with pytest.raises(ValueError, match="must be a YAML mapping"):
            _parse_board_yml("just a string")

    def test_bare_dict_without_board_key(self):
        """Parses dict without board key using top-level data."""
        from src.services.ck_boards.service import _parse_board_yml

        content = """
name: flat_board
vendor: flatco
socs:
  - name: nrf9160
"""
        result = _parse_board_yml(content)

        assert result["name"] == "flat_board"
        assert result["vendor"] == "flatco"

    def test_empty_socs(self):
        """Handles board with no socs."""
        from src.services.ck_boards.service import _parse_board_yml

        content = """
board:
  name: no_soc
  vendor: nobody
  socs: []
"""
        result = _parse_board_yml(content)

        assert result["socs"] == []
        assert result["variants"] == []


# ---------------------------------------------------------------------------
# CkBoardsService — list_refs
# ---------------------------------------------------------------------------

class TestCkBoardsServiceListRefs:
    """Tests for CkBoardsService.list_refs() with mocked git."""

    @patch("src.services.ck_boards.service.subprocess.run")
    def test_list_refs_production_filters_branches(self, mock_run):
        """Production mode filters branches to only main/master."""
        from src.services.ck_boards.service import CkBoardsService

        # Mock subprocess for clone and git operations
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as tmpdir:
            bare_repo = os.path.join(tmpdir, "ck_boards.git")
            os.makedirs(bare_repo)

            with patch.object(CkBoardsService, "__init__", lambda self, **kw: None):
                svc = CkBoardsService.__new__(CkBoardsService)
                svc._bare_repo = bare_repo
                svc._git_env = {}
                svc._environment = "production"
                svc._ready = True

                with patch.object(svc, "_git_list_branches", return_value=["main", "develop", "feature/x"]):
                    with patch.object(svc, "_git_list_tags", return_value=["v1.0"]):
                        refs = svc.list_refs()

                assert refs["branches"] == ["main"]
                assert refs["tags"] == ["v1.0"]

    @patch("src.services.ck_boards.service.subprocess.run")
    def test_list_refs_development_shows_all(self, mock_run):
        """Development mode shows all branches."""
        from src.services.ck_boards.service import CkBoardsService

        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as tmpdir:
            bare_repo = os.path.join(tmpdir, "ck_boards.git")
            os.makedirs(bare_repo)

            with patch.object(CkBoardsService, "__init__", lambda self, **kw: None):
                svc = CkBoardsService.__new__(CkBoardsService)
                svc._bare_repo = bare_repo
                svc._git_env = {}
                svc._environment = "development"
                svc._ready = True

                with patch.object(svc, "_git_list_branches", return_value=["main", "develop", "feature/x"]):
                    with patch.object(svc, "_git_list_tags", return_value=[]):
                        refs = svc.list_refs()

                assert refs["branches"] == ["main", "develop", "feature/x"]


# ---------------------------------------------------------------------------
# CkBoardsService — _scan_boards_in_dir
# ---------------------------------------------------------------------------

class TestScanBoardsInDir:
    """Tests for CkBoardsService._scan_boards_in_dir() with real filesystem."""

    def test_scan_discovers_families(self):
        """Scans board directories and groups them by family."""
        from src.services.ck_boards.service import CkBoardsService

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create board directories with board.yml
            for name, yml in [
                ("alpha_a0", "board:\n  name: alpha_a0\n  vendor: ck\n  socs:\n    - name: nrf52840\n"),
                ("alpha_b0", "board:\n  name: alpha_b0\n  vendor: ck\n  socs:\n    - name: nrf52840\n    - name: nrf9151\n"),
                ("sigma5_c0", "board:\n  name: sigma5_c0\n  vendor: ck\n  socs:\n    - name: nrf54l15\n"),
            ]:
                board_dir = os.path.join(tmpdir, name)
                os.makedirs(board_dir)
                with open(os.path.join(board_dir, "board.yml"), "w") as f:
                    f.write(yml)

            with patch.object(CkBoardsService, "__init__", lambda self, **kw: None):
                svc = CkBoardsService.__new__(CkBoardsService)
                families = svc._scan_boards_in_dir(tmpdir)

            assert "alpha" in families
            assert "sigma5" in families
            assert len(families["alpha"]["revisions"]) == 2
            assert families["alpha"]["vendor"] == "ck"

    def test_scan_skips_non_board_dirs(self):
        """Skips directories without board.yml."""
        from src.services.ck_boards.service import CkBoardsService

        with tempfile.TemporaryDirectory() as tmpdir:
            # Directory without board.yml
            os.makedirs(os.path.join(tmpdir, "not_a_board"))
            # File (not a directory)
            with open(os.path.join(tmpdir, "readme.txt"), "w") as f:
                f.write("not a board")

            with patch.object(CkBoardsService, "__init__", lambda self, **kw: None):
                svc = CkBoardsService.__new__(CkBoardsService)
                families = svc._scan_boards_in_dir(tmpdir)

            assert len(families) == 0

    def test_scan_handles_malformed_yml(self):
        """Malformed board.yml files are skipped with warning."""
        from src.services.ck_boards.service import CkBoardsService

        with tempfile.TemporaryDirectory() as tmpdir:
            board_dir = os.path.join(tmpdir, "bad_board_a0")
            os.makedirs(board_dir)
            with open(os.path.join(board_dir, "board.yml"), "w") as f:
                f.write("this is not valid yaml: [")

            with patch.object(CkBoardsService, "__init__", lambda self, **kw: None):
                svc = CkBoardsService.__new__(CkBoardsService)
                families = svc._scan_boards_in_dir(tmpdir)

            # Should be empty due to parse error
            assert len(families) == 0


# ---------------------------------------------------------------------------
# CkBoardsService — _find_boards_dir
# ---------------------------------------------------------------------------

class TestFindBoardsDir:
    """Tests for CkBoardsService._find_boards_dir()."""

    def test_finds_current_boards_vendor(self):
        """Finds boards at current/boards/<vendor>/ layout."""
        from src.services.ck_boards.service import CkBoardsService

        with tempfile.TemporaryDirectory() as tmpdir:
            vendor_dir = os.path.join(tmpdir, "current", "boards", "corekinect")
            os.makedirs(vendor_dir)

            with patch.object(CkBoardsService, "__init__", lambda self, **kw: None):
                svc = CkBoardsService.__new__(CkBoardsService)
                result = svc._find_boards_dir(tmpdir)

            assert result == vendor_dir

    def test_falls_back_to_boards_dir(self):
        """Falls back to boards/ directory."""
        from src.services.ck_boards.service import CkBoardsService

        with tempfile.TemporaryDirectory() as tmpdir:
            boards_dir = os.path.join(tmpdir, "boards")
            os.makedirs(boards_dir)

            with patch.object(CkBoardsService, "__init__", lambda self, **kw: None):
                svc = CkBoardsService.__new__(CkBoardsService)
                result = svc._find_boards_dir(tmpdir)

            assert result == boards_dir

    def test_falls_back_to_worktree_root(self):
        """Falls back to worktree root when no boards directory found."""
        from src.services.ck_boards.service import CkBoardsService

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(CkBoardsService, "__init__", lambda self, **kw: None):
                svc = CkBoardsService.__new__(CkBoardsService)
                result = svc._find_boards_dir(tmpdir)

            assert result == tmpdir


# ---------------------------------------------------------------------------
# CkBoardsService — _validate_ref
# ---------------------------------------------------------------------------

class TestValidateRef:
    """Tests for CkBoardsService._validate_ref()."""

    def test_valid_branch(self):
        """Known branch passes validation."""
        from src.services.ck_boards.service import CkBoardsService

        with patch.object(CkBoardsService, "__init__", lambda self, **kw: None):
            svc = CkBoardsService.__new__(CkBoardsService)
            svc._bare_repo = "/fake/repo.git"
            svc._git_env = {}

            with patch.object(svc, "_git_list_branches", return_value=["main", "develop"]):
                with patch.object(svc, "_git_list_tags", return_value=[]):
                    svc._validate_ref("main")  # Should not raise

    def test_valid_tag(self):
        """Known tag passes validation."""
        from src.services.ck_boards.service import CkBoardsService

        with patch.object(CkBoardsService, "__init__", lambda self, **kw: None):
            svc = CkBoardsService.__new__(CkBoardsService)
            svc._bare_repo = "/fake/repo.git"
            svc._git_env = {}

            with patch.object(svc, "_git_list_branches", return_value=[]):
                with patch.object(svc, "_git_list_tags", return_value=["v1.0"]):
                    svc._validate_ref("v1.0")  # Should not raise

    def test_unknown_ref_raises(self):
        """Unknown ref raises ValueError."""
        from src.services.ck_boards.service import CkBoardsService

        with patch.object(CkBoardsService, "__init__", lambda self, **kw: None):
            svc = CkBoardsService.__new__(CkBoardsService)
            svc._bare_repo = "/fake/repo.git"
            svc._git_env = {}

            with patch.object(svc, "_git_list_branches", return_value=["main"]):
                with patch.object(svc, "_git_list_tags", return_value=[]):
                    with pytest.raises(ValueError, match="not found"):
                        svc._validate_ref("nonexistent")
