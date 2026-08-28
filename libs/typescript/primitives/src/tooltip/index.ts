/**
 * `@eden/primitives` — the Tooltip public surface.
 *
 * Re-exports the Tooltip component. The shared overlay token math lives once in
 * `../overlay/tokens.ts` (cited there — one concept, one home). The Tooltip is the tooltip-layer
 * SELECTION of that shared overlay surface.
 */
export { default as Tooltip } from './tooltip.svelte';
