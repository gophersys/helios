/**
 * P2.3 — derive the user-visible failure banner for a TestRun.
 *
 * The v0.12.0 -> 0.12.3 silent-skew incident produced runs that
 * finished with status=COMPLETED, total>0, passed=0, failed=0,
 * errors=0 — every test silently skipped, no signal to the operator.
 * P2.1 fixed the autoconf root cause; P2.2 had http-api downgrade
 * that count-shape to FAILED with a synthesized errorMessage. P2.3
 * is the frontend's job: actually SHOW the error to the operator.
 *
 * This module is pure-TS and unit-tested. The matching Svelte
 * component (`run-error-banner.svelte`) is a thin renderer over
 * `deriveRunErrorBanner(run)` and is verified visually in dev.
 */

import type { TestRun } from '$lib/types/models';

export type RunErrorBannerVariant = 'all-skipped' | 'failed' | 'cancelled';

export interface RunErrorBanner {
  /** Whether the banner should render at all. */
  readonly visible: boolean;
  /** Severity / icon variant. */
  readonly variant: RunErrorBannerVariant | null;
  /** Headline shown bold at the top of the banner. */
  readonly headline: string;
  /** Body text (the run's errorMessage, normalized). */
  readonly detail: string;
}

const HIDDEN: RunErrorBanner = {
  visible: false,
  variant: null,
  headline: '',
  detail: '',
};

/**
 * Detect the "all tests skipped" pathology.
 *
 * Mirror of the http-api detection at `report_finish`:
 *   total > 0 AND passed == 0 AND failed == 0
 *
 * (errors fold into failedCount on the run row — see
 * apps/backend/http-api/src/api/v2/runs/reporter.py.)
 *
 * total == 0 (no tests collected) is intentionally NOT flagged — a
 * test app with zero discoverable tests is a different problem.
 */
export function isAllSkipped(run: Pick<
  TestRun,
  'completedCount' | 'passedCount' | 'failedCount'
>): boolean {
  return (
    run.completedCount > 0
    && run.passedCount === 0
    && run.failedCount === 0
  );
}

/**
 * Decide what banner (if any) to display for a run.
 *
 * Visibility rules:
 *   - status === 'FAILED' AND errorMessage present  → render
 *   - status === 'FAILED' AND all-skipped pattern   → render (synthetic message
 *                                                     in case http-api didn't
 *                                                     populate one for any reason)
 *   - status === 'CANCELLED' AND errorMessage      → render (cancellation note)
 *   - all other shapes                              → hidden
 *
 * The headline distinguishes the all-skipped variant explicitly so
 * the operator immediately knows it's a version-skew pathology, not
 * a single failed test.
 */
export function deriveRunErrorBanner(
  run: Pick<
    TestRun,
    'status' | 'errorMessage' | 'completedCount' | 'passedCount' | 'failedCount'
  > | null | undefined,
): RunErrorBanner {
  if (!run) {
    return HIDDEN;
  }

  const detail = (run.errorMessage ?? '').trim();
  const allSkipped = isAllSkipped(run);

  if (run.status === 'FAILED') {
    if (allSkipped) {
      return {
        visible: true,
        variant: 'all-skipped',
        headline: `All ${run.completedCount} tests skipped — run did not execute`,
        detail: detail || (
          'No executions completed. Most likely cause: test package '
          + "framework version mismatch with the runner's corekinect. "
          + "Run 'corectl test refresh-framework && corectl test upload' "
          + 'to re-publish the test package.'
        ),
      };
    }
    if (detail) {
      return {
        visible: true,
        variant: 'failed',
        headline: 'Run failed',
        detail,
      };
    }
    return HIDDEN;
  }

  if (run.status === 'CANCELLED' && detail) {
    return {
      visible: true,
      variant: 'cancelled',
      headline: 'Run cancelled',
      detail,
    };
  }

  return HIDDEN;
}
