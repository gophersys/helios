/**
 * `@eden/primitives` — the DropdownMenu public surface.
 *
 * Re-exports the DropdownMenu component and its row type. The shared overlay token math lives once
 * in `../overlay/tokens.ts` (cited there — one concept, one home). The menu is the dropdown-layer
 * SELECTION of that shared overlay surface.
 */
export { default as DropdownMenu } from './dropdown-menu.svelte';
export type { DropdownMenuItem } from './types.js';
