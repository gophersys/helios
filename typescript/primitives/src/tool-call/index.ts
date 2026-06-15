/**
 * `@eden/primitives` — the ToolCall public surface. One concept, one home — the appearance is decided
 * in `tokens.ts`, cited here.
 */
export { default as ToolCall } from './tool-call.svelte';
export {
  deriveToolCallTokens,
  toolCallStyleVars,
  type ToolCallStatus,
  type ToolCallTokens,
} from './tokens.js';
