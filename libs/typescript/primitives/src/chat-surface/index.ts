/**
 * `@eden/primitives` — the chat-surface vocabulary public surface.
 *
 * The single home (10 §9) for the derived role-pair + proportion primitives every chat component
 * shares. Re-exports the pure helpers the design-correctness gate audits and the chat components
 * cite — the appearance vocabulary is decided in `tokens.ts`, cited here and by each component.
 */
export {
  proseSurface,
  accentSurface,
  quietSurface,
  stateSurface,
  proportion,
  rampPx,
  space,
  hitTargetPx,
  styleVars,
  type SurfacePair,
  type StateRole,
  type ProportionPick,
  type StyleEntry,
} from './tokens.js';
