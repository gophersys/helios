/**
 * `@eden/primitives` — the StreamingText public surface.
 *
 * Re-exports the component, its token-derivation API, and the pure token-by-token reveal math
 * (`appendChunk`, `streamProgress`) the host drives. One concept, one home — the appearance and the
 * reveal logic are decided in `tokens.ts`, cited here.
 */
export { default as StreamingText } from './streaming-text.svelte';
export {
  deriveStreamingTextTokens,
  streamingTextStyleVars,
  appendChunk,
  streamProgress,
  type StreamingTextTokens,
} from './tokens.js';
