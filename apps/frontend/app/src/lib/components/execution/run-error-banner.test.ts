/**
 * P2.3 — tests for the run-error-banner derivation.
 *
 * Contract pinned:
 *   - COMPLETED runs never show the banner.
 *   - FAILED with all-skipped → "all-skipped" variant + count in headline
 *     + synthetic message when none provided by the API.
 *   - FAILED with at least one passed/failed test → "failed" variant +
 *     the provided errorMessage (no synthesis).
 *   - CANCELLED with a note → "cancelled" variant.
 *   - Missing run / null → hidden.
 *
 * The Svelte component over this helper is verified visually in dev
 * (no Svelte component test harness in this app — see
 * .claude/knowledge/apps/frontend/app.md, "Testing").
 */

import { describe, it, expect } from 'vitest';
import {
  deriveRunErrorBanner,
  isAllSkipped,
} from './run-error-banner';

// A minimal run shape — we only consume a few fields.
function makeRun(overrides: Partial<{
  status: 'PENDING' | 'ACTIVE' | 'COMPLETED' | 'FAILED' | 'CANCELLED';
  errorMessage: string | undefined;
  completedCount: number;
  passedCount: number;
  failedCount: number;
}> = {}) {
  return {
    status: 'COMPLETED' as const,
    errorMessage: undefined,
    completedCount: 0,
    passedCount: 0,
    failedCount: 0,
    ...overrides,
  };
}

describe('isAllSkipped', () => {
  it('returns true when total > 0 and passed/failed both zero', () => {
    expect(isAllSkipped(makeRun({ completedCount: 126, passedCount: 0, failedCount: 0 }))).toBe(true);
  });

  it('returns false when at least one passed', () => {
    expect(isAllSkipped(makeRun({ completedCount: 5, passedCount: 1, failedCount: 0 }))).toBe(false);
  });

  it('returns false when at least one failed', () => {
    expect(isAllSkipped(makeRun({ completedCount: 5, passedCount: 0, failedCount: 1 }))).toBe(false);
  });

  it('returns false when total == 0 (no tests collected)', () => {
    expect(isAllSkipped(makeRun({ completedCount: 0, passedCount: 0, failedCount: 0 }))).toBe(false);
  });
});

describe('deriveRunErrorBanner', () => {
  it('returns hidden for COMPLETED runs', () => {
    const banner = deriveRunErrorBanner(makeRun({
      status: 'COMPLETED',
      completedCount: 10,
      passedCount: 10,
    }));
    expect(banner.visible).toBe(false);
  });

  it('returns hidden for ACTIVE runs', () => {
    const banner = deriveRunErrorBanner(makeRun({
      status: 'ACTIVE',
      completedCount: 3,
      passedCount: 0,
      failedCount: 0,
    }));
    expect(banner.visible).toBe(false);
  });

  it('returns hidden for null/undefined run', () => {
    expect(deriveRunErrorBanner(null).visible).toBe(false);
    expect(deriveRunErrorBanner(undefined).visible).toBe(false);
  });

  describe('all-skipped variant', () => {
    it('renders with the all-skipped headline naming the count', () => {
      const banner = deriveRunErrorBanner(makeRun({
        status: 'FAILED',
        completedCount: 126,
        passedCount: 0,
        failedCount: 0,
        errorMessage: undefined,
      }));
      expect(banner.visible).toBe(true);
      expect(banner.variant).toBe('all-skipped');
      expect(banner.headline).toContain('126');
      expect(banner.headline.toLowerCase()).toContain('skipped');
    });

    it('synthesizes a remediation detail when API did not supply one', () => {
      const banner = deriveRunErrorBanner(makeRun({
        status: 'FAILED',
        completedCount: 126,
      }));
      expect(banner.detail.toLowerCase()).toContain('framework');
      // The detail must point at the corectl remediation.
      expect(banner.detail).toContain('corectl test refresh-framework');
      expect(banner.detail).toContain('corectl test upload');
    });

    it('prefers the API-provided errorMessage when present', () => {
      const apiMsg = 'Framework constraint >=1.0 violated by runner corekinect 0.8.0';
      const banner = deriveRunErrorBanner(makeRun({
        status: 'FAILED',
        completedCount: 126,
        errorMessage: apiMsg,
      }));
      expect(banner.variant).toBe('all-skipped');  // still classified as all-skipped
      expect(banner.detail).toBe(apiMsg);
      // Synthetic remediation must NOT replace the precise message.
      expect(banner.detail).not.toContain('corectl test refresh-framework');
    });

    it('trims whitespace in the detail', () => {
      const banner = deriveRunErrorBanner(makeRun({
        status: 'FAILED',
        completedCount: 126,
        errorMessage: '   some message   ',
      }));
      expect(banner.detail).toBe('some message');
    });
  });

  describe('failed variant', () => {
    it('renders the errorMessage when a real failure occurred', () => {
      const banner = deriveRunErrorBanner(makeRun({
        status: 'FAILED',
        completedCount: 10,
        passedCount: 7,
        failedCount: 3,
        errorMessage: 'test_03_post failed on slot-2: NOR pre-state non-FF',
      }));
      expect(banner.visible).toBe(true);
      expect(banner.variant).toBe('failed');
      expect(banner.headline).toBe('Run failed');
      expect(banner.detail).toContain('NOR pre-state non-FF');
    });

    it('is hidden when status is FAILED but no errorMessage and not all-skipped', () => {
      // Defensive: if backend marks FAILED without a reason and there
      // were real test outcomes, we'd surface that via the existing
      // per-test failure UI — no need for the top banner.
      const banner = deriveRunErrorBanner(makeRun({
        status: 'FAILED',
        completedCount: 10,
        passedCount: 7,
        failedCount: 3,
      }));
      expect(banner.visible).toBe(false);
    });
  });

  describe('cancelled variant', () => {
    it('renders when CANCELLED with a note', () => {
      const banner = deriveRunErrorBanner(makeRun({
        status: 'CANCELLED',
        completedCount: 5,
        passedCount: 2,
        failedCount: 0,
        errorMessage: 'Operator cancelled at slot-1 boot',
      }));
      expect(banner.visible).toBe(true);
      expect(banner.variant).toBe('cancelled');
      expect(banner.headline).toBe('Run cancelled');
      expect(banner.detail).toContain('slot-1');
    });

    it('is hidden when CANCELLED without a note', () => {
      const banner = deriveRunErrorBanner(makeRun({
        status: 'CANCELLED',
        completedCount: 5,
        passedCount: 2,
      }));
      expect(banner.visible).toBe(false);
    });
  });
});
