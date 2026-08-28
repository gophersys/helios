/**
 * `@eden/primitives` — the Message public surface.
 *
 * Re-exports the component and its token-derivation API. The component default export is the Svelte 5
 * `message.svelte`; the named exports are the pure token math (`deriveMessageTokens`,
 * `messageStyleVars`) the design-correctness gate audits, plus the role + token types. One concept,
 * one home — the appearance is decided in `tokens.ts`, cited here.
 */
export { default as Message } from './message.svelte';
export {
  deriveMessageTokens,
  messageStyleVars,
  type MessageRole,
  type MessageTokens,
} from './tokens.js';
