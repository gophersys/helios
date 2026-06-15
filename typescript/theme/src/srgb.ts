/**
 * sRGB 8-bit codec — the ONLY place a hex string enters the engine: parsing a brand SEED.
 *
 * Authoring a color as a hand-set hex is the design-correctness cardinal sin (ADR-0024 §3, the
 * no-hand-set-hex provenance lint). But a brand SEED is, by definition, an external literal the
 * founder picked (C21's five locked colors). The engine ingests it ONCE here, converts to OKLCH,
 * and from then on every ramp step is DERIVED. The WCAG contrast math (research §B.4) is also
 * specified on 8-bit channels (`C8/255`), so the codec is load-bearing for the gate too.
 */

import type { Srgb } from './oklch.js';
import { srgbToOkLch, okLchToSrgb, type OkLch } from './oklch.js';

/** A color as three 8-bit integer channels, [0, 255] — the form WCAG luminance is specified on. */
export interface Srgb8 {
  /** Red channel, integer [0, 255]. */
  readonly r8: number;
  /** Green channel, integer [0, 255]. */
  readonly g8: number;
  /** Blue channel, integer [0, 255]. */
  readonly b8: number;
}

/** Thrown when a seed hex string is not a usable `#rgb` / `#rrggbb` literal. */
export class HexParseError extends Error {
  /** A stable, inspectable classification (rule 12 — inspect by type, not by string). */
  readonly kind = 'hex-parse-invalid' as const;
  constructor(message: string) {
    super(message);
    this.name = 'HexParseError';
  }
}

const HEX6 = /^#?([0-9a-fA-F]{6})$/;
const HEX3 = /^#?([0-9a-fA-F]{3})$/;

/**
 * Parse a brand-seed hex string (`#rrggbb` or `#rgb`) into 8-bit channels.
 *
 * @throws {HexParseError} if the string is not a 3- or 6-digit hex color.
 */
export function parseHex(hex: string): Srgb8 {
  const six = HEX6.exec(hex);
  if (six?.[1] !== undefined) {
    const n = Number.parseInt(six[1], 16);
    return { r8: (n >> 16) & 0xff, g8: (n >> 8) & 0xff, b8: n & 0xff };
  }
  const three = HEX3.exec(hex);
  if (three?.[1] !== undefined) {
    const [rNibble = '0', gNibble = '0', bNibble = '0'] = three[1];
    const dup = (nibble: string): number => Number.parseInt(nibble + nibble, 16);
    return { r8: dup(rNibble), g8: dup(gNibble), b8: dup(bNibble) };
  }
  throw new HexParseError(`not a #rgb or #rrggbb hex color: ${JSON.stringify(hex)}`);
}

const clamp01 = (x: number): number => (x < 0 ? 0 : x > 1 ? 1 : x);
const to255 = (channel: number): number => Math.round(clamp01(channel) * 255);

/** Quantize a continuous sRGB color (channels in [0,1]) to 8-bit channels (clamped, rounded). */
export function srgbTo8(srgb: Srgb): Srgb8 {
  return { r8: to255(srgb.r), g8: to255(srgb.g), b8: to255(srgb.b) };
}

/** Expand 8-bit channels to a continuous sRGB color (channels in [0,1]). */
export function srgb8To({ r8, g8, b8 }: Srgb8): Srgb {
  return { r: r8 / 255, g: g8 / 255, b: b8 / 255 };
}

/** Render 8-bit channels as a lowercase `#rrggbb` string (for CSS custom-property emission). */
export function formatHex({ r8, g8, b8 }: Srgb8): string {
  const hh = (n: number): string => n.toString(16).padStart(2, '0');
  return `#${hh(r8)}${hh(g8)}${hh(b8)}`;
}

/** Ingest a seed hex literal straight to OKLCH — the seed's one and only hex→math crossing. */
export function hexToOkLch(hex: string): OkLch {
  return srgbToOkLch(srgb8To(parseHex(hex)));
}

/** Quantize an OKLCH color to 8-bit sRGB channels (clamped to gamut by rounding). */
export function okLchTo8(oklch: OkLch): Srgb8 {
  return srgbTo8(okLchToSrgb(oklch));
}
