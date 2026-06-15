/**
 * OKLab / OKLCH color science — the sRGB↔OKLab conversion via the verbatim research matrices,
 * plus the sRGB gamma transfer with the corrected 0.04045 threshold.
 *
 * Every constant here is transcribed VERBATIM from docs/research/05-design-foundations.md §B.3
 * (Formula B3-A — "encode verbatim") and §B.4 (the corrected 0.04045 linearization threshold,
 * verifier correction #1). OKLab (Björn Ottosson, 2020) is perceptually uniform — equal numeric
 * steps ≈ equal perceived steps, with decorrelated axes — which is precisely why the token
 * generator works in OKLCH rather than HSL (research §B.3 Principles).
 *
 * MATH IS SOURCE OF TRUTH (ADR-0024 §7): no value here is invented; each cites its research line.
 */

/** A color in the sRGB cube, each channel a gamma-ENCODED value in [0, 1] (the on-the-wire form). */
export interface Srgb {
  /** Red, gamma-encoded, [0, 1]. */
  readonly r: number;
  /** Green, gamma-encoded, [0, 1]. */
  readonly g: number;
  /** Blue, gamma-encoded, [0, 1]. */
  readonly b: number;
}

/** A color in OKLab — perceptually-uniform Cartesian (L lightness, a/b opponent axes). */
export interface OkLab {
  /** Perceptual lightness, ~[0, 1] (0 black … 1 white). */
  readonly l: number;
  /** Green↔red opponent axis. */
  readonly a: number;
  /** Blue↔yellow opponent axis. */
  readonly b: number;
}

/**
 * A color in OKLCH — the cylindrical form of OKLab the token engine works in (research §B.3):
 * hue/chroma stay on-brand while only L moves, which is what makes the ramp + contrast gate sound.
 */
export interface OkLch {
  /** Perceptual lightness, ~[0, 1]. */
  readonly l: number;
  /** Chroma (colorfulness), ≥ 0. */
  readonly c: number;
  /** Hue angle in DEGREES, [0, 360). */
  readonly h: number;
}

/**
 * The sRGB gamma transfer, ENCODED → LINEAR (research §B.3 / §B.4, corrected threshold 0.04045).
 *
 * The 0.04045 boundary is the W3C May-2021 errata value, NOT the stale 0.03928 some libraries
 * still ship (verifier correction #1). Both bracket the same single 8-bit channel value, so no
 * pass/fail ever flips — but we hard-code 0.04045 and document it (research §B.4 Correction #1).
 */
export function srgbChannelToLinear(channel: number): number {
  return channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
}

/** The sRGB gamma transfer, LINEAR → ENCODED (research §B.3, threshold 0.0031308). */
export function linearToSrgbChannel(linear: number): number {
  return linear <= 0.0031308 ? 12.92 * linear : 1.055 * linear ** (1 / 2.4) - 0.055;
}

const cbrt = Math.cbrt;

/**
 * sRGB → OKLab (research §B.3 Formula B3-A, "encode verbatim"). Linearizes each channel, applies
 * the M1 (linear-sRGB → LMS) matrix, takes the cube root, then the M2 (LMS' → OKLab) matrix —
 * every coefficient transcribed exactly from the formula block.
 */
export function srgbToOkLab({ r, g, b }: Srgb): OkLab {
  const rl = srgbChannelToLinear(r);
  const gl = srgbChannelToLinear(g);
  const bl = srgbChannelToLinear(b);

  // M1: linear sRGB → LMS (research B3-A).
  const longCone = 0.4122214708 * rl + 0.5363325363 * gl + 0.0514459929 * bl;
  const mediumCone = 0.2119034982 * rl + 0.6806995451 * gl + 0.1073969566 * bl;
  const shortCone = 0.0883024619 * rl + 0.2817188376 * gl + 0.6299787005 * bl;

  const longRoot = cbrt(longCone);
  const mediumRoot = cbrt(mediumCone);
  const shortRoot = cbrt(shortCone);

  // M2: LMS' → OKLab (research B3-A).
  return {
    l: 0.2104542553 * longRoot + 0.793617785 * mediumRoot - 0.0040720468 * shortRoot,
    a: 1.9779984951 * longRoot - 2.428592205 * mediumRoot + 0.4505937099 * shortRoot,
    b: 0.0259040371 * longRoot + 0.7827717662 * mediumRoot - 0.808675766 * shortRoot,
  };
}

/**
 * OKLab → sRGB (the inverse of B3-A). The M2⁻¹ and M1⁻¹ matrices are the exact inverses of the
 * verbatim research matrices; channels are gamma-re-encoded. Channels are NOT clamped here — the
 * caller (gamut mapping) needs to detect out-of-[0,1] to know a color falls outside the sRGB gamut.
 */
export function okLabToSrgb({ l, a, b }: OkLab): Srgb {
  // M2⁻¹: OKLab → LMS' (the inverse of the research M2).
  const longRoot = l + 0.3963377774 * a + 0.2158037573 * b;
  const mediumRoot = l - 0.1055613458 * a - 0.0638541728 * b;
  const shortRoot = l - 0.0894841775 * a - 1.291485548 * b;

  const longCone = longRoot ** 3;
  const mediumCone = mediumRoot ** 3;
  const shortCone = shortRoot ** 3;

  // M1⁻¹: LMS → linear sRGB (the inverse of the research M1).
  const rl = 4.0767416621 * longCone - 3.3077115913 * mediumCone + 0.2309699292 * shortCone;
  const gl = -1.2684380046 * longCone + 2.6097574011 * mediumCone - 0.3413193965 * shortCone;
  const bl = -0.0041960863 * longCone - 0.7034186147 * mediumCone + 1.707614701 * shortCone;

  return {
    r: linearToSrgbChannel(rl),
    g: linearToSrgbChannel(gl),
    b: linearToSrgbChannel(bl),
  };
}

const RAD_TO_DEG = 180 / Math.PI;
const DEG_TO_RAD = Math.PI / 180;

/** OKLab → OKLCH (the polar form): `C = √(a²+b²)`, `H = atan2(b,a)` in degrees [0,360) (B3-A). */
export function okLabToOkLch({ l, a, b }: OkLab): OkLch {
  const c = Math.sqrt(a * a + b * b);
  let h = Math.atan2(b, a) * RAD_TO_DEG;
  if (h < 0) h += 360;
  return { l, c, h };
}

/** OKLCH → OKLab. */
export function okLchToOkLab({ l, c, h }: OkLch): OkLab {
  const hRad = h * DEG_TO_RAD;
  return { l, a: c * Math.cos(hRad), b: c * Math.sin(hRad) };
}

/** sRGB → OKLCH (the composition the ramp generator uses). */
export function srgbToOkLch(srgb: Srgb): OkLch {
  return okLabToOkLch(srgbToOkLab(srgb));
}

/** OKLCH → sRGB (un-clamped; see {@link okLabToSrgb}). */
export function okLchToSrgb(oklch: OkLch): Srgb {
  return okLabToSrgb(okLchToOkLab(oklch));
}
