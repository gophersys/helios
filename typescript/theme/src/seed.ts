/**
 * @eden-seed-source — THE designated brand-seed source (the one auditable hex crossing).
 *
 * The theme SEED — the small brand input the generator expands into a complete token set.
 *
 * The thesis (research §1): a primary hue + a few optional hues + font families + a couple of
 * scalar preferences (type ratio, base unit) is SUFFICIENT to generate a complete, proportional,
 * accessible design-token system. The seed carries TASTE; the research tables carry the perceptual
 * floors + proportional structure; the generator composes them (research §1 / §C.3).
 *
 * The C21 seed (the founder's five LOCKED colors + three font families) is the reference brand.
 * D2 / ADR-0024 §7: the 5 colors + 3 fonts are IMMUTABLE seeds; the type sizes are RE-DERIVED for
 * harmony (never the hand-picked irregular C21 values). The hex literals below are the ONLY hex in
 * the lib and are SEEDS, not authored colors — they cross to OKLCH once at generation (see srgb.ts).
 */

/** The font-family slots the engine maps (research §C21: display/text/code). */
export interface FontFamilies {
  /** The display/heading family (serif). */
  readonly display: string;
  /** The body/text family (sans). */
  readonly text: string;
  /** The code/mono family. */
  readonly code: string;
}

/** The optional brand hue slots beyond the required primary (research §C.2 brand axis). */
export interface BrandHues {
  /** The primary brand seed — required (research §B.3: snapped + pinned to a ramp step). */
  readonly primary: string;
  /** The secondary brand seed (optional). */
  readonly secondary?: string;
  /** The tertiary brand seed (optional). */
  readonly tertiary?: string;
  /** The neutral seed (optional; absent → a desaturated primary-tinted neutral is derived). */
  readonly neutral?: string;
}

/**
 * The complete brand seed (research §C.2 brand axis). Hues are hex SEEDS; the type ratio + base
 * unit are the scalar preferences; the fonts are the family slots. State hues (success/warning/
 * error/info) are near-STATIC cultural signals (research §B.3) and are not part of the brand seed —
 * the generator supplies their fixed hues.
 */
export interface ThemeSeed {
  /** The brand hue seeds (hex strings — the seed's one hex crossing). */
  readonly hues: BrandHues;
  /** The font-family slots. */
  readonly fonts: FontFamilies;
  /** The type ratio preference (research Table B1-A; default the minor third 1.20). */
  readonly typeRatio?: number;
  /** The base size px preference (research §B.1; default 16). */
  readonly baseSizePx?: number;
}

/**
 * The C21 reference seed — the founder's five LOCKED colors + three font families (intake C21,
 * `documents/design-system/tokens.json`; mirrored in docs/tools/render-html.mjs):
 *   Bone #F4F1E8 (background) · Ink #1A1A1A (text) · Deep Forest #243D2C (primary surface) ·
 *   Moss #5C7F5C (accent/primary) · Sage #A8B89C (support/secondary).
 * Fonts: Fraunces (display) · Inter (text) · JetBrains Mono (code).
 *
 * D2 / ADR-0024 §7: these are IMMUTABLE seeds. `Moss` is the primary brand hue (the accent the UI
 * leans on); `Sage` the secondary; `Deep Forest` the tertiary/deep surface; `Ink` the neutral.
 * The Bone/Ink paper-ink pair anchors the light surface, derived through the ramp + contrast gate.
 */
export const C21_SEED: ThemeSeed = Object.freeze({
  hues: {
    primary: '#5C7F5C', // Moss — the accent the UI leans on
    secondary: '#A8B89C', // Sage — support
    tertiary: '#243D2C', // Deep Forest — deep primary surface
    neutral: '#1A1A1A', // Ink — the neutral anchor
  },
  fonts: {
    display: 'Fraunces',
    text: 'Inter',
    code: 'JetBrains Mono',
  },
  typeRatio: 1.2, // the minor third — research default for general UI (OD-17-type-ratio default)
  baseSizePx: 16,
});

/** The C21 paper/ink surface anchors (the two locked surface colors; research §B.3 surface roles). */
export const C21_SURFACE = Object.freeze({
  /** Bone — the light surface/background. */
  paper: '#F4F1E8',
  /** Ink — the on-surface text. */
  ink: '#1A1A1A',
});
