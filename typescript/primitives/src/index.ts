/**
 * `@eden/primitives` — the Eden component primitives barrel (ADR-0024, RD-16/OD-1).
 *
 * Accessible Svelte 5 components GENERATED FROM THE MATH: every color/size/space is DERIVED from an
 * `@eden/theme` token (never hand-set), the behavior is the bits-ui primitive layer, and each
 * component carries a mechanical design-correctness proof (the contrast gate + the 44px hit-target
 * floor + scale provenance, in `*.design.test.ts`) and a version-pinned a11y-evidence record (axe
 * on Chromium+WebKit + keyboard, in `a11y-evidence/`). MATH IS SOURCE OF TRUTH.
 *
 * This barrel is a pure re-export (no logic; excluded from the coverage floor — see vitest.config).
 */

// ── Button — the reference component proving the pipeline end-to-end ──────────────────────────
export {
  Button,
  deriveButtonTokens,
  buttonStyleVars,
  defaultButtonTheme,
  type ButtonVariant,
  type ButtonTokens,
  type ThemeSeed,
} from './button/index.js';

// ── IconButton — a square, icon-only Button (cites the Button's variant→role selection) ───────
export {
  IconButton,
  deriveIconButtonTokens,
  iconButtonStyleVars,
  type IconButtonTokens,
} from './icon-button/index.js';

// ── Input / Textarea — token-driven native text fields (shared derivation; one home) ──────────
export {
  Input,
  Textarea,
  deriveInputTokens,
  inputStyleVars,
  type InputTokens,
} from './input/index.js';

// ── Field — the label + control + error group, correctly wired for accessibility ──────────────
export { Field, deriveFieldTokens, fieldStyleVars, type FieldTokens } from './field/index.js';

// ── Overlay group (RD-16/OD-1 — bits-ui Portal + Eden tokens through the portal) ──────────────
// Dialog (incl. nested/LIFO), Popover, Tooltip, DropdownMenu — every one a SELECTION of the shared
// overlay surface token math (one concept, one home: ./overlay/tokens.ts). Each derives its
// color/size/space from @eden/theme, carries no hardcoded literal, and is proven by a design-
// correctness test (portaled computed colors == resolved tokens, contrast gate) + an a11y-evidence
// record (axe ZERO serious/critical at every depth on Chromium+WebKit, keyboard focus-trap/LIFO).
export { Dialog } from './dialog/index.js';
export { Popover } from './popover/index.js';
export { Tooltip } from './tooltip/index.js';
export { DropdownMenu, type DropdownMenuItem } from './dropdown-menu/index.js';

// The shared overlay token math (the ONE home every overlay component cites — 10 §9).
export {
  deriveOverlayTokens,
  overlayStyleVars,
  defaultOverlayTheme,
  type OverlayLayer,
  type OverlayTokens,
} from './overlay/index.js';

// ── CommandPalette — the OD-1 ⌘K (Dialog.Portal wrapping Command.Root; fuzzy + grouped + a11y) ──
// The command group: a fuzzy-scored, grouped, virtualizing command menu composed as Dialog.Portal
// wrapping bits-ui Command.Root (the OD-1-proven ⌘K). Its appearance is DERIVED from @eden/theme
// (command-palette/tokens.ts: input/item/selected/heading role pairs + the decoupled 44px floor),
// carries no hardcoded literal, and is proven by a design-correctness test (contrast gate on every
// painted pair + scale provenance + 44px floor) and an a11y-evidence record (axe ZERO
// serious/critical on Chromium+WebKit, keyboard Arrow/Enter/Escape + aria-activedescendant).
export {
  CommandPalette,
  deriveCommandPaletteTokens,
  commandPaletteStyleVars,
  defaultCommandPaletteTheme,
  commandContrast,
  type CommandPaletteItem,
  type CommandPaletteGroup,
  type CommandPaletteTokens,
} from './command-palette/index.js';

// ── chat-surface — the SHARED token vocabulary every chat component is built from (one home) ───
// The single place the chat group's derived role-pair + proportion primitives live (10 §9): a
// gated {fg,bg,border} container, a type-scale proportion pick, a spacing-ramp step, the 44px hit
// floor. Every chat component below CITES these helpers and re-spells no role selection or px.
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
} from './chat-surface/index.js';

// ── CHAT SURFACES — the agent-event taxonomy as token-driven components (the demo face) ────────
// Message (user/assistant bubbles), StreamingText (token-by-token), and the agent-event cards:
// ToolCall, PermissionRequest (the 5b human prompt), UsageMeter, ThinkingBlock. Each derives its
// color/size/space from @eden/theme via chat-surface, carries no hardcoded literal, and is proven
// by a design-correctness test (contrast gate on every text/bg pair incl. code blocks + scale
// provenance + the 44px floor) and an a11y-evidence record (axe Chromium+WebKit + keyboard).
export {
  Message,
  deriveMessageTokens,
  messageStyleVars,
  type MessageRole,
  type MessageTokens,
} from './message/index.js';

export {
  StreamingText,
  deriveStreamingTextTokens,
  streamingTextStyleVars,
  appendChunk,
  streamProgress,
  type StreamingTextTokens,
} from './streaming-text/index.js';

export {
  ToolCall,
  deriveToolCallTokens,
  toolCallStyleVars,
  type ToolCallStatus,
  type ToolCallTokens,
} from './tool-call/index.js';

export {
  PermissionRequest,
  derivePermissionRequestTokens,
  permissionRequestStyleVars,
  permissionHeadingPairOklch,
  type PermissionRequestTokens,
} from './permission-request/index.js';

export {
  UsageMeter,
  deriveUsageMeterTokens,
  usageMeterStyleVars,
  usageFraction,
  usageTier,
  barWidthPercent,
  type UsageTier,
  type UsageMeterTokens,
} from './usage-meter/index.js';

export {
  ThinkingBlock,
  deriveThinkingBlockTokens,
  thinkingBlockStyleVars,
  type ThinkingBlockTokens,
} from './thinking-block/index.js';
