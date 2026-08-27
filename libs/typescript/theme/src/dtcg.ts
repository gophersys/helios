/**
 * The unified DTCG token model (research §C.1) — the `$type`s the generated system spans.
 *
 * These mirror the Design Tokens Community Group format (`$type`/`$value`/`$extensions`). Every
 * generated token carries its `$type`; color values are OKLCH; composites (typography, shadow,
 * transition) nest. Eden-specific data (spring, z-index, elevation overlay, the CONTRAST AUDIT,
 * density policy) rides `$extensions.eden.*` (research §C.1 last row). The contrast audit sidecar
 * is what makes "the theme is accessible" a CHECKED property of the build, not a claim (§C.3).
 *
 * One concept, one home (10 §9): the token shapes are defined ONCE here and cited by the generator.
 */

import type { OkLch } from './oklch.js';
import type { CubicBezier, ShadowLayer, Spring } from './motion.js';
import type { ContrastResult } from './contrast.js';

/** The DTCG `$type` discriminants the engine emits (research §C.1 table). */
export type TokenType =
  | 'color'
  | 'dimension'
  | 'number'
  | 'typography'
  | 'shadow'
  | 'duration'
  | 'cubicBezier'
  | 'transition';

/** The Eden contrast-audit extension carried on every resolved `on-*` pair (research §C.1/§C.3). */
export interface ContrastAudit {
  /** The achieved unrounded WCAG ratio. */
  readonly ratio: number;
  /** The WCAG target the pair was held to. */
  readonly target: number;
  /** The conformance level. */
  readonly level: ContrastResult['level'];
  /** The advisory APCA Lc (signed). */
  readonly apcaLc: number;
}

/** The `$extensions.eden` namespace shape (research §C.1: spring/z/elevation/contrast/density). */
export interface EdenExtensions {
  /** A dark-mode override `$value` for a semantic color token (research §B.3 two-tier model). */
  readonly dark?: OkLch;
  /** The contrast audit, on `on-*`/state/focus tokens. */
  readonly contrast?: ContrastAudit;
  /** A spring's resolved physical parameters (research §B.5). */
  readonly spring?: Spring;
  /** The density scale policy for a geometry token (research §B.6: linear|leading|none). */
  readonly densityScale?: 'linear' | 'leading' | 'none';
}

/** The DTCG `$extensions` wrapper carrying the {@link EdenExtensions} namespace. */
export interface TokenExtensions {
  readonly eden?: EdenExtensions;
}

/** A DTCG color token (`$value` is OKLCH; research §C.1). */
export interface ColorToken {
  readonly $type: 'color';
  readonly $value: OkLch;
  readonly $extensions?: TokenExtensions;
}

/** A DTCG dimension token (px-valued geometry; research §C.1). */
export interface DimensionToken {
  readonly $type: 'dimension';
  readonly $value: number;
  readonly $extensions?: TokenExtensions;
}

/** A DTCG number token (line-height ratio, type ratio, z-index, opacity; research §C.1). */
export interface NumberToken {
  readonly $type: 'number';
  readonly $value: number;
}

/** The composite value of a {@link TypographyToken} (research §C.1: the typography role fields). */
export interface TypographyValue {
  readonly fontFamily: string;
  readonly fontSizePx: number;
  readonly fontWeight: number;
  readonly lineHeight: number;
  readonly letterSpacingEm: number;
  /** The optional resolved fluid clamp() string for display/heading roles (research §B.1). */
  readonly fluidCss?: string;
}

/** A DTCG composite typography token (research §C.1: family/size/weight/lineHeight/letterSpacing). */
export interface TypographyToken {
  readonly $type: 'typography';
  readonly $value: TypographyValue;
}

/** The value of a {@link DurationToken} — a magnitude + unit (research §C.1). */
export interface DurationValue {
  readonly value: number;
  readonly unit: 'ms';
}

/** A DTCG duration token (research §C.1). */
export interface DurationToken {
  readonly $type: 'duration';
  readonly $value: DurationValue;
}

/** The `eden` namespace of a {@link CubicBezierToken}'s extensions. */
export interface CubicBezierEden {
  readonly linearFallback?: string;
}

/** The Eden extension on a {@link CubicBezierToken}: the emphasized-easing `linear()` fallback. */
export interface CubicBezierExtensions {
  readonly eden?: CubicBezierEden;
}

/** A DTCG cubic-bezier token (research §C.1; emphasized also carries a linear() fallback). */
export interface CubicBezierToken {
  readonly $type: 'cubicBezier';
  readonly $value: CubicBezier;
  readonly $extensions?: CubicBezierExtensions;
}

/** A DTCG composite shadow token — a multi-layer ARRAY (research §C.1/§B.5). */
export interface ShadowToken {
  readonly $type: 'shadow';
  readonly $value: readonly ShadowLayer[];
}
