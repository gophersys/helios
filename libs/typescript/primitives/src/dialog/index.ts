/**
 * `@eden/primitives` — the Dialog public surface.
 *
 * Re-exports the modal Dialog component (the bits-ui behavior layer + the token binding). The shared
 * overlay token math (`deriveOverlayTokens`, `overlayStyleVars`, `defaultOverlayTheme`, the
 * `OverlayLayer`/`OverlayTokens` types) lives once in `../overlay/tokens.ts` and is cited there —
 * one concept, one home. The Dialog is the modal-layer SELECTION of that shared overlay surface.
 */
export { default as Dialog } from './dialog.svelte';
