/**
 * HotspotMap — unit + component render (application-logic correctness, ADR-0024). The pure
 * derivation + plot composition asserted directly over a REAL codeinsight Report slice for Eden's own
 * libs (the self-feeding target, contract §6), plus the REAL Svelte 5 component: the figure mounts
 * with an accessible name, every point is a keyboard-focusable ≥44px target carrying its metrics, and
 * the offscreen data-table fallback enumerates every entity.
 */
import { describe, expect, it } from 'vitest';
import { render } from '@testing-library/svelte';
import { generateTheme, C21_SEED, type Theme } from '@eden/theme';
import HotspotMap from './hotspot-map.svelte';
import { deriveHotspotMapTokens, hotspotMapStyleVars, hitTargetPx } from './tokens.js';
import { buildHotspotPlot, DEFAULT_HOTSPOT_ENCODING, DEFAULT_PLOT_DIMENSIONS } from './plot.js';
import { hotspotColorAt, entityLabel, type HotspotRamp } from './scales.js';
import type { Entity, Report } from '../report/index.js';

/**
 * A small Eden-libs codeinsight Report slice (contract §6 — Eden analyzing Eden). The top hotspot
 * `cases.go` mirrors the contract worked example (churnRelative ≈ 1.07 / cyclomatic 216 / score 1.0)
 * so the placement assertions below check the known top-right, max-colour point.
 */
const EDEN_LIBS_REPORT: Report = {
  schemaVersion: '0.1.0',
  repository: {
    identifier: 'gophersys/libs',
    headCommit: '6596b3d0000000000000000000000000000000aa',
    analyzedAt: '2026-06-17T00:00:00Z',
    commitCount: 412,
  },
  window: { toCommit: '6596b3d0000000000000000000000000000000aa', revisions: 412 },
  entities: [
    {
      path: 'libs/go/agentsession/cases.go',
      kind: 'file',
      language: 'go',
      lines: 1840,
      cyclomatic: 216,
      churnAbsolute: 1969,
      churnRelative: 1.07,
      changeFrequency: 58,
      hotspotScore: 1.0,
      ageDays: 3,
    },
    {
      path: 'libs/go/errors/kind.go',
      kind: 'file',
      language: 'go',
      lines: 540,
      cyclomatic: 96,
      churnAbsolute: 54,
      churnRelative: 0.1,
      changeFrequency: 6,
      hotspotScore: 0.3,
      ageDays: 64,
    },
    {
      path: 'libs/go/observability/clock.go',
      kind: 'file',
      language: 'go',
      lines: 90,
      cyclomatic: 8,
      churnAbsolute: 9,
      churnRelative: 0.1,
      changeFrequency: 2,
      hotspotScore: 0.05,
      ageDays: 120,
    },
  ],
  couplings: [],
  ownership: [],
  summary: {
    lines: 2470,
    entityCount: 3,
    technicalDebtRatio: 0.08,
    maintainabilityRating: 'B',
    busFactor: 1,
  },
  trends: [],
  views: [
    {
      id: 'hotspots',
      title: 'Hotspot map — Eden libs',
      primitive: 'hotspot-map',
      attentionPoint: 'pull-request',
      encoding: { ...DEFAULT_HOTSPOT_ENCODING },
      source: 'entities',
    },
  ],
};

const ENTITIES: readonly Entity[] = EDEN_LIBS_REPORT.entities;

describe('buildHotspotPlot — the pure render plan over the real Eden-libs Report', () => {
  const theme = generateTheme(C21_SEED);

  it('places the top hotspot (cases.go) at the TOP-RIGHT with the MAX colour', () => {
    const plot = buildHotspotPlot(
      ENTITIES,
      DEFAULT_HOTSPOT_ENCODING,
      theme,
      DEFAULT_PLOT_DIMENSIONS,
    );
    const cases = plot.points.find((p) => p.label === 'libs/go/agentsession/cases.go')!;
    const calm = plot.points.find((p) => p.label === 'libs/go/observability/clock.go')!;

    // cases.go has the max x (churnRelative 1.07) and max y (cyclomatic 216) → right edge + top.
    const xs = plot.points.map((p) => p.cx);
    const ys = plot.points.map((p) => p.cy);
    expect(cases.cx).toBe(Math.max(...xs)); // rightmost
    expect(cases.cy).toBe(Math.min(...ys)); // topmost (smallest pixel-y, y is flipped)

    // it carries the MAX hotspot colour (score 1.0 == the ramp's hot end), and it is the largest dot.
    expect(cases.colorValue).toBe(1);
    expect(cases.radius).toBe(Math.max(...plot.points.map((p) => p.radius)));

    // the calm helper sits bottom-left with the smallest dot.
    expect(calm.cx).toBe(Math.min(...xs));
    expect(calm.radius).toBe(Math.min(...plot.points.map((p) => p.radius)));
  });

  it('every placed point lies within the plot box', () => {
    const plot = buildHotspotPlot(
      ENTITIES,
      DEFAULT_HOTSPOT_ENCODING,
      theme,
      DEFAULT_PLOT_DIMENSIONS,
    );
    const { width, height, margin } = DEFAULT_PLOT_DIMENSIONS;
    for (const p of plot.points) {
      expect(p.cx).toBeGreaterThanOrEqual(margin);
      expect(p.cx).toBeLessThanOrEqual(width - margin);
      expect(p.cy).toBeGreaterThanOrEqual(margin);
      expect(p.cy).toBeLessThanOrEqual(height - margin);
    }
  });

  it('is PAYLOAD-DRIVEN: a different encoding re-binds the axes (generalizes to any scatter View)', () => {
    // bind x to changeFrequency instead of churnRelative — the same scales, a different field.
    const plot = buildHotspotPlot(
      ENTITIES,
      { ...DEFAULT_HOTSPOT_ENCODING, x: 'changeFrequency' },
      theme,
      DEFAULT_PLOT_DIMENSIONS,
    );
    const cases = plot.points.find((p) => p.label === 'libs/go/agentsession/cases.go')!;
    expect(cases.xValue).toBe(58); // now reads changeFrequency, not churnRelative
  });

  it('lays out a colour legend low→high (5 stops) and axis ticks', () => {
    const plot = buildHotspotPlot(
      ENTITIES,
      DEFAULT_HOTSPOT_ENCODING,
      theme,
      DEFAULT_PLOT_DIMENSIONS,
    );
    expect(plot.legend).toHaveLength(5);
    expect(plot.legend[0]!.score).toBe(0);
    expect(plot.legend[plot.legend.length - 1]!.score).toBe(1);
    expect(plot.xTicks.length).toBeGreaterThanOrEqual(2);
    expect(plot.yTicks.length).toBeGreaterThanOrEqual(2);
  });
});

describe('the pure scale edge cases (hue short-arc + the label/space fallbacks)', () => {
  it('hotspotColorAt takes the SHORTER hue arc across the 0°/360° seam (a two-hue ramp)', () => {
    // a forged ramp 350° → 10°: the short arc is +20° (through 0°), NOT −340° through green.
    const ramp: HotspotRamp = { low: { l: 0.9, c: 0.1, h: 350 }, high: { l: 0.4, c: 0.1, h: 10 } };
    const mid = hotspotColorAt(0.5, ramp);
    // the midpoint hue lands at 0° (the seam), not ~180° (the long way round).
    expect(Math.min(mid.h, 360 - mid.h)).toBeLessThan(1);
  });

  it('entityLabel returns the string field, else the empty string (never undefined)', () => {
    const e = {
      path: 'a/b.ts',
      kind: 'file',
      lines: 1,
      churnAbsolute: 0,
      churnRelative: 0,
      changeFrequency: 0,
      hotspotScore: 0,
      ageDays: 0,
    } satisfies Entity;
    expect(entityLabel(e, 'path')).toBe('a/b.ts');
    expect(entityLabel(e, 'lines')).toBe(''); // a numeric field is not a label
    expect(entityLabel(e, 'missing')).toBe('');
  });
});

describe('deriveHotspotMapTokens — defensive totality on a degenerate theme (empty scales)', () => {
  it('falls back to 0/inherit when typography + spacing are empty (the totality contract)', () => {
    const base = generateTheme(C21_SEED);
    // a theme stripped of its generated typography + spacing (never produced by generateTheme; this
    // exercises the fallback arms that keep the derivation total without a non-null assertion).
    const degenerate: Theme = { ...base, typography: [], spacing: [] };
    const t = deriveHotspotMapTokens(degenerate);
    expect(t.tickLabelSizePx).toBe(0);
    expect(t.labelSizePx).toBe(0);
    expect(t.labelLineHeightPx).toBe(0);
    expect(t.fontFamily).toBe('inherit');
    expect(t.paddingPx).toBe(0);
    expect(t.gapPx).toBe(0);
    expect(t.radiusPx).toBe(0);
    // the colours + hit target (which read roles + controlGeometry, still present) stay derived.
    expect(t.plotBackground).toContain('oklch(');
    expect(t.hitTargetPx).toBeGreaterThanOrEqual(44);
  });

  it('falls back to body then the first role when the named typography role is absent', () => {
    const base = generateTheme(C21_SEED);
    const body = base.typography.find((r) => r.name === 'body')!;
    // drop caption + label so roleSizePx falls through to the body role (the ?? body arm).
    const noCaption: Theme = {
      ...base,
      typography: base.typography.filter((r) => r.name !== 'caption' && r.name !== 'label'),
    };
    const t = deriveHotspotMapTokens(noCaption);
    expect(t.tickLabelSizePx).toBe(body.fontSizePx);
    expect(t.labelSizePx).toBe(body.fontSizePx);
  });
});

describe('deriveHotspotMapTokens / hotspotMapStyleVars — the derived chrome', () => {
  const theme: Theme = generateTheme(C21_SEED);

  it('the plot is the prose surface; the axis is the outline role (one home — @eden/theme roles)', () => {
    const t = deriveHotspotMapTokens(theme);
    expect(t.foregroundOklch).toEqual(theme.roles.onSurface.value);
    expect(t.plotBackgroundOklch).toEqual(theme.roles.surface.value);
    expect(t.axisOklch).toEqual(theme.roles.outline.value);
    expect(t.hitTargetPx).toBe(hitTargetPx(theme));
  });

  it('emits oklch() + px custom properties, no hand-set hex', () => {
    const css = hotspotMapStyleVars(deriveHotspotMapTokens(theme));
    expect(css).toContain('--eden-hotspot-map-plot-bg: oklch(');
    expect(css).toContain('--eden-hotspot-map-padding: 16px;');
    expect(css).toContain('--eden-hotspot-map-hit-target: ');
    expect(css).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
  });
});

describe('HotspotMap.svelte — the real component', () => {
  it('renders an accessible figure named by the title, with a description of the encoding', () => {
    const { getByRole, getByText } = render(HotspotMap, { props: { entities: ENTITIES } });
    const group = getByRole('group', { name: 'Hotspot map: churn versus complexity' });
    expect(group).toBeTruthy();
    // the encoding description is announced (a visually-hidden <p>, not a role="img" that would
    // present-away the interactive points).
    const description = getByText(/Scatter of 3 entities/);
    expect(description.textContent).toContain('churnRelative');
    expect(description.textContent).toContain('cyclomatic');
  });

  it('every point is a keyboard-focusable button carrying its path + metrics (colour is never alone)', () => {
    const { getAllByRole } = render(HotspotMap, { props: { entities: ENTITIES } });
    const targets = getAllByRole('button');
    expect(targets).toHaveLength(ENTITIES.length);
    const top = targets.find((el) => (el.getAttribute('aria-label') ?? '').includes('cases.go'))!;
    expect(top.getAttribute('aria-label')).toContain('churnRelative 1.07');
    expect(top.getAttribute('aria-label')).toContain('cyclomatic 216');
    expect(top.getAttribute('tabindex')).toBe('0');
  });

  it('renders the OFFSCREEN data-table fallback enumerating every entity', () => {
    const { getByRole, getAllByRole } = render(HotspotMap, { props: { entities: ENTITIES } });
    const table = getByRole('table');
    expect(table).toBeTruthy();
    // a header row + one row per entity.
    const rows = getAllByRole('row');
    expect(rows.length).toBe(ENTITIES.length + 1);
  });

  it('binds the derived plot-bg var into the figure inline style', () => {
    const theme = generateTheme(C21_SEED);
    const { container } = render(HotspotMap, { props: { entities: ENTITIES, theme } });
    const figure = container.querySelector('[data-eden-hotspot-map]')!;
    const tokens = deriveHotspotMapTokens(theme);
    expect(figure.getAttribute('style')).toContain(
      `--eden-hotspot-map-plot-bg: ${tokens.plotBackground}`,
    );
  });

  it('renders an empty scatter without throwing (no entities → no points, the figure still present)', () => {
    const { getByRole, getByText, queryAllByRole } = render(HotspotMap, {
      props: { entities: [] },
    });
    expect(getByRole('group')).toBeTruthy();
    expect(getByText(/Scatter of 0 entities/)).toBeTruthy();
    expect(queryAllByRole('button')).toHaveLength(0);
  });
});
