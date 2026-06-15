/**
 * `@eden/primitives` — the Input / Textarea public surface.
 *
 * Re-exports the single-line `Input` and multi-line `Textarea` components and their shared
 * token-derivation API. Both components render native text fields (the most accessible base — no
 * generic text-input primitive exists in bits-ui) styled entirely from derived `--eden-input-*`
 * tokens. One concept, one home — the appearance is decided once in `tokens.ts` and the Textarea is
 * an Input that wraps, so they SHARE `deriveInputTokens`.
 */
export { default as Input } from './input.svelte';
export { default as Textarea } from './textarea.svelte';
export { deriveInputTokens, inputStyleVars, type InputTokens } from './tokens.js';
