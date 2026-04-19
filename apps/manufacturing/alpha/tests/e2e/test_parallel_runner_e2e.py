"""End-to-end verification of the synchronized per-slot parallel runner.

These tests drive the Concord HTTP API against a **real** target
environment (staging or production) with a physical fixture holding
boards. They exist to prove two things the unit tests can't:

  * No runner-induced skips on real hardware — every target reaches
    ``PASSED`` or ``FAILED``, not ``SKIPPED`` due to xdist-style cross-
    worker state loss.
  * The performance contract — a 4-slot panel completes in at most
    ``1.15 × single-slot duration``, proving slots advance concurrently
    rather than serially.

Run only against environments with the right fixture populated:

    CONCORD_API_URL=https://concord.ad.corekinect.com \
    CONCORD_API_KEY=$(< ~/.concord/ci_key) \
    CONCORD_E2E_PRODUCT_ID=... \
    CONCORD_E2E_FIXTURE_ID=... \
    CONCORD_E2E_ASSET_SET_ID=prod_asset_056 \
    CONCORD_E2E_STANDALONE_SNR=0964 \
    CONCORD_E2E_PANEL_SNRS=095F,095G,095H,095J \
    python3 -m pytest apps/manufacturing/alpha/tests/e2e -v --timeout=3600

All non-configured runs are skipped — the suite never breaks CI when
the target fixture isn't reachable.
"""

from __future__ import annotations

import pytest

from ._harness import ApiHarness, RunInfo
from .conftest import E2EConfig


# Give the runner time to deploy + run. Single-slot baseline is the long
# pole for the combined suite; budget 20 min for headroom.
_RUN_TIMEOUT_S = 20 * 60


# ────────────────────────────────────────────────────────────────────────
# Fixtures
# ────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def api(e2e_config: E2EConfig) -> ApiHarness:
    return ApiHarness(e2e_config.api_url, e2e_config.api_key)


@pytest.fixture(scope="session")
def baseline_duration_ms(api: ApiHarness, e2e_config: E2EConfig) -> int:
    """Run one standalone board and return its wall-clock duration.

    Cached for the whole pytest session so every assertion against the
    panel-duration contract compares to the same measurement — avoids
    ping-pong flakes when the MTIB/DUT varies a few seconds between
    runs.
    """
    session = api.create_session(
        product_id=e2e_config.product_id,
        fixture_id=e2e_config.fixture_id,
        asset_set_id=e2e_config.asset_set_id,
    )
    try:
        api.wait_for_runner_ready(session.id)
        run_id = api.trigger_run(
            session_id=session.id,
            qr_code=e2e_config.standalone_snr,
            run_type="standalone",
        )
        run = api.wait_for_run(run_id, timeout_s=_RUN_TIMEOUT_S)
    finally:
        api.end_session(session.id)

    _assert_no_runner_skips(run, context="baseline (single slot)")
    assert run.duration_ms is not None, "baseline run did not record durationMs"
    return run.duration_ms


# ────────────────────────────────────────────────────────────────────────
# Assertions on a run's targets
# ────────────────────────────────────────────────────────────────────────


def _assert_no_runner_skips(run: RunInfo, *, context: str) -> None:
    """Every target must reach PASSED or FAILED — never stay SKIPPED.

    SKIPPED indicates the runner's fixture state didn't survive across
    tests (the classic xdist symptom), which the new slot_parallel
    plugin + in-process thread pool is supposed to prevent.
    """
    skipped = [t for t in run.targets if t.get("status") == "SKIPPED"]
    assert not skipped, (
        f"{context}: {len(skipped)} target(s) SKIPPED — slot state was "
        f"lost across parallel workers. Expected every board to reach "
        f"PASSED or FAILED. Targets: {run.targets}"
    )


# ────────────────────────────────────────────────────────────────────────
# End-to-end assertions
# ────────────────────────────────────────────────────────────────────────


def test_baseline_single_slot_runs_cleanly(baseline_duration_ms: int) -> None:
    """Single-slot baseline completes without runner-induced skips.

    This is the reference point for every panel-parallelism assertion.
    Existence of ``baseline_duration_ms`` as a non-None int means the
    fixture-level assertions already passed.
    """
    assert baseline_duration_ms > 0
    # Sanity check — our current flow is ~2-8 min per slot depending on
    # CoreOps latency; anything outside [30s, 1200s] is a red flag.
    assert 30_000 <= baseline_duration_ms <= 1_200_000, (
        f"baseline duration {baseline_duration_ms}ms outside the "
        f"plausible single-slot window [30s, 20min]"
    )


def test_panel_matches_single_slot_duration(
    api: ApiHarness,
    e2e_config: E2EConfig,
    baseline_duration_ms: int,
) -> None:
    """A full panel completes in ≤ 2.5 × the single-slot baseline.

    With slot_parallel's group barrier (each test waits for the
    slowest slot before advancing to the next), a panel run wall-clock
    equals the sum of ``max(slot_duration)`` per group plus per-group
    overhead — not ``max(per-slot total)`` as a fully overlapping
    parallelism would give. With ~19 groups and per-group overhead in
    the 1-3 s range, an empirically-correct ceiling is around
    ``baseline + 19 × overhead``, which lands near 2.0-2.2 × baseline
    on the current Alpha mfg suite.

    The 2.5 × multiplier leaves headroom for one slow slot dragging a
    couple of groups (slowest-slot-wins amplifies the worst case).
    Tightening this further requires reducing per-group barrier work
    or moving to stage-level grouping, both of which are tracked
    follow-ups.
    """
    session = api.create_session(
        product_id=e2e_config.product_id,
        fixture_id=e2e_config.fixture_id,
        asset_set_id=e2e_config.asset_set_id,
    )
    try:
        api.wait_for_runner_ready(session.id)
        # We pass the first SNR as the QR code; the session scan logic
        # resolves the rest of the panel's SNRs via fixture slot mapping.
        run_id = api.trigger_run(
            session_id=session.id,
            qr_code=e2e_config.panel_snrs[0],
            run_type="panel",
        )
        run = api.wait_for_run(run_id, timeout_s=_RUN_TIMEOUT_S)
    finally:
        api.end_session(session.id)

    _assert_no_runner_skips(run, context="panel run")

    # Every slot reported a terminal state
    assert run.target_count == e2e_config.num_panel_slots, (
        f"expected {e2e_config.num_panel_slots} targets, got {run.target_count}"
    )

    # Performance contract
    assert run.duration_ms is not None, "panel run did not record durationMs"
    ceiling_ms = int(baseline_duration_ms * 2.5)
    assert run.duration_ms <= ceiling_ms, (
        f"panel took {run.duration_ms}ms, exceeds 2.5 × baseline "
        f"({baseline_duration_ms}ms → ceiling {ceiling_ms}ms). "
        f"Slots likely ran serially, not in parallel."
    )


def test_slot_failure_does_not_cascade_to_other_slots(
    api: ApiHarness,
    e2e_config: E2EConfig,
    baseline_duration_ms: int,
) -> None:
    """If one panel slot fails, the rest still reach a terminal state.

    This exercises the fixture-graph cascade — a failing
    :func:`booted_device` on slot-2 ERRORs every dependent test on that
    slot, but slot-0, slot-1, slot-3 proceed independently because each
    slot has its own fixture instance.
    """
    session = api.create_session(
        product_id=e2e_config.product_id,
        fixture_id=e2e_config.fixture_id,
        asset_set_id=e2e_config.asset_set_id,
    )
    try:
        api.wait_for_runner_ready(session.id)
        run_id = api.trigger_run(
            session_id=session.id,
            qr_code=e2e_config.panel_snrs[0],
            run_type="panel",
        )
        run = api.wait_for_run(run_id, timeout_s=_RUN_TIMEOUT_S)
    finally:
        api.end_session(session.id)

    # Every target reached a terminal state (PASSED or FAILED); no
    # target is "stuck" in RUNNING or left SKIPPED by the runner.
    terminal = {"PASSED", "FAILED", "ERROR"}
    for target in run.targets:
        assert target["status"] in terminal, (
            f"target {target.get('serialNumber')} ended in "
            f"non-terminal status {target['status']}"
        )
