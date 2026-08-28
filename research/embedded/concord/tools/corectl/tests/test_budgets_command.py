"""Tests for ``corectl.commands.budgets``.

The budget analyzer is pure logic once the HTTP responses are in hand
— percentile math + suggestion rounding + the name-stripping regex.
These tests lock those down so a refactor doesn't silently change
the numbers operators paste into their test files.
"""

from __future__ import annotations

from typing import Any, Dict, List

import pytest

from corectl.commands import budgets as bud


# ────────────────────────────────────────────────────────────────────────
# Slot-suffix stripping
# ────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "input_name, expected",
    [
        ("test_01_boot[slot-0]",        "test_01_boot"),
        ("test_04_charger[slot-3]",     "test_04_charger"),
        ("test_10_personalize[slot-12]", "test_10_personalize"),
        ("test_no_param",               "test_no_param"),
        ("",                            ""),
    ],
)
def test_strip_slot_suffix(input_name, expected):
    assert bud._strip_slot_suffix(input_name) == expected


# ────────────────────────────────────────────────────────────────────────
# Percentile nearest-rank
# ────────────────────────────────────────────────────────────────────────


def test_percentile_empty_returns_zero():
    assert bud._percentile([], 0.95) == 0.0


def test_percentile_single_value():
    assert bud._percentile([42.0], 0.95) == 42.0
    assert bud._percentile([42.0], 0.50) == 42.0


def test_percentile_monotonic_and_within_bounds():
    values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    # p50 ≈ 5.0, p95 ≈ 10.0, bounded by max
    assert bud._percentile(values, 0.50) <= bud._percentile(values, 0.95)
    assert bud._percentile(values, 0.95) <= max(values)
    assert bud._percentile(values, 0.50) >= min(values)


# ────────────────────────────────────────────────────────────────────────
# Budget rounding rule
# ────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "max_ms, expected_s",
    [
        # Tiny test — floored to 10s
        (10,        10),
        (500,       10),
        (1_000,     10),
        # Just under the 5s+5s break point → still 10
        (4_999,     10),
        # Right at 5s observed — ceil(5+5, 5) = 10
        (5_000,     10),
        # 6s observed → ceil(11, 5) = 15
        (6_000,     15),
        # 10s observed → ceil(15, 5) = 15
        (10_000,    15),
        # 11s observed → ceil(16, 5) = 20
        (11_000,    20),
        # 41s observed (real example from the electrical stage)
        (41_000,    50),
        # 55s observed (flash_app)
        (55_000,    60),
        # 255.3s observed (boot tail) — ceil((255.3 + 5) / 5) * 5 = 265
        (255_300,   265),
        # Exactly 255s observed — target 260 hits the boundary cleanly
        (255_000,   260),
    ],
)
def test_suggest_budget_rounds_up_with_margin_and_floor(max_ms, expected_s):
    assert bud._suggest_budget_s(max_ms) == expected_s


def test_suggest_budget_always_ge_floor():
    # For any max <= 5s, the budget must be the 10s floor.
    for ms in (0, 1, 10, 100, 1000, 4999, 5000):
        assert bud._suggest_budget_s(ms) >= 10


# ────────────────────────────────────────────────────────────────────────
# Aggregation
# ────────────────────────────────────────────────────────────────────────


def _exec(name: str, module: str, status: str, duration_ms: int) -> Dict[str, Any]:
    return {
        "name": name,
        "module": module,
        "status": status,
        "durationMs": duration_ms,
    }


def _run(*executions: Dict[str, Any]) -> Dict[str, Any]:
    return {"targets": [{"executions": list(executions)}]}


def test_collect_durations_groups_by_stripped_name():
    runs_data = [
        _run(
            _exec("test_01_boot[slot-0]", "test_03_post", "PASSED", 30_000),
            _exec("test_01_boot[slot-1]", "test_03_post", "PASSED", 45_000),
        ),
        _run(
            _exec("test_01_boot[slot-0]", "test_03_post", "PASSED", 32_000),
        ),
    ]
    buckets = bud._collect_durations(runs_data, module_prefix=None)
    assert set(buckets.keys()) == {"test_01_boot"}
    assert sorted(buckets["test_01_boot"]) == [30_000.0, 32_000.0, 45_000.0]


def test_collect_durations_filters_by_module_prefix():
    runs_data = [
        _run(
            _exec("test_01_boot[slot-0]", "test_03_post", "PASSED", 30_000),
            _exec("test_01_uvlo[slot-0]", "test_01_electrical", "PASSED", 20_000),
        ),
    ]
    buckets = bud._collect_durations(runs_data, module_prefix="test_03_post")
    assert list(buckets.keys()) == ["test_01_boot"]


def test_collect_durations_skips_non_terminal_and_zero_durations():
    runs_data = [
        _run(
            _exec("test_01_boot[slot-0]", "test_03_post", "RUNNING", 0),
            _exec("test_01_boot[slot-1]", "test_03_post", "SKIPPED", 5),
            _exec("test_01_boot[slot-2]", "test_03_post", "PASSED", 0),  # duration too small
            _exec("test_01_boot[slot-3]", "test_03_post", "PASSED", 30_000),
        ),
    ]
    buckets = bud._collect_durations(runs_data, module_prefix=None)
    assert buckets["test_01_boot"] == [30_000.0]


def test_collect_durations_includes_failed_tests():
    # A failed test still took real time; we want that data in the budget.
    runs_data = [
        _run(
            _exec("test_01_boot[slot-0]", "test_03_post", "FAILED", 28_000),
            _exec("test_01_boot[slot-1]", "test_03_post", "PASSED", 30_000),
        ),
    ]
    buckets = bud._collect_durations(runs_data, module_prefix=None)
    assert sorted(buckets["test_01_boot"]) == [28_000.0, 30_000.0]


def test_collect_durations_empty_when_no_eligible_executions():
    runs_data = [
        _run(_exec("test_01_boot[slot-0]", "test_03_post", "SKIPPED", 0)),
    ]
    assert bud._collect_durations(runs_data, module_prefix=None) == {}
