/**
 * `@eden/theme` — the design-system token engine (ADR-0024, docs/research/05-design-foundations.md).
 *
 * A small brand SEED (a primary hue + optional hues, font families, a type ratio, a base unit) is
 * fed through research-derived tables and pure deterministic functions to GENERATE a complete,
 * proportional, accessible design-token system. The seed carries TASTE; the tables carry perceptual
 * floors + proportional structure; the generator composes them (research §1). The accessibility
 * CONTRAST GATE is a HARD CONSTRAINT the pipeline satisfies by construction (research §B.4/§C.3).
 *
 * Framework-agnostic: this lib is DATA + a GENERATOR. Bits-UI is the (later) behavior primitive per
 * RD-16; components consume these tokens, never the reverse. MATH IS SOURCE OF TRUTH (ADR-0024 §7):
 * C21's five LOCKED colors + three fonts are SEEDS — every scale value is derived, never hand-set.
 *
 * This barrel is a pure re-export (no logic; excluded from the coverage floor — see vitest.config).
 */

// ── color science: OKLCH ↔ sRGB via the verbatim research matrices (research §B.3) ────────────
export {
  type Srgb,
  type OkLab,
  type OkLch,
  srgbChannelToLinear,
  linearToSrgbChannel,
  srgbToOkLab,
  okLabToSrgb,
  okLabToOkLch,
  okLchToOkLab,
  srgbToOkLch,
  okLchToSrgb,
} from './oklch.js';

// ── sRGB 8-bit codec — the seed's one hex crossing (research §B.3/§B.4) ───────────────────────
export {
  type Srgb8,
  HexParseError,
  parseHex,
  srgbTo8,
  srgb8To,
  formatHex,
  hexToOkLch,
  okLchTo8,
} from './srgb.js';

// ── gamut mapping (research Algorithm B3-D) ───────────────────────────────────────────────────
export { gamutMapOkLch } from './gamut.js';

// ── the contrast gate — the HARD CONSTRAINT (research §B.4) ───────────────────────────────────
export {
  type WcagLevel,
  type ContentClass,
  type ContrastResult,
  relativeLuminance,
  wcagContrastRatio,
  wcagTarget,
  wcagPasses,
  apcaLc,
  nearestPassingForeground,
} from './contrast.js';

// ── color ramps — the OKLCH tonal palette (research §B.3) ─────────────────────────────────────
export {
  type RampStep,
  type ColorRamp,
  RAMP_STEPS,
  LIGHTNESS_LADDER,
  CHROMA_ENVELOPE,
  nearestRampStep,
  generateRamp,
} from './ramp.js';

// ── typography scale (research §B.1) ──────────────────────────────────────────────────────────
export {
  type FluidRange,
  type FluidType,
  BASE_SIZE_PX,
  DEFAULT_TYPE_RATIO,
  BODY_LINE_HEIGHT_FLOOR,
  typeSizePx,
  lineHeight,
  trackingEm,
  fluidType,
} from './typography.js';

// ── spacing, grid & breakpoints — BRAND-INVARIANT (research §B.2) ─────────────────────────────
export {
  type SpaceToken,
  type Breakpoint,
  BASE_UNIT_PX,
  TARGET_FLOOR_PX,
  PROSE_MEASURE_CH,
  BREAKPOINTS,
  generateSpacingRamp,
} from './spacing.js';

// ── density & adaptivity (research §B.6) ──────────────────────────────────────────────────────
export {
  type DensityTier,
  type DensityMode,
  type TargetContext,
  type BaseGeometry,
  type DensifiedGeometry,
  DENSITY_STEP,
  DEFAULT_DENSITY,
  DENSITY_MODES,
  RECOMMENDED_DENSITY_MODE,
  EXPERT_DENSITY_MODE,
  DENSITY_MODE_TIER,
  densityTierForMode,
  snap4,
  densify,
} from './density.js';

// ── motion & elevation (research §B.5) ────────────────────────────────────────────────────────
export {
  type DurationToken,
  type CubicBezier,
  type Spring,
  type ShadowLayer,
  DURATION_LADDER,
  EASING,
  EMPHASIZED_SPLINE_PATH,
  SHADOW_ALPHA0,
  SPRING_PRESETS,
  Z_INDEX,
  emphasizedLinearFallback,
  spring,
  layeredShadow,
} from './motion.js';

// ── the unified DTCG token model (research §C.1) ──────────────────────────────────────────────
export {
  type TokenType,
  type ContrastAudit,
  type EdenExtensions,
  type TokenExtensions,
  type ColorToken,
  type DimensionToken,
  type NumberToken,
  type TypographyValue,
  type TypographyToken,
  type DurationValue,
  type DurationToken as DtcgDurationToken,
  type CubicBezierEden,
  type CubicBezierExtensions,
  type CubicBezierToken,
  type ShadowToken,
} from './dtcg.js';

// ── the seed (research §C.2) + the C21 reference brand (D2 / ADR-0024 §7) ─────────────────────
export {
  type FontFamilies,
  type BrandHues,
  type ThemeSeed,
  C21_SEED,
  C21_SURFACE,
} from './seed.js';

// ── generateTheme(seed) — the seed → complete-token-set pipeline (research §C.3) ──────────────
export {
  type ThemeMode,
  type RoleColor,
  type RoleSet,
  type Theme,
  type TypographyRole,
  type MotionSlice,
  type GenerateOptions,
  generateTheme,
} from './generate.js';

// ── CSS custom-property emission (research §C.4) ──────────────────────────────────────────────
export { oklchToCss, themeToCssVariables } from './css.js';
