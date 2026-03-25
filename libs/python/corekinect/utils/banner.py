"""
Build metadata banner for Concord services.

Prints a formatted startup banner with version, git, build, and runtime info.
Metadata is injected via Docker build args → ENV at image build time.
Falls back to local git/runtime detection when running outside Docker.

Usage:
    from corekinect.utils.banner import print_banner
    print_banner("concord-http-api")
"""

import os
import platform
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


# ── Build metadata (populated from env vars set at Docker build time) ──

@dataclass
class BuildInfo:
    service: str = "unknown"
    version: str = "dev"
    environment: str = "development"
    git_commit: str = "unknown"
    git_branch: str = "unknown"
    git_dirty: bool = False
    build_time: str = "unknown"
    build_host: str = "unknown"
    python_version: str = ""
    node_version: str = ""
    arch: str = ""
    os_info: str = ""
    extras: dict = field(default_factory=dict)

    @property
    def commit_short(self) -> str:
        return self.git_commit[:7] if len(self.git_commit) > 7 else self.git_commit

    @property
    def commit_display(self) -> str:
        parts = [self.commit_short]
        if self.git_branch and self.git_branch != "unknown":
            parts.append(f"({self.git_branch})")
        if self.git_dirty:
            parts.append("[dirty]")
        return " ".join(parts)

    @property
    def runtime_display(self) -> str:
        parts = []
        if self.python_version:
            parts.append(f"Python {self.python_version}")
        if self.node_version:
            parts.append(f"Node {self.node_version}")
        if self.arch:
            parts.append(self.arch)
        return " \u00b7 ".join(parts)

    @property
    def build_display(self) -> str:
        parts = []
        if self.build_time and self.build_time != "unknown":
            # Try to make it human-readable
            try:
                dt = datetime.fromisoformat(self.build_time.replace("Z", "+00:00"))
                parts.append(dt.strftime("%Y-%m-%d %H:%M:%S"))
            except (ValueError, AttributeError):
                parts.append(self.build_time)
        else:
            parts.append("just now")
        if self.build_host and self.build_host != "unknown":
            parts.append(f"on {self.build_host}")
        return " ".join(parts)


def _run(cmd: str) -> str:
    """Run a shell command and return stdout, or empty string on failure."""
    try:
        result = subprocess.run(
            cmd.split(), capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""


def _detect_os() -> str:
    """Detect OS description."""
    # Try /etc/os-release first (Linux)
    try:
        with open("/etc/os-release") as f:
            for line in f:
                if line.startswith("PRETTY_NAME="):
                    return line.split("=", 1)[1].strip().strip('"')
    except FileNotFoundError:
        pass
    return platform.platform()


def collect(service: str, **extras) -> BuildInfo:
    """Collect build metadata from environment and runtime."""
    info = BuildInfo(service=service)

    # From Docker build args (injected as ENV)
    info.version = os.getenv("APP_VERSION", "dev")
    info.environment = os.getenv("ENVIRONMENT", "development")
    info.git_commit = os.getenv("GIT_COMMIT", "")
    info.git_branch = os.getenv("GIT_BRANCH", "")
    info.git_dirty = os.getenv("GIT_DIRTY", "false").lower() in ("true", "1", "yes")
    info.build_time = os.getenv("BUILD_TIME", "")
    info.build_host = os.getenv("BUILD_HOST", "")

    # Fallback: detect from local git if env vars missing
    if not info.git_commit:
        info.git_commit = _run("git rev-parse --short HEAD") or "unknown"
    if not info.git_branch:
        info.git_branch = _run("git rev-parse --abbrev-ref HEAD") or "unknown"
    if not info.git_dirty and not os.getenv("GIT_DIRTY"):
        dirty_output = _run("git status --porcelain")
        info.git_dirty = bool(dirty_output)
    if not info.build_time:
        info.build_time = datetime.now(timezone.utc).isoformat()
    if not info.build_host:
        info.build_host = platform.node()

    # Runtime detection
    info.python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    info.node_version = _run("node --version").lstrip("v")
    info.arch = f"{platform.machine()}"
    info.os_info = _detect_os()

    info.extras = extras
    return info


# ── Banner formatting ──

_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_CYAN = "\033[36m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_WHITE = "\033[97m"
_RED = "\033[31m"
_MAGENTA = "\033[35m"
_BG_DARK = "\033[48;5;236m"

_ENV_COLORS = {
    "production": _RED,
    "staging": _YELLOW,
    "development": _GREEN,
    "local": _CYAN,
}


def _colorize(use_color: bool) -> dict:
    """Return color codes or empty strings based on use_color flag."""
    if use_color:
        return {
            "reset": _RESET, "bold": _BOLD, "dim": _DIM,
            "cyan": _CYAN, "green": _GREEN, "yellow": _YELLOW,
            "white": _WHITE, "red": _RED, "magenta": _MAGENTA,
        }
    return {k: "" for k in ["reset", "bold", "dim", "cyan", "green", "yellow", "white", "red", "magenta"]}


def format_banner(info: BuildInfo, color: bool = True) -> str:
    """Format build info into a box banner string."""
    c = _colorize(color)

    env_color = _ENV_COLORS.get(info.environment, _CYAN) if color else ""

    rows = [
        ("Version", info.version),
        ("Environment", info.environment),
        ("Commit", info.commit_display),
        ("Built", info.build_display),
        ("Runtime", info.runtime_display),
        ("OS", info.os_info),
    ]

    # Add extras
    for key, val in info.extras.items():
        rows.append((key, str(val)))

    # Calculate widths
    label_width = max(len(r[0]) for r in rows)
    value_width = max(len(r[1]) for r in rows)
    content_width = label_width + 3 + value_width  # label + "   " + value
    title_len = len(info.service)
    inner_width = max(content_width, title_len) + 4  # padding

    # Build the banner
    lines = []
    top = f"{c['dim']}\u2552{'═' * inner_width}╕{c['reset']}"
    bot = f"{c['dim']}\u2558{'═' * inner_width}╛{c['reset']}"
    sep = f"{c['dim']}├{'─' * inner_width}┤{c['reset']}"
    wall_l = f"{c['dim']}│{c['reset']}"
    wall_r = f"{c['dim']}│{c['reset']}"

    lines.append(top)

    # Title row
    title = f"{c['bold']}{c['white']}  {info.service}{c['reset']}"
    padding = inner_width - title_len - 2
    lines.append(f"{wall_l}{title}{' ' * padding}{wall_r}")

    lines.append(sep)

    # Data rows
    for label, value in rows:
        padded_label = label.rjust(label_width)

        # Color the value based on field
        if label == "Environment":
            colored_val = f"{env_color}{c['bold']}{value}{c['reset']}"
        elif label == "Commit" and info.git_dirty:
            colored_val = f"{c['cyan']}{value.replace('[dirty]', '')}{c['yellow']}[dirty]{c['reset']}"
        elif label == "Version":
            colored_val = f"{c['green']}{c['bold']}{value}{c['reset']}"
        else:
            colored_val = f"{c['white']}{value}{c['reset']}"

        dim_label = f"{c['dim']}{padded_label}{c['reset']}"
        # We need to calculate padding based on raw (uncolored) lengths
        raw_content = f"  {padded_label}   {value}"
        pad = inner_width - len(raw_content)
        lines.append(f"{wall_l}  {dim_label}   {colored_val}{' ' * pad}{wall_r}")

    lines.append(bot)

    return "\n".join(lines)


def print_banner(
    service: str,
    color: bool = True,
    logger=None,
    **extras,
) -> BuildInfo:
    """
    Collect build info and print the startup banner.

    Args:
        service: Service name (e.g. "concord-http-api")
        color: Whether to use ANSI colors (default True)
        logger: Optional Logger instance. If provided, banner is logged via logger.info().
                Otherwise printed to stdout.
        **extras: Additional key-value pairs to display in the banner.

    Returns:
        The collected BuildInfo for programmatic access.
    """
    info = collect(service, **extras)
    banner = format_banner(info, color=color)

    if logger:
        # Log each line separately so log prefix doesn't break the box
        for line in banner.split("\n"):
            logger.info(line)
    else:
        print(banner, flush=True)

    return info
