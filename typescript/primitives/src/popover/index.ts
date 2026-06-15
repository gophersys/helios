/**
 * `@eden/primitives` — the Popover public surface.
 *
 * Re-exports the Popover component. The shared overlay token math lives once in
 * `../overlay/tokens.ts` (cited there — one concept, one home). The Popover is the dropdown-layer
 * SELECTION of that shared overlay surface.
 */
export { default as Popover } from './popover.svelte';
