/**
 * Run status derivation helpers.
 *
 * The backend stores ``TestRun.status`` as the authoritative state, but
 * websocket events for per-target progress (``run_target_start``,
 * ``run_execution_result``) can arrive before the ``run_start`` event that
 * flips the run to ``ACTIVE``. Reading ``run.status`` directly causes the
 * widget at the top of the manufacturing session page (which renders per
 * target) to show "Running" while the row in the history table still shows
 * "Pending" for the same run.
 *
 * ``effectiveRunStatus`` derives a single status string that both views can
 * agree on by promoting a stored ``PENDING`` run to ``ACTIVE`` whenever any
 * of its targets is no longer queued.
 */

import type { RunTarget, TestRun } from '$lib/types/models';

export type EffectiveRunStatus = TestRun['status'];

/** A target whose status indicates work is in flight or already finished. */
const ACTIVE_TARGET_STATES: ReadonlySet<RunTarget['status']> = new Set<RunTarget['status']>([
  'RUNNING',
  'PASSED',
  'FAILED',
  'ERROR',
]);

const TERMINAL_TARGET_STATES: ReadonlySet<RunTarget['status']> = new Set<RunTarget['status']>([
  'PASSED',
  'FAILED',
  'ERROR',
]);

/**
 * Return the status that should be shown to a user for a given run.
 *
 * Rules (in priority order):
 *   1. Terminal stored statuses (``COMPLETED``/``FAILED``/``CANCELLED``) are
 *      respected verbatim — once the backend has written a terminal value,
 *      it wins over any stale per-target snapshots.
 *   2. ``ACTIVE`` is respected verbatim.
 *   3. ``PENDING`` is promoted to ``ACTIVE`` when any target has started
 *      executing (``RUNNING`` or any terminal state). This catches the WS
 *      race where ``run_target_start`` is processed before ``run_start``.
 */
export function effectiveRunStatus(run: TestRun): EffectiveRunStatus {
  const stored = run.status;
  if (stored !== 'PENDING') return stored;

  const targets = run.targets ?? [];
  if (targets.some(t => ACTIVE_TARGET_STATES.has(t.status))) {
    return 'ACTIVE';
  }
  return stored;
}

/**
 * True when the run is doing work right now (or is queued and about to).
 * Used to gate "active run" lookups so both the panel widget and the run
 * history row pick the same record as the live one.
 */
export function isRunInFlight(run: TestRun): boolean {
  const status = effectiveRunStatus(run);
  return status === 'PENDING' || status === 'ACTIVE';
}

/** Convenience: are all targets in a terminal state? */
export function allTargetsTerminal(run: TestRun): boolean {
  const targets = run.targets ?? [];
  if (targets.length === 0) return false;
  return targets.every(t => TERMINAL_TARGET_STATES.has(t.status));
}
