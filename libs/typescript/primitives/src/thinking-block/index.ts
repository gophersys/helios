/**
 * `@eden/primitives` — the ThinkingBlock public surface. One concept, one home — the appearance is
 * decided in `tokens.ts`, cited here; the disclosure behaviour delegates to the bits-ui Collapsible.
 */
export { default as ThinkingBlock } from './thinking-block.svelte';
export {
  deriveThinkingBlockTokens,
  thinkingBlockStyleVars,
  type ThinkingBlockTokens,
} from './tokens.js';
