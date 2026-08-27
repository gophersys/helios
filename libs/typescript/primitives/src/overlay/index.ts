/**
 * `@eden/primitives` — the shared overlay token surface.
 *
 * The ONE home (10 §9) for the portaled-overlay token math every overlay component (Dialog, Popover,
 * Tooltip, DropdownMenu) derives from. `deriveOverlayTokens` reads a generated `@eden/theme` and
 * emits the `--eden-overlay-*` CSS vars; `overlayStyleVars` serializes them for binding THROUGH the
 * bits-ui Portal (OD-1). The components SELECT a layer (`modal`/`dropdown`/`tooltip`) and cite this
 * math — they never re-derive a color or size.
 */
export {
  deriveOverlayTokens,
  overlayStyleVars,
  defaultOverlayTheme,
  type OverlayLayer,
  type OverlayTokens,
} from './tokens.js';
