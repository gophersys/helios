#!/usr/bin/env python3
"""Cyclomatic complexity checker with allowlist support.

Usage:
    python3 .ci/lib/check_complexity.py <src_dir> [--threshold=15] [--avg-threshold=6] [--allowlist=.ci/complexity-allowlist.json]

Exit codes:
    0 — all functions within threshold (or allowlisted)
    1 — violations found
"""

import json
import sys
from pathlib import Path

from radon.complexity import cc_visit

CC_THRESHOLD = 15
AVG_THRESHOLD = 6.0
ALLOWLIST_PATH = None


def load_allowlist(path: str) -> dict:
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def check_complexity(src_dir: str, threshold: int, avg_threshold: float, allowlist: dict) -> bool:
    violations = []
    total_cc = 0
    func_count = 0
    grades = {"A": 0, "B": 0, "C": 0, "D+": 0}

    for p in sorted(Path(src_dir).rglob("*.py")):
        # Skip test files and virtual environments
        if "/tests/" in str(p) or p.name.startswith("test_"):
            continue
        if "/.venv/" in str(p) or "/site-packages/" in str(p):
            continue
        try:
            blocks = cc_visit(p.read_text())
        except SyntaxError:
            continue

        rel_path = str(p)
        file_allowlist = allowlist.get(rel_path, {})

        for b in blocks:
            func_count += 1
            total_cc += b.complexity
            g = "A" if b.complexity <= 5 else "B" if b.complexity <= 10 else "C" if b.complexity <= 20 else "D+"
            grades[g] += 1

            # Check against allowlist or global threshold
            allowed_cc = file_allowlist.get(b.name, threshold)
            if b.complexity > allowed_cc:
                violations.append((b.complexity, allowed_cc, rel_path, b.name, b.lineno))

    avg_cc = round(total_cc / func_count, 1) if func_count else 0
    pct_a = round(grades["A"] / func_count * 100) if func_count else 0

    # Report
    print(f"\n  Functions: {func_count}")
    print(f"  Average CC: {avg_cc} (threshold: {avg_threshold})")
    print(f"  A(1-5): {grades['A']} ({pct_a}%) | B(6-10): {grades['B']} | C(11-20): {grades['C']} | D+(21+): {grades['D+']}")

    if violations:
        print(f"\n  {len(violations)} VIOLATION(S):")
        violations.sort(reverse=True)
        for cc, allowed, path, name, line in violations:
            tag = f" (allowlisted at {allowed})" if allowed != threshold else ""
            print(f"    CC={cc} {path}:{line} {name}{tag}")

    failed = False
    if violations:
        print(f"\n  FAIL: {len(violations)} function(s) exceed complexity threshold")
        failed = True
    if avg_cc > avg_threshold:
        print(f"\n  FAIL: Average CC {avg_cc} exceeds threshold {avg_threshold}")
        failed = True

    if not failed:
        print(f"\n  PASS: All functions within thresholds")

    return not failed


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("src_dir")
    parser.add_argument("--threshold", type=int, default=10)
    parser.add_argument("--avg-threshold", type=float, default=6.0)
    parser.add_argument("--allowlist", default=".ci/complexity-allowlist.json")
    args = parser.parse_args()

    allowlist = load_allowlist(args.allowlist)
    ok = check_complexity(args.src_dir, args.threshold, args.avg_threshold, allowlist)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
