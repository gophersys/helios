/**
 * The axe-core injection helper (mirrors the OD-1 spike — the proven RD-16 pattern).
 *
 * Injects the REAL axe-core engine into the page and runs a full audit. Returns the violations PLUS
 * the pass/rule counts so a test can both assert ZERO serious/critical AND prove axe actually walked
 * a non-trivial WCAG rule set (guards against a vacuous pass from a silently-failed injection).
 */
import fs from 'node:fs';
import { createRequire } from 'node:module';
import type { Page } from '@playwright/test';

const require = createRequire(import.meta.url);
const axePath = require.resolve('axe-core/axe.min.js');
export const AXE_SOURCE: string = fs.readFileSync(axePath, 'utf8');

export interface AxeViolation {
  readonly id: string;
  readonly impact: string | null | undefined;
  readonly help: string;
  readonly nodes: number;
  readonly targets: readonly unknown[];
}

export interface AxeResult {
  readonly violations: readonly AxeViolation[];
  readonly passCount: number;
  readonly ruleCount: number;
}

/** Inject the real axe-core engine into the page if it is not already present. */
export async function ensureAxe(page: Page): Promise<void> {
  const ran = await page.evaluate((src: string): boolean => {
    const w = window as unknown as { axe?: { run?: unknown } };
    if (!w.axe) {
      // eslint-disable-next-line no-eval
      window.eval(src);
    }
    return typeof w.axe?.run === 'function';
  }, AXE_SOURCE);
  if (!ran) throw new Error('axe-core failed to inject');
}

export async function runAxeFull(page: Page): Promise<AxeResult> {
  await ensureAxe(page);

  return await page.evaluate(async (): Promise<AxeResult> => {
    const axe = (window as unknown as { axe: { run: (ctx: Document, opt: unknown) => Promise<{
      violations: { id: string; impact?: string | null; help: string; nodes: { target: unknown }[] }[];
      passes: unknown[];
      inapplicable: unknown[];
      incomplete: unknown[];
    }> } }).axe;
    const results = await axe.run(document, { resultTypes: ['violations'] });
    return {
      violations: results.violations.map((v) => ({
        id: v.id,
        impact: v.impact,
        help: v.help,
        nodes: v.nodes.length,
        targets: v.nodes.slice(0, 3).map((n) => n.target),
      })),
      passCount: results.passes.length,
      ruleCount:
        results.passes.length +
        results.violations.length +
        results.inapplicable.length +
        results.incomplete.length,
    };
  });
}

export function seriousOrCritical(violations: readonly AxeViolation[]): readonly AxeViolation[] {
  return violations.filter((v) => v.impact === 'serious' || v.impact === 'critical');
}
