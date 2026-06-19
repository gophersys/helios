// Status encoding — ONE home for how a health status reads. Triple-encoded (R3 E1): a generated
// role COLOR + a SHAPE (survives grayscale / colour-blindness) + a GLYPH. Never colour alone.
// StatusGlyph/StatusChip and the node outlines all read this table, so health is decodable from
// the legend without tribal knowledge. Colours are the generated @eden/theme role tokens (the
// OKLCH ramp puts error darkest → warning mid → success light, so severity is a monotonic
// lightness ramp under CVD for free); never a hand-picked hex.
import type { Status } from './contract';

export interface StatusSpec {
  /** The plain word a human reads (the Scorecard's dominant label). */
  label: string;
  /** The CSS var name of the generated role colour (used as `var(<token>)`). */
  token: string;
  /** The glyph SHAPE — the redundant, colour-independent encoding. */
  shape: 'circle' | 'triangle' | 'octagon' | 'diamond' | 'hollow';
  /** Severity rank for worst-of rollups + default sort (higher = worse). */
  severity: number;
}

export const STATUS: Record<Status, StatusSpec> = {
  down: { label: 'Down', token: '--color-error', shape: 'octagon', severity: 4 },
  warn: { label: 'Degraded', token: '--color-warning', shape: 'triangle', severity: 3 },
  progressing: { label: 'Updating', token: '--color-info', shape: 'diamond', severity: 2 },
  ok: { label: 'Healthy', token: '--color-success', shape: 'circle', severity: 1 },
  unknown: { label: 'Unknown', token: '--color-outline', shape: 'hollow', severity: 0 },
};

/** `var(--color-…)` for a status — the single place a status colour is resolved. */
export function statusColor(status: Status | undefined): string {
  return `var(${STATUS[status ?? 'unknown'].token})`;
}

/** Worst-of a set of statuses by severity (down > warn > progressing > ok > unknown). An empty
 *  set is `unknown`; an all-ok set is `ok` — never averaged, so 1-of-50 broken still reads broken. */
export function worstOf(statuses: Iterable<Status | undefined>): Status {
  let worst: Status = 'unknown';
  let seen = false;
  for (const s of statuses) {
    const v = s ?? 'unknown';
    seen = true;
    if (STATUS[v].severity > STATUS[worst].severity) worst = v;
  }
  // an all-`unknown`-but-non-empty set stays unknown; an empty set is unknown too.
  return seen ? worst : 'unknown';
}
