"""ck_boards git service — bare clone management, worktree checkout, board parsing.

Maintains a bare git clone of the ck_boards repository and provides
methods to list branches/tags and scan boards for SoC topology.
"""

import logging
import os
import shutil
import subprocess
import uuid
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


def _parse_board_yml(content: str) -> Dict[str, Any]:
    """Parse a board.yml file into a structured dict.

    Zephyr board.yml wraps everything under a top-level 'board:' key:
      board:
        name: alpha_b0
        vendor: corekinect
        socs: [...]
        revision: {revisions: [...]}
    """
    raw = yaml.safe_load(content)
    if not isinstance(raw, dict):
        raise ValueError("board.yml must be a YAML mapping")
    data = raw.get("board", raw)
    socs = data.get("socs", [])
    revision_block = data.get("revision", {})
    revisions = revision_block.get("revisions", []) if isinstance(revision_block, dict) else []
    return {
        "name": data.get("name", ""),
        "vendor": data.get("vendor", ""),
        "socs": [s.get("name", "") for s in socs if isinstance(s, dict)],
        "revisions": [r.get("name", "") for r in revisions if isinstance(r, dict)],
        "variants": [v.get("name", "") for s in socs if isinstance(s, dict) for v in s.get("variants", []) if isinstance(v, dict)],
    }


class CkBoardsService:
    """Service for interacting with the ck_boards bare git repository."""

    def __init__(self, bare_repo_path: str, worktree_base_path: str):
        self._bare_repo = bare_repo_path
        self._worktree_base = worktree_base_path

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_refs(self) -> Dict[str, List[str]]:
        """List all branches and tags from the bare repo."""
        branches = self._git_list_branches()
        tags = self._git_list_tags()
        return {"branches": branches, "tags": tags}

    def fetch(self) -> None:
        """Fetch latest from remote origin."""
        self._run_git(["fetch", "--prune", "origin"])

    def discover_boards(self, branch: str) -> List[Dict[str, Any]]:
        """Scan all board directories on a branch.

        Returns list of:
            {"board": "alpha_b0", "vendor": "corekinect", "socs": [...], "revisions": [...], "variants": [...]}
        """
        self._validate_ref(branch)
        worktree_path = self._checkout_worktree(branch)
        try:
            return self._scan_boards(worktree_path)
        finally:
            self._remove_worktree(worktree_path)

    def discover_board_detail(self, board_name: str, branch: str) -> Dict[str, Any]:
        """Get full details for a single board on a branch.

        Returns same shape as discover_boards but for one board.
        """
        self._validate_ref(branch)
        worktree_path = self._checkout_worktree(branch)
        try:
            boards_dir = self._find_boards_dir(worktree_path)
            board_dir = os.path.join(boards_dir, board_name)
            board_yml = os.path.join(board_dir, "board.yml")

            if not os.path.isdir(board_dir) or not os.path.isfile(board_yml):
                raise ValueError(f"Board '{board_name}' not found on this branch")

            with open(board_yml) as f:
                board_data = _parse_board_yml(f.read())

            return {
                "board": board_data["name"] or board_name,
                "vendor": board_data["vendor"],
                "socs": board_data["socs"],
                "revisions": board_data["revisions"],
                "variants": board_data["variants"],
            }
        finally:
            self._remove_worktree(worktree_path)

    # ------------------------------------------------------------------
    # Git operations
    # ------------------------------------------------------------------

    def _run_git(self, args: List[str], cwd: Optional[str] = None) -> str:
        """Run a git command against the bare repo."""
        cmd = ["git", "--git-dir", self._bare_repo] + args
        result = subprocess.run(
            cmd, capture_output=True, text=True, cwd=cwd, timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
        return result.stdout.strip()

    def _git_list_branches(self) -> List[str]:
        """List branch names (strip refs/heads/ prefix)."""
        output = self._run_git(["for-each-ref", "--format=%(refname:short)", "refs/heads/"])
        return [line for line in output.splitlines() if line]

    def _git_list_tags(self) -> List[str]:
        """List tag names (strip refs/tags/ prefix)."""
        output = self._run_git(["for-each-ref", "--format=%(refname:short)", "refs/tags/"])
        return [line for line in output.splitlines() if line]

    def _validate_ref(self, ref: str) -> None:
        """Check that a ref (branch or tag) exists in the bare repo."""
        branches = self._git_list_branches()
        tags = self._git_list_tags()
        if ref not in branches and ref not in tags:
            raise ValueError(f"Ref '{ref}' not found in ck_boards repository")

    def _checkout_worktree(self, ref: str) -> str:
        """Create a temporary worktree for the given ref."""
        worktree_id = f"{ref.replace('/', '_')}_{uuid.uuid4().hex[:8]}"
        worktree_path = os.path.join(self._worktree_base, worktree_id)
        self._run_git(["worktree", "add", "--detach", worktree_path, ref])
        return worktree_path

    def _remove_worktree(self, worktree_path: str) -> None:
        """Remove a worktree and clean up its directory."""
        try:
            self._run_git(["worktree", "remove", "--force", worktree_path])
        except RuntimeError:
            if os.path.exists(worktree_path):
                shutil.rmtree(worktree_path, ignore_errors=True)
            try:
                self._run_git(["worktree", "prune"])
            except RuntimeError:
                pass

    # ------------------------------------------------------------------
    # Board scanning
    # ------------------------------------------------------------------

    def _find_boards_dir(self, worktree_path: str) -> str:
        """Find the boards directory in the worktree.

        ck_boards layout: current/boards/<vendor>/
        """
        current_boards = os.path.join(worktree_path, "current", "boards")
        if os.path.isdir(current_boards):
            for vendor in os.listdir(current_boards):
                vendor_dir = os.path.join(current_boards, vendor)
                if os.path.isdir(vendor_dir):
                    return vendor_dir
            return current_boards
        boards_dir = os.path.join(worktree_path, "boards")
        if os.path.isdir(boards_dir):
            return boards_dir
        return worktree_path

    def _scan_boards(self, worktree_path: str) -> List[Dict[str, Any]]:
        """Scan all board directories for board.yml files."""
        boards_dir = self._find_boards_dir(worktree_path)
        results = []

        for entry in sorted(os.listdir(boards_dir)):
            board_dir = os.path.join(boards_dir, entry)
            board_yml = os.path.join(board_dir, "board.yml")
            if os.path.isdir(board_dir) and os.path.isfile(board_yml):
                with open(board_yml) as f:
                    board_data = _parse_board_yml(f.read())
                results.append({
                    "board": board_data["name"] or entry,
                    "vendor": board_data["vendor"],
                    "socs": board_data["socs"],
                    "revisions": board_data["revisions"],
                    "variants": board_data["variants"],
                })

        return results
