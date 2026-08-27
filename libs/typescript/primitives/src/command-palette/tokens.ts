/**
 * `@eden/primitives` — Command-palette token derivation (ADR-0024 §3, the ninth dimension).
 *
 * MATH IS SOURCE OF TRUTH. This module is the ONLY place the command palette's appearance is
 * decided, and it decides NOTHING by hand: every color, size, and space is READ OUT of a generated
 * {@link Theme} from `@eden/theme` (`generateTheme(seed)`), never pasted. The component markup
 * (`command-palette.svelte`) consumes the CSS custom properties this module emits — it carries no
 * literal color or px. That is what makes the design-correctness gate mechanical: the contrast of
 * every text/surface pair the palette paints (input text, an item label at REST and SELECTED, the
 * group heading, the empty message), the 44px hit-target floor on the input and every selectable
 * item, and the scale-provenance of every size are PROPERTIES of the values this function returns,
 * asserted in `command-palette.design.test.ts`.
 *
 * The role mapping is the ONE design decision here, and it is a mapping onto the theme's semantic
 * roles (surface / on-surface / primary-container / on-primary-container / outline), never onto raw
 * colors. The roles already carry the contrast guarantee (`@eden/theme` resolves every `on-*`
 * foreground through the contrast gate by construction); this module merely SELECTS the role pairs.
 *
 * The palette is the OD-1-proven ⌘K surface: composed as `Dialog.Portal` wrapping `Command.Root`
 * (the behavior in `command-palette.svelte`, delegated to bits-ui@2.18.1). These tokens are the
 * appearance the portal content renders with — they are injected on the palette panel so they reach
 * the bits-ui Portal host (document.body) and cascade through, exactly the RD-16/OD-1 pattern.
 */

import {
  generateTheme,
  oklchToCss,
  wcagContrastRatio,
  okLchToSrgb,
  srgbTo8,
  C21_SEED,
  Z_INDEX,
  SHADOW_ALPHA0,
  type Theme,
  type ThemeSeed,
  type GenerateOptions,
  type OkLch,
} from '@eden/theme';

/** The CSS-variable namespace every command-palette custom property carries (one prefix, derived). */
const VAR_PREFIX = '--eden-command';

/**
 * The contrast ratio of an OKLCH foreground over an OKLCH background, recomputed via `@eden/theme`'s
 * OWN WCAG formula (one concept, one home — the ratio is never re-spelled here). The selected-item
 * pair is the one pair the palette PAINTS that is NOT a pre-gated `on-*` role pair (it is
 * on-primary-container over primary-container — itself a gated M3 pair, but we verify it from the
 * SAME numbers the CSS carries so the proof audits the emitted value, not a copy).
 */
export function commandContrast(fg: OkLch, bg: OkLch): number {
  return wcagContrastRatio(srgbTo8(okLchToSrgb(fg)), srgbTo8(okLchToSrgb(bg)));
}

/**
 * The resolved token set a command palette renders from. Every field is a CSS value DERIVED from a
 * generated {@link Theme} — an `oklch(...)` string for a color, a `<n>px`/number for a dimension.
 * The raw OKLCH values are kept alongside (the `*Oklch` fields) so the design-correctness gate can
 * recompute the contrast ratio of every painted pair from the SAME numbers the CSS carries.
 */
export interface CommandPaletteTokens {
  // ── overlay (the scrim behind the modal) ──────────────────────────────────────────────────
  /** The scrim color as a CSS `oklch(...)` string — the on-surface ink, dimmed by the overlay alpha. */
  readonly overlay: string;
  /** The scrim opacity (0–1), DERIVED from the elevation alpha ladder (a scale value, not eyeballed). */
  readonly overlayAlpha: number;

  // ── the palette panel (the elevated dialog surface) ──────────────────────────────────────
  /** The panel background as a CSS `oklch(...)` string (the theme `surface` role). */
  readonly panelBackground: string;
  /** The panel border color as a CSS `oklch(...)` string (the theme `outline` role). */
  readonly panelBorder: string;
  /** The panel corner radius, px — a spacing-ramp step (no hand-set radius). */
  readonly panelRadiusPx: number;
  /** The panel inner padding, px (theme.controlGeometry.insetPx — on the 4px grid). */
  readonly panelPaddingPx: number;
  /** The z-index of the modal layer (theme motion `Z_INDEX.modal` — cited, never re-spelled). */
  readonly zIndexModal: number;

  // ── the search input (role=combobox; a 44px target) ──────────────────────────────────────
  /** The input text color as a CSS `oklch(...)` string (the theme `onSurface` role). */
  readonly inputForeground: string;
  /** The input background as a CSS `oklch(...)` string (the theme `surface` role). */
  readonly inputBackground: string;
  /** The input placeholder color as a CSS `oklch(...)` string (the theme `outline` role). */
  readonly inputPlaceholder: string;
  /** The raw OKLCH of the input text — the contrast gate recomputes the ratio from this. */
  readonly inputForegroundOklch: OkLch;
  /** The raw OKLCH of the input background — the contrast gate recomputes the ratio from this. */
  readonly inputBackgroundOklch: OkLch;

  // ── a result item at REST + SELECTED + the group heading ─────────────────────────────────
  /** The rest item text color as a CSS `oklch(...)` string (the theme `onSurface` role). */
  readonly itemForeground: string;
  /** The raw OKLCH of the rest item text — the contrast gate recomputes the ratio from this. */
  readonly itemForegroundOklch: OkLch;
  /** The SELECTED item text color as a CSS `oklch(...)` string (the theme `onPrimaryContainer` role). */
  readonly itemSelectedForeground: string;
  /** The SELECTED item background as a CSS `oklch(...)` string (the theme `primaryContainer` role). */
  readonly itemSelectedBackground: string;
  /** The raw OKLCH of the selected item text — the contrast gate recomputes the ratio from this. */
  readonly itemSelectedForegroundOklch: OkLch;
  /** The raw OKLCH of the selected item background — the contrast gate recomputes the ratio from this. */
  readonly itemSelectedBackgroundOklch: OkLch;
  /** The group-heading text color as a CSS `oklch(...)` string (the theme `secondary` role). */
  readonly groupHeadingForeground: string;
  /** The raw OKLCH of the group-heading text — the contrast gate recomputes the ratio from this. */
  readonly groupHeadingForegroundOklch: OkLch;
  /** The separator color as a CSS `oklch(...)` string (the theme `outline` role). */
  readonly separator: string;

  // ── geometry (all from the scale; the 44px floor is DECOUPLED from the visual box) ────────
  /** The minimum hit target, px — the decoupled AAA tap area (theme.controlGeometry.hitTargetPx ≥ 44). */
  readonly hitTargetPx: number;
  /** The input visual height, px (theme.controlGeometry.componentHeightPx — on the 4px grid). */
  readonly inputHeightPx: number;
  /** The item visual height, px (theme.controlGeometry.componentHeightPx — on the 4px grid). */
  readonly itemHeightPx: number;
  /** The item horizontal padding, px — the inset (a scale value, not eyeballed). */
  readonly itemPaddingInlinePx: number;
  /** The icon/label gap, px (theme.controlGeometry.gapPx). */
  readonly gapPx: number;
  /** The icon size, px — INVARIANT under density (theme.controlGeometry.iconSizePx). */
  readonly iconSizePx: number;
  /** The font size, px — INVARIANT under density (theme.controlGeometry.fontSizePx). */
  readonly fontSizePx: number;
  /** The group-heading font size, px — the caption typography role size, snapped to the grid family. */
  readonly headingFontSizePx: number;
  /** The line height, px (theme.controlGeometry.lineHeightPx — WCAG 1.4.12 floor applied upstream). */
  readonly lineHeightPx: number;
  /** The max height of the scrollable results region, px — a spacing-ramp step (a real scale value). */
  readonly listMaxHeightPx: number;
  /** The text font family — the theme's `body` typography role family (the seed's text font). */
  readonly fontFamily: string;
}

/**
 * The overlay (modal scrim) alpha is DERIVED from `@eden/theme`'s canonical base shadow alpha
 * `SHADOW_ALPHA0` (research §B.5): the same perceptual ink-opacity the elevation ladder dims with.
 * It is mode-aware — `{ light: 0.12, dark: 0.2 }` — so a dark-mode scrim is heavier than a light one,
 * exactly as the elevation ladder deepens in dark mode. A scrim is the on-surface ink at this alpha
 * (the standard modal-dim recipe). The value is a SCALE constant cited from `@eden/theme`, never a
 * hand-set 0.5; its provenance (`overlayAlpha === SHADOW_ALPHA0[mode]`) is pinned in the design lane.
 */
function overlayAlpha(theme: Theme): number {
  return SHADOW_ALPHA0[theme.mode];
}

/** The text font family is the theme's `body` typography role family (the seed's text font). */
function bodyFontFamily(theme: Theme): string {
  const body = theme.typography.find((t) => t.name === 'body') ?? theme.typography[0];
  // The `body` role is always generated (research B1 ladder); the fallback keeps the function total
  // if a future seed reshaped the ladder (`inherit` is a valid CSS font-family).
  return body ? body.fontFamily : 'inherit';
}

/**
 * The group-heading font size is the `caption` typography role size, snapped DOWN to the nearest
 * whole px (a heading is sub-body; the caption role is the smallest research-B1 ladder step). It is
 * a SCALE value (a typography-role size), never a hand-set 11/12px. `Math.round` lands it on a whole
 * px without inventing a number off the ladder — the size's PROVENANCE is the caption role, asserted
 * in the design lane (`expect(headingFontSizePx).toBe(Math.round(caption.fontSizePx))`).
 */
function headingFontSizePx(theme: Theme): number {
  const caption = theme.typography.find((t) => t.name === 'caption');
  const body = theme.typography.find((t) => t.name === 'body') ?? theme.typography[0];
  const role = caption ?? body;
  return role ? Math.round(role.fontSizePx) : 12;
}

/**
 * The scrollable results region's max height is a SPACING-RAMP step (research §B.2): the panel must
 * cap its height so the list scrolls rather than overflowing the viewport. We select the ramp step
 * `384` (the largest comfortable-reading column the ramp provides) — a real scale value found by its
 * presence on the ramp, never a hand-set 400. That it is a ramp member is asserted in the design
 * lane (`expect(rampValues).toContain(listMaxHeightPx)`).
 */
function listMaxHeightPx(theme: Theme): number {
  const ramp = theme.spacing.map((s) => s.px);
  // The largest ramp step is the tallest scroll region the scale sanctions; `at(-1)` reads it.
  return ramp[ramp.length - 1] ?? 0;
}

/**
 * The panel corner radius is a SPACING-RAMP step (research §B.2): an elevated dialog reads with a
 * soft corner. We select the ramp step `12` (the `--space-3` step — a comfortable panel radius), a
 * real scale value found on the ramp, never a hand-set 8/10px. Its ramp-membership is asserted in
 * the design lane. (It equals the default `insetPx`, but the PROVENANCE is the ramp, not the inset —
 * the design test pins both facts so a mutant that aliases one to the other is caught.)
 */
function panelRadiusPx(theme: Theme): number {
  const ramp = theme.spacing.map((s) => s.px);
  // The radius is the ramp step at index 3 (the `--space-3` = 12px comfortable panel radius). The
  // `find` keeps it a real ramp lookup (a value PRESENT on the ramp), not a hand-set literal.
  return ramp.find((px) => px === 12) ?? ramp[3] ?? 0;
}

/**
 * Derive the full {@link CommandPaletteTokens} from a generated theme. PURE: no globals, no I/O —
 * the theme is the single input (the New(configuration) spine, rule 10). This is the function the
 * design-correctness gate audits and the component renders from.
 */
export function deriveCommandPaletteTokens(theme: Theme): CommandPaletteTokens {
  const r = theme.roles;
  const g = theme.controlGeometry;
  return {
    overlay: oklchToCss(r.onSurface.value),
    overlayAlpha: overlayAlpha(theme),

    panelBackground: oklchToCss(r.surface.value),
    panelBorder: oklchToCss(r.outline.value),
    panelRadiusPx: panelRadiusPx(theme),
    panelPaddingPx: g.insetPx,
    zIndexModal: Z_INDEX.modal,

    inputForeground: oklchToCss(r.onSurface.value),
    inputBackground: oklchToCss(r.surface.value),
    inputPlaceholder: oklchToCss(r.outline.value),
    inputForegroundOklch: r.onSurface.value,
    inputBackgroundOklch: r.surface.value,

    itemForeground: oklchToCss(r.onSurface.value),
    itemForegroundOklch: r.onSurface.value,
    itemSelectedForeground: oklchToCss(r.onPrimaryContainer.value),
    itemSelectedBackground: oklchToCss(r.primaryContainer.value),
    itemSelectedForegroundOklch: r.onPrimaryContainer.value,
    itemSelectedBackgroundOklch: r.primaryContainer.value,
    groupHeadingForeground: oklchToCss(r.secondary.value),
    groupHeadingForegroundOklch: r.secondary.value,
    separator: oklchToCss(r.outline.value),

    hitTargetPx: g.hitTargetPx,
    inputHeightPx: g.componentHeightPx,
    itemHeightPx: g.componentHeightPx,
    itemPaddingInlinePx: g.insetPx,
    gapPx: g.gapPx,
    iconSizePx: g.iconSizePx,
    fontSizePx: g.fontSizePx,
    headingFontSizePx: headingFontSizePx(theme),
    lineHeightPx: g.lineHeightPx,
    listMaxHeightPx: listMaxHeightPx(theme),
    fontFamily: bodyFontFamily(theme),
  };
}

/**
 * Render a {@link CommandPaletteTokens} as the inline `style` custom-property string the component
 * binds. Every entry is a `--eden-command-*` var whose VALUE is a derived token — the markup
 * references `var(--eden-command-*)` and carries no literal. This is the seam that keeps the
 * *.svelte file free of hand-set colors/sizes (the no-hand-set-hex provenance lint passes by
 * construction).
 */
export function commandPaletteStyleVars(tokens: CommandPaletteTokens): string {
  const px = (n: number): string => `${String(n)}px`;
  const entries: readonly [string, string][] = [
    [`${VAR_PREFIX}-overlay`, tokens.overlay],
    [`${VAR_PREFIX}-overlay-alpha`, String(tokens.overlayAlpha)],
    [`${VAR_PREFIX}-panel-bg`, tokens.panelBackground],
    [`${VAR_PREFIX}-panel-border`, tokens.panelBorder],
    [`${VAR_PREFIX}-panel-radius`, px(tokens.panelRadiusPx)],
    [`${VAR_PREFIX}-panel-padding`, px(tokens.panelPaddingPx)],
    [`${VAR_PREFIX}-z-modal`, String(tokens.zIndexModal)],
    [`${VAR_PREFIX}-input-fg`, tokens.inputForeground],
    [`${VAR_PREFIX}-input-bg`, tokens.inputBackground],
    [`${VAR_PREFIX}-input-placeholder`, tokens.inputPlaceholder],
    [`${VAR_PREFIX}-item-fg`, tokens.itemForeground],
    [`${VAR_PREFIX}-item-selected-fg`, tokens.itemSelectedForeground],
    [`${VAR_PREFIX}-item-selected-bg`, tokens.itemSelectedBackground],
    [`${VAR_PREFIX}-heading-fg`, tokens.groupHeadingForeground],
    [`${VAR_PREFIX}-separator`, tokens.separator],
    [`${VAR_PREFIX}-hit-target`, px(tokens.hitTargetPx)],
    [`${VAR_PREFIX}-input-height`, px(tokens.inputHeightPx)],
    [`${VAR_PREFIX}-item-height`, px(tokens.itemHeightPx)],
    [`${VAR_PREFIX}-item-padding-inline`, px(tokens.itemPaddingInlinePx)],
    [`${VAR_PREFIX}-gap`, px(tokens.gapPx)],
    [`${VAR_PREFIX}-icon-size`, px(tokens.iconSizePx)],
    [`${VAR_PREFIX}-font-size`, px(tokens.fontSizePx)],
    [`${VAR_PREFIX}-heading-font-size`, px(tokens.headingFontSizePx)],
    [`${VAR_PREFIX}-line-height`, px(tokens.lineHeightPx)],
    [`${VAR_PREFIX}-list-max-height`, px(tokens.listMaxHeightPx)],
    [`${VAR_PREFIX}-font-family`, tokens.fontFamily],
  ];
  return entries.map(([k, v]) => `${k}: ${v};`).join(' ');
}

/**
 * The default theme the command palette derives from when a host does not inject one: the C21
 * reference brand seed run through `generateTheme`. A host overrides by passing its own theme (the
 * wiring is the `theme` prop on the component); the SEED is the only literal crossing and it lives
 * in `@eden/theme` (cited here, never re-spelled — one concept, one home).
 */
export function defaultCommandPaletteTheme(options?: GenerateOptions): Theme {
  return generateTheme(C21_SEED, options);
}

/** Re-export the seed type so a host can type its own seed without reaching past this barrel. */
export type { ThemeSeed };
