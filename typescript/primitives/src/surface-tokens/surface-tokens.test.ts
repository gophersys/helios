/**
 * surface-tokens — unit contract for the shared Wave-1 surface vocabulary (ADR-0024, doc 17 §3/§4).
 *
 * The single home for the wave's radii (control/surface/sheet), elevations (raised/overlay), and the
 * status/health role selection (the Clusters vocabulary). This suite asserts each derivation directly
 * and assertion-richly (every branch + the exact ramp step / role / shadow segment) so a mutated
 * mapping, ramp key, alpha, or level is killed — the mutation floor (75) rides on these.
 */
import { describe, expect, it } from 'vitest';
import { generateTheme, C21_SEED, oklchToCss, type Theme } from '@eden/theme';
import {
  radiusPx,
  elevationShadow,
  statusRole,
  statusRoleOklch,
  statusTint,
  type Radius,
  type Elevation,
  type Status,
} from './tokens.js';

const theme: Theme = generateTheme(C21_SEED);

describe('radiusPx — the three named radii are exact spacing-ramp steps (doc 17 §3)', () => {
  const rampByName = (name: string): number => theme.spacing.find((s) => s.name === name)!.px;

  it('control → space-1, surface → space-2, sheet → space-3 (the monotonic radius set)', () => {
    expect(radiusPx(theme, 'control')).toBe(rampByName('space-1'));
    expect(radiusPx(theme, 'surface')).toBe(rampByName('space-2'));
    expect(radiusPx(theme, 'sheet')).toBe(rampByName('space-3'));
  });

  it('the default-theme radii are the exact ramp px (4 / 8 / 12) — a scale value, not eyeballed', () => {
    expect(radiusPx(theme, 'control')).toBe(4);
    expect(radiusPx(theme, 'surface')).toBe(8);
    expect(radiusPx(theme, 'sheet')).toBe(12);
  });

  it('every radius is on the generated spacing ramp (membership oracle)', () => {
    const ramp = theme.spacing.map((s) => s.px);
    for (const r of ['control', 'surface', 'sheet'] as const) {
      expect(ramp).toContain(radiusPx(theme, r));
    }
  });

  it('the radii are strictly monotonic control < surface < sheet (distinct rungs, not aliased)', () => {
    const set: Radius[] = ['control', 'surface', 'sheet'];
    const [c, s, sh] = set.map((r) => radiusPx(theme, r));
    expect(c).toBeLessThan(s!);
    expect(s!).toBeLessThan(sh!);
  });
});

describe('elevationShadow — the raised/overlay shadows are composed from the theme motion recipe', () => {
  it('raised draws the level-2 elevation layers; overlay draws level-8 (distinct, deeper) layers', () => {
    const raised = elevationShadow(theme, 'raised');
    const overlay = elevationShadow(theme, 'overlay');
    const level2 = theme.motion.elevation.find((e) => e.level === 2)!;
    const level8 = theme.motion.elevation.find((e) => e.level === 8)!;
    // one box-shadow segment per generated layer (a comma-joined stack)
    expect(raised.split(',').length).toBe(level2.layers.length);
    expect(overlay.split(',').length).toBe(level8.layers.length);
    // the overlay lift is a DEEPER shadow than the raised one (distinct levels, not aliased)
    expect(overlay).not.toBe(raised);
  });

  it('each shadow segment carries the on-surface umbra at the layer alpha (a derived umbra, no hex)', () => {
    const raised = elevationShadow(theme, 'raised');
    const umbra = theme.roles.onSurface.value;
    // the umbra hue/chroma/lightness are the on-surface role's (translucent), never a pasted rgba/hex
    expect(raised).toContain(`${String(Math.round(umbra.l * 10000) / 10000)} `);
    expect(raised).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
    expect(raised).not.toContain('rgba');
    // the alpha of the first layer appears in the emitted string (the derived falloff)
    const a0 = theme.motion.elevation.find((e) => e.level === 2)!.layers[0]!.alpha;
    expect(raised).toContain(`/ ${String(a0)}`);
  });

  it('the shadow offsets are the theme layer offsets in px (the B5-E formula, not invented)', () => {
    const raised = elevationShadow(theme, 'raised');
    const layer0 = theme.motion.elevation.find((e) => e.level === 2)!.layers[0]!;
    expect(raised).toContain(`${String(layer0.offsetXPx)}px ${String(layer0.offsetYPx)}px`);
  });

  const ELEVATIONS: Elevation[] = ['raised', 'overlay'];
  it('every elevation composes a non-empty, hex-free box-shadow', () => {
    for (const e of ELEVATIONS) {
      const s = elevationShadow(theme, e);
      expect(s.length).toBeGreaterThan(0);
      expect(s).toMatch(/oklch\(/);
      expect(s).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
    }
  });
});

describe('statusRole* — the Clusters health vocabulary maps to the exact semantic roles', () => {
  const CASES: readonly [Status, keyof Theme['roles']][] = [
    ['healthy', 'success'],
    ['updating', 'info'],
    ['degraded', 'warning'],
    ['down', 'error'],
    ['unknown', 'outline'],
    ['neutral', 'outline'],
    ['accent', 'primary'],
  ];

  it('each status resolves to its exact role OKLCH (the Clusters status.ts mapping)', () => {
    for (const [status, role] of CASES) {
      expect(statusRoleOklch(status, theme)).toEqual(theme.roles[role].value);
      expect(statusRole(status, theme)).toBe(oklchToCss(theme.roles[role].value));
    }
  });

  it('the health hues are DISTINCT — healthy/updating/degraded/down are four different colours', () => {
    const healthy = oklchToCss(statusRoleOklch('healthy', theme));
    const updating = oklchToCss(statusRoleOklch('updating', theme));
    const degraded = oklchToCss(statusRoleOklch('degraded', theme));
    const down = oklchToCss(statusRoleOklch('down', theme));
    expect(new Set([healthy, updating, degraded, down]).size).toBe(4);
  });

  it('unknown and neutral both alias the outline role (the same quiet colour)', () => {
    expect(statusRoleOklch('unknown', theme)).toEqual(statusRoleOklch('neutral', theme));
    expect(statusRoleOklch('unknown', theme)).toEqual(theme.roles.outline.value);
  });

  it('accent is the primary role — distinct from every health hue', () => {
    expect(statusRoleOklch('accent', theme)).toEqual(theme.roles.primary.value);
    expect(statusRoleOklch('accent', theme)).not.toEqual(statusRoleOklch('healthy', theme));
  });
});

describe('statusTint — a translucent VIEW of the status role (the Clusters wash)', () => {
  it('the tint carries the role L/C/H verbatim with the given alpha appended (no colour invented)', () => {
    const alpha = 0.12;
    const role = statusRoleOklch('down', theme);
    const tint = statusTint('down', theme, alpha);
    const r4 = (n: number): string => String(Math.round(n * 10000) / 10000);
    expect(tint).toBe(`oklch(${r4(role.l)} ${r4(role.c)} ${r4(role.h)} / ${String(alpha)})`);
  });

  it('a higher alpha yields a stronger (different) wash — the border vs fill distinction', () => {
    const fill = statusTint('healthy', theme, 0.12);
    const edge = statusTint('healthy', theme, 0.35);
    expect(fill).not.toBe(edge);
    expect(edge).toContain('/ 0.35');
    expect(fill).toContain('/ 0.12');
  });
});

describe('totality — the fallback branches keep every function total (drive the guards)', () => {
  it('radiusPx falls back to controlGeometry.insetPx when the ramp lacks the rung', () => {
    // Drive the rampStepPx fallback: a ramp missing space-2 → radiusPx(surface) uses insetPx.
    const noSpace2 = { ...theme, spacing: theme.spacing.filter((s) => s.name !== 'space-2') };
    expect(radiusPx(noSpace2, 'surface')).toBe(theme.controlGeometry.insetPx);
    // the other radii are unaffected (space-1 / space-3 still present)
    expect(radiusPx(noSpace2, 'control')).toBe(theme.spacing.find((s) => s.name === 'space-1')!.px);
  });

  it('elevationShadow is empty when the theme carries no elevation ladder at all (total)', () => {
    const noElevation = { ...theme, motion: { ...theme.motion, elevation: [] } };
    expect(elevationShadow(noElevation, 'raised')).toBe('');
  });

  it('elevationShadow falls back to the FIRST ladder entry when the named level is absent', () => {
    // A ladder lacking level 2 (raised) but carrying one other entry → the `?? elevation[0]` fallback
    // uses that first entry's layers (a non-empty, well-formed shadow).
    const oneLevel = {
      ...theme,
      motion: {
        ...theme.motion,
        elevation: [theme.motion.elevation.find((e) => e.level === 8)!],
      },
    };
    const shadow = elevationShadow(oneLevel, 'raised');
    expect(shadow).not.toBe('');
    expect(shadow).toMatch(/oklch\(.* \/ /);
  });
});
