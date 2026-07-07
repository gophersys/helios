/**
 * `@eden/primitives` — the Wave-1 surface token vocabulary public surface.
 *
 * The single home (10 §9) the Wave-1 atoms/molecules cite for the derived primitives doc 17 §3/§4
 * names but doc-10's chat-surface did not already own: the three radii (control/surface/sheet), the
 * two elevations (raised/overlay), and the status/health role selection (the Clusters vocabulary).
 * Every Wave-1 component `tokens.ts` imports from here (and from chat-surface) rather than
 * re-spelling a ramp lookup, a shadow recipe, or a status→role mapping.
 */
export {
  radiusPx,
  elevationShadow,
  statusRole,
  statusRoleOklch,
  statusTint,
  type Radius,
  type Elevation,
  type Status,
} from './tokens.js';
