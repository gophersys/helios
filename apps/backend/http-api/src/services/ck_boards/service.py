"""ck_boards git service — bare clone management, worktree checkout, board parsing.

Maintains a bare git clone of the ck_boards repository and provides
methods to list branches/tags, scan boards, and parse DTS files for
peripheral discovery.
"""

import logging
import os
import re
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Known peripheral compatible strings → type + bus mapping
# ---------------------------------------------------------------------------

_PERIPHERAL_MAP: Dict[str, Dict[str, str]] = {
    "bosch,bmi270": {"type": "accelerometer", "bus": "spi"},
    "bosch,bmi160": {"type": "accelerometer", "bus": "spi"},
    "st,lis2dh": {"type": "accelerometer", "bus": "i2c"},
    "ti,bq25180": {"type": "charger", "bus": "i2c"},
    "ti,bq35100": {"type": "fuel-gauge", "bus": "i2c"},
    "nxp,tca9534a": {"type": "gpio-expander", "bus": "i2c"},
    "pixart,pah8151": {"type": "ppg", "bus": "spi"},
    "melexis,mlx90614": {"type": "ir-temp", "bus": "i2c"},
    "microchip,mcp4017": {"type": "potentiometer", "bus": "i2c"},
    "atmel,at24": {"type": "eeprom", "bus": "i2c"},
    "nordic,nrf-uarte": {"type": "uart", "bus": "uart"},
}


def _classify_peripheral(compatible: str) -> Dict[str, str]:
    """Map a DTS compatible string to a peripheral type and bus."""
    info = _PERIPHERAL_MAP.get(compatible)
    if info:
        return {"compatible": compatible, **info}
    return {"compatible": compatible, "type": "unknown", "bus": "unknown"}


def _parse_dts_compatibles(dts_content: str) -> List[str]:
    """Extract all compatible string values from DTS content."""
    return re.findall(r'compatible\s*=\s*"([^"]+)"', dts_content)


def _parse_board_yml(content: str) -> Dict[str, Any]:
    """Parse a board.yml file into a structured dict."""
    data = yaml.safe_load(content)
    if not isinstance(data, dict):
        raise ValueError("board.yml must be a YAML mapping")
    return {
        "name": data.get("name", ""),
        "socs": data.get("socs", []),
        "revisions": data.get("revisions", []),
        "variants": data.get("variants", []),
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
        """List all branches and tags from the bare repo.

        Returns:
            {"branches": ["main", "release/v2.1", ...], "tags": ["v1.0.0", ...]}
        """
        branches = self._git_list_branches()
        tags = self._git_list_tags()
        return {"branches": branches, "tags": tags}

    def fetch(self) -> None:
        """Fetch latest from remote origin."""
        self._run_git(["fetch", "--prune", "origin"])

    def discover_boards(self, branch: str) -> List[Dict[str, Any]]:
        """Scan all board directories on a branch. Lightweight — no DTS parsing.

        Returns list of:
            {"board": "alpha", "socs": [...], "revisions": [...], "variants": [...]}
        """
        self._validate_ref(branch)
        worktree_path = self._checkout_worktree(branch)
        try:
            return self._scan_boards(worktree_path)
        finally:
            self._remove_worktree(worktree_path)

    def discover_board_detail(self, board_name: str, branch: str) -> Dict[str, Any]:
        """Deep scan of a single board — parses DTS for peripheral manifest.

        Returns:
            {"board": "alpha", "socs": [...], "revisions": [{"name": ..., "peripherals": [...]}], "variants": [...]}
        """
        self._validate_ref(branch)
        worktree_path = self._checkout_worktree(branch)
        try:
            return self._scan_board_detail(worktree_path, board_name)
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
            # Fallback: force remove directory and prune
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
        """Find the boards directory in the worktree."""
        boards_dir = os.path.join(worktree_path, "boards")
        if os.path.isdir(boards_dir):
            return boards_dir
        # Fallback: boards at root level
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
                    "socs": board_data["socs"],
                    "revisions": board_data["revisions"],
                    "variants": board_data["variants"],
                })

        return results

    def _scan_board_detail(self, worktree_path: str, board_name: str) -> Dict[str, Any]:
        """Deep scan a single board with DTS peripheral parsing."""
        boards_dir = self._find_boards_dir(worktree_path)
        board_dir = os.path.join(boards_dir, board_name)
        board_yml = os.path.join(board_dir, "board.yml")

        if not os.path.isdir(board_dir) or not os.path.isfile(board_yml):
            raise ValueError(f"Board '{board_name}' not found on this branch")

        with open(board_yml) as f:
            board_data = _parse_board_yml(f.read())

        # Parse DTS files for each revision directory
        revisions = []
        for rev_name in board_data.get("revisions", []):
            rev_dir = os.path.join(board_dir, rev_name)
            peripherals = []
            if os.path.isdir(rev_dir):
                peripherals = self._parse_revision_dts(rev_dir)
            revisions.append({
                "name": rev_name,
                "peripherals": peripherals,
            })

        return {
            "board": board_data["name"] or board_name,
            "socs": board_data["socs"],
            "revisions": revisions,
            "variants": board_data["variants"],
        }

    def _parse_revision_dts(self, rev_dir: str) -> List[Dict[str, str]]:
        """Parse all DTS files in a revision directory for peripherals."""
        all_compatibles = set()
        for filename in os.listdir(rev_dir):
            if filename.endswith((".dts", ".dtsi", ".overlay")):
                filepath = os.path.join(rev_dir, filename)
                with open(filepath) as f:
                    compatibles = _parse_dts_compatibles(f.read())
                    all_compatibles.update(compatibles)

        return [_classify_peripheral(c) for c in sorted(all_compatibles)]
