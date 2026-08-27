/**
 * `@eden/primitives` — the Field public surface.
 *
 * Re-exports the form `Field` (label + control + error, correctly wired for accessibility) and its
 * token-derivation API. The Field is the a11y composition layer: it owns the `<label for>` +
 * aria-describedby + aria-invalid relationship and the label/error text contrast; the control is
 * supplied as a snippet so the same Field wraps an Input, a Textarea, or any control honoring the
 * `{ id, describedby, invalid }` wiring contract. One concept, one home — the appearance is decided
 * once in `tokens.ts`, cited here.
 */
export { default as Field } from './field.svelte';
export { deriveFieldTokens, fieldStyleVars, type FieldTokens } from './tokens.js';
