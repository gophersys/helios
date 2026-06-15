/**
 * `generateTheme(seed)` — the seed → complete-token-set pipeline (research §C.3).
 *
 * This is the keystone: it composes the color ramps (with the seed pinned), assigns M3 tone→role
 * roles (Table B3-E) per mode, runs the CONTRAST GATE as a HARD CONSTRAINT on every text/UI pair
 * (the only place a brand input can be overridden — research §C.3), and emits the typography,
 * spacing, motion, elevation, and density slices. The artifact carries the `eden.contrast` proof
 * on every `on-*` pair, so "the theme is accessible" is a checked property of the build (§C.3).
 *
 * MATH IS SOURCE OF TRUTH (ADR-0024 §7): every value flows from the research tables; the seed
 * contributes only hue/chroma/font/ratio.
 */

import { hexToOkLch, srgbTo8 } from './srgb.js';
import { gamutMapOkLch } from './gamut.js';
import { type OkLch, okLchToSrgb } from './oklch.js';
import { generateRamp, nearestRampStep, type ColorRamp } from './ramp.js';
import {
  nearestPassingForeground,
  type ContrastResult,
  type WcagLevel,
  type ContentClass,
} from './contrast.js';
import {
  typeSizePx,
  lineHeight,
  trackingEm,
  fluidType,
  DEFAULT_TYPE_RATIO,
  BASE_SIZE_PX,
} from './typography.js';
import { generateSpacingRamp, BREAKPOINTS, type SpaceToken, type Breakpoint } from './spacing.js';
import {
  DENSITY_STEP,
  DEFAULT_DENSITY,
  densify,
  type DensityTier,
  type DensifiedGeometry,
} from './density.js';
import {
  DURATION_LADDER,
  EASING,
  emphasizedLinearFallback,
  spring,
  SPRING_PRESETS,
  layeredShadow,
  Z_INDEX,
  type CubicBezier,
  type ShadowLayer,
  type Spring,
} from './motion.js';
import type { ContrastAudit } from './dtcg.js';
import type { ThemeSeed } from './seed.js';

/** A rendered mode of the theme — the color axis (research §C.2: light/dark). */
export type ThemeMode = 'light' | 'dark';

/** The semantic state-hue ramps — near-STATIC cultural signals (research §B.3). */
const STATE_HUE_DEG = { error: 27, warning: 78, success: 145, info: 230 } as const;

/** A semantic-role color resolved for a mode, with its contrast proof when it is a foreground. */
export interface RoleColor {
  /** The OKLCH value of this role in the active mode. */
  readonly value: OkLch;
  /** The contrast audit, present on every `on-*` foreground (research §C.3 sidecar). */
  readonly contrast?: ContrastAudit;
}

/** The full semantic role set for a mode (research Table B3-E — the M3 tone→role assignments). */
export interface RoleSet {
  readonly surface: RoleColor;
  readonly onSurface: RoleColor;
  readonly primary: RoleColor;
  readonly onPrimary: RoleColor;
  readonly primaryContainer: RoleColor;
  readonly onPrimaryContainer: RoleColor;
  readonly secondary: RoleColor;
  readonly outline: RoleColor;
  readonly error: RoleColor;
  readonly onError: RoleColor;
  readonly warning: RoleColor;
  readonly success: RoleColor;
  readonly info: RoleColor;
}

/** The complete generated theme (research §C.3 return). */
export interface Theme {
  /** The mode this theme was rendered for. */
  readonly mode: ThemeMode;
  /** The density tier this theme was rendered for. */
  readonly density: DensityTier;
  /** The Tier-1 primitive color ramps (brand-only, mode-agnostic; research §B.3 two-tier). */
  readonly ramps: {
    readonly primary: ColorRamp;
    readonly secondary: ColorRamp;
    readonly tertiary: ColorRamp;
    readonly neutral: ColorRamp;
  };
  /** The Tier-2 semantic roles, resolved for {@link mode} with the contrast gate applied. */
  readonly roles: RoleSet;
  /** The typography roles (re-derived from the seed ratio; research §B.1). */
  readonly typography: readonly TypographyRole[];
  /** The brand-invariant spacing ramp (research §B.2). */
  readonly spacing: readonly SpaceToken[];
  /** The breakpoint config (research §B.2). */
  readonly breakpoints: readonly Breakpoint[];
  /** The density-transformed control geometry for the active tier (research §B.6). */
  readonly controlGeometry: DensifiedGeometry;
  /** The motion slice (durations, easing, springs, shadows, z-index; research §B.5). */
  readonly motion: MotionSlice;
}

/** One typography role's resolved values (research §B.1 composite typography token). */
export interface TypographyRole {
  readonly name: string;
  readonly fontFamily: string;
  readonly fontSizePx: number;
  readonly lineHeight: number;
  readonly letterSpacingEm: number;
  readonly fluidCss: string | undefined;
}

/** The motion slice of a theme (research §B.5). */
export interface MotionSlice {
  readonly durations: typeof DURATION_LADDER;
  readonly easing: Readonly<Record<string, CubicBezier>>;
  readonly emphasizedLinearFallback: string;
  readonly springs: Readonly<Record<string, Spring>>;
  readonly elevation: readonly {
    readonly level: number;
    readonly layers: readonly ShadowLayer[];
  }[];
  readonly zIndex: typeof Z_INDEX;
}

/** Options selecting the rendered axes (research §C.2: mode × density). */
export interface GenerateOptions {
  /** The color mode (default `light`). */
  readonly mode?: ThemeMode;
  /** The density tier (default `comfortable`; agent surfaces pass `compact` — OD-17-density-default). */
  readonly density?: DensityTier;
  /** The WCAG conformance level the contrast gate holds text to (default `AA`). */
  readonly level?: WcagLevel;
}

// ── role tone assignments (research Table B3-E, M3 baseline light/dark) ────────────────────────
// Tones are 0..100; we map a tone to the nearest ramp step's OKLCH lightness so the role draws
// from the SAME generated ramp (research §B.3: "the same generated ramps are reused — only the
// role→step mapping flips" for dark mode).

const toneToL = (tone: number): number => tone / 100;

function rampAtLightness(ramp: ColorRamp, targetL: number): OkLch {
  // Reuse the public seed-snap: pick the ramp step whose ladder lightness is nearest the target
  // tone, then read that step's OKLCH (research §B.3 — roles draw from the SAME generated ramp).
  return ramp.steps[nearestRampStep(targetL)];
}

/** A neutral OKLCH at an exact lightness (for surface/on-surface paper-ink anchors). */
function neutralAt(ramp: ColorRamp, l: number): OkLch {
  // Pull chroma to near-zero for true neutrals (surface/text), holding the neutral hue.
  return gamutMapOkLch({ l, c: Math.min(ramp.steps[500].c, 0.01), h: ramp.hue });
}

function deriveHue(hex: string | undefined, fallback: OkLch): OkLch {
  return hex === undefined ? fallback : hexToOkLch(hex);
}

/**
 * Resolve a foreground role against a background through the CONTRAST GATE (research §C.3). Returns
 * the gate-repaired color + its audit, so an inaccessible pair is repaired-by-construction, never
 * shipped.
 */
function gatedForeground(
  seedFg: OkLch,
  background: OkLch,
  contentClass: ContentClass,
  level: WcagLevel,
): RoleColor {
  const bg8 = srgbTo8(okLchToSrgb(background));
  const result: ContrastResult = nearestPassingForeground(seedFg, bg8, contentClass, level);
  const audit: ContrastAudit = {
    ratio: result.achievedRatio,
    target: result.targetRatio,
    level: result.level,
    apcaLc: result.apcaLc,
  };
  return { value: result.suggestedForeground, contrast: audit };
}

function buildRoles(ramps: Theme['ramps'], mode: ThemeMode, level: WcagLevel): RoleSet {
  const dark = mode === 'dark';
  const neutral = ramps.neutral;

  // Surface: light bg is high-tone (98–99), dark bg is low-tone (6–10) — research Table B3-E.
  const surface = neutralAt(neutral, dark ? toneToL(8) : toneToL(98));
  const onSurfaceL = dark ? toneToL(90) : toneToL(10);
  const onSurfaceSeed = neutralAt(neutral, onSurfaceL);
  // Primary: light tone 40, dark tone 80 (research Table B3-E).
  const primary = rampAtLightness(ramps.primary, dark ? toneToL(80) : toneToL(40));
  const primaryContainer = rampAtLightness(ramps.primary, dark ? toneToL(30) : toneToL(90));
  const secondary = rampAtLightness(ramps.secondary, dark ? toneToL(80) : toneToL(40));
  const outline = neutralAt(neutral, dark ? toneToL(60) : toneToL(50));

  // State ramps share the lightness ladder at the brand chroma scale but a fixed cultural hue.
  const stateRamp = (hueDeg: number): ColorRamp =>
    generateRamp({ l: toneToL(40), c: ramps.primary.steps[500].c, h: hueDeg });
  const errorRamp = stateRamp(STATE_HUE_DEG.error);
  const warningRamp = stateRamp(STATE_HUE_DEG.warning);
  const successRamp = stateRamp(STATE_HUE_DEG.success);
  const infoRamp = stateRamp(STATE_HUE_DEG.info);
  const error = rampAtLightness(errorRamp, dark ? toneToL(80) : toneToL(40));
  const warning = rampAtLightness(warningRamp, dark ? toneToL(80) : toneToL(45));
  const success = rampAtLightness(successRamp, dark ? toneToL(80) : toneToL(40));
  const info = rampAtLightness(infoRamp, dark ? toneToL(80) : toneToL(40));

  return {
    surface: { value: surface },
    // on-surface text is normal-text class → AA 4.5 (research Table B4-B), gate-repaired.
    onSurface: gatedForeground(onSurfaceSeed, surface, 'normal-text', level),
    primary: { value: primary },
    // on-primary text against the primary surface — normal text.
    onPrimary: gatedForeground(
      neutralAt(neutral, dark ? toneToL(20) : toneToL(100)),
      primary,
      'normal-text',
      level,
    ),
    primaryContainer: { value: primaryContainer },
    onPrimaryContainer: gatedForeground(
      rampAtLightness(ramps.primary, dark ? toneToL(90) : toneToL(30)),
      primaryContainer,
      'normal-text',
      level,
    ),
    secondary: { value: secondary },
    // outline is a UI-component contrast (research Table B4-B, ≥3.0), gated against the surface.
    outline: gatedForeground(outline, surface, 'ui-component', level),
    error: { value: error },
    onError: gatedForeground(
      neutralAt(neutral, dark ? toneToL(20) : toneToL(100)),
      error,
      'normal-text',
      level,
    ),
    warning: { value: warning },
    success: { value: success },
    info: { value: info },
  };
}

/** A typography role's static shape: its modular index, whether it is body text, font slot, fluidity. */
interface TypeRoleSpec {
  readonly name: string;
  /** The modular index `i` for `size = base·ratio^i` (research §B.1). */
  readonly index: number;
  /** Body text → the WCAG 1.4.12 ≥1.5× line-height floor applies (research B1-C). */
  readonly body: boolean;
  /** Which seed font slot this role renders in (display headings vs reading text). */
  readonly font: 'display' | 'text';
  /** Display/heading roles carry a fluid clamp() value (research §B.1). */
  readonly fluid: boolean;
}

const TYPE_ROLES: readonly TypeRoleSpec[] = [
  { name: 'display-large', index: 5, body: false, font: 'display', fluid: true },
  { name: 'display-small', index: 4, body: false, font: 'display', fluid: true },
  { name: 'headline', index: 3, body: false, font: 'display', fluid: true },
  { name: 'title', index: 2, body: false, font: 'display', fluid: false },
  { name: 'body-large', index: 1, body: true, font: 'text', fluid: false },
  { name: 'body', index: 0, body: true, font: 'text', fluid: false },
  { name: 'label', index: -1, body: false, font: 'text', fluid: false },
  { name: 'caption', index: -2, body: false, font: 'text', fluid: false },
];

function buildTypography(seed: ThemeSeed): readonly TypographyRole[] {
  const base = seed.baseSizePx ?? BASE_SIZE_PX;
  const ratio = seed.typeRatio ?? DEFAULT_TYPE_RATIO;
  const fluidRange = { minViewportPx: 600, maxViewportPx: 1400 };
  return TYPE_ROLES.map((role) => {
    const sizePx = typeSizePx(role.index, base, ratio);
    const family = role.font === 'display' ? seed.fonts.display : seed.fonts.text;
    const fluid = role.fluid
      ? fluidType(sizePx, typeSizePx(role.index + 1, base, ratio), fluidRange).css
      : undefined;
    return {
      name: role.name,
      fontFamily: family,
      fontSizePx: sizePx,
      lineHeight: lineHeight(sizePx, 60, role.body),
      letterSpacingEm: trackingEm(sizePx),
      fluidCss: fluid,
    };
  });
}

function buildMotion(): MotionSlice {
  return {
    durations: DURATION_LADDER,
    easing: EASING,
    emphasizedLinearFallback: emphasizedLinearFallback(),
    // OD-17-motion-personality resolved-as-default: a single neutral personality in v1 — we expose
    // the documented spring presets, derived through the corrected math, not a brand-driven choice.
    springs: {
      smooth: spring(SPRING_PRESETS.smooth.durationSec, SPRING_PRESETS.smooth.bounce),
      snappy: spring(SPRING_PRESETS.snappy.durationSec, SPRING_PRESETS.snappy.bounce),
      bouncy: spring(SPRING_PRESETS.bouncy.durationSec, SPRING_PRESETS.bouncy.bounce),
      legacy: spring(SPRING_PRESETS.legacy.durationSec, SPRING_PRESETS.legacy.bounce),
    },
    elevation: [1, 2, 3, 4, 6, 8, 12, 24].map((level) => ({
      level,
      layers: layeredShadow(level, 4, 'light'),
    })),
    zIndex: Z_INDEX,
  };
}

/**
 * Generate the complete token set from a seed (research §C.3 pipeline). The contrast gate runs as a
 * HARD CONSTRAINT on every text/UI pair; the result carries the `eden.contrast` proof. Pure: no
 * I/O, no clock, no globals (rule 10) — the same seed + options always yields the same theme.
 */
export function generateTheme(seed: ThemeSeed, options: GenerateOptions = {}): Theme {
  const mode: ThemeMode = options.mode ?? 'light';
  const density: DensityTier = options.density ?? 'comfortable';
  const level: WcagLevel = options.level ?? 'AA';

  // 1. COLOR — Tier-1 primitive ramps from the seed hues (research §B.3). Pin the seed identity.
  const primarySeed = hexToOkLch(seed.hues.primary);
  const neutralSeed = deriveHue(seed.hues.neutral, { ...primarySeed, c: 0.01 });
  const ramps = {
    primary: generateRamp(primarySeed),
    secondary: generateRamp(deriveHue(seed.hues.secondary, primarySeed)),
    tertiary: generateRamp(deriveHue(seed.hues.tertiary, primarySeed)),
    neutral: generateRamp(neutralSeed),
  };

  // 2. ROLES — Tier-2 semantic roles, mode-resolved, contrast-gated (research §B.3/§B.4/§C.3).
  const roles = buildRoles(ramps, mode, level);

  // 3. TYPOGRAPHY — re-derived from the seed ratio (research §B.1; D2 re-derives C21's sizes).
  const typography = buildTypography(seed);

  // 4. SPACING + GRID — brand-INVARIANT (research §B.2).
  const spacing = generateSpacingRamp();
  const breakpoints = BREAKPOINTS;

  // 5. DENSITY — the geometry transform for the active tier (research §B.6). A representative
  // control row (base d=0: height 40, inset 12, gap 16, font 14, icon 20) densified per tier.
  const controlGeometry = densify(
    { componentHeightPx: 40, insetPx: 12, gapPx: 16, fontSizePx: 14, iconSizePx: 20 },
    density,
  );

  // 6. MOTION + ELEVATION (research §B.5).
  const motion = buildMotion();

  return {
    mode,
    density,
    ramps,
    roles,
    typography,
    spacing,
    breakpoints,
    controlGeometry,
    motion,
  };
}

/** The density-step table re-exported for callers that resolve tiers (research Table B6-C). */
export { DENSITY_STEP, DEFAULT_DENSITY };
