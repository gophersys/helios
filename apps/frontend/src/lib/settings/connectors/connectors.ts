// The Connectors settings section — the app-local contract mirror + write-only display logic.
//
// Home: the Connectors section of the ONE Settings surface (doc 17 §7; the connectors design §3).
// This module is the PURE, unit-testable spine of the section: the TypeScript mirror of the §2
// `ConnectorView` wire shape, the closed v1 kind enum, and the write-only display helpers that carry
// the security invariant — after a credential is saved it is NEVER echoed, only its fingerprint /
// last-4 + account hint. No field here can carry a secret VALUE (that crosses `connectProvider`
// once, and never rides a view). See the connectors design §2 (the FE↔BE wire shape is binding).
//
// P-D7 promotion candidates (build app-local now, promote to libs/typescript when stable — do NOT
// touch libs/typescript this wave): the WriteOnlyField display logic below is the security spine the
// design flags as most-worth-a-single-audited-home; the ConnectorRow / SecretField molecules that
// consume it are the promotion units. Their pure helpers live here so the promoted molecule imports
// one audited home for the no-echo rule.

/** The closed v1 connector-kind enum (§2.2). Only kinds whose connect path actually works are in the
 *  enum — honest chrome (P-D6): a kind Eden cannot yet consume is not offered. LOCKED v1 set: the
 *  three ESO bootstrap items (claude-api / github / openrouter). */
export const CONNECTOR_KINDS = ['claude-api', 'github', 'openrouter'] as const;
export type ConnectorKind = (typeof CONNECTOR_KINDS)[number];

/** A human-facing descriptor for a connector kind: the picker label, the provider glyph (the
 *  placeholder ProviderMark until the Avatar/Icon atom lands — doc 17 §4 anticipates it), and the
 *  credential-entry hint. Kept beside the enum so "one concept, one home" (10 §9). */
export interface ConnectorKindDescriptor {
  kind: ConnectorKind;
  label: string;
  glyph: string;
  credentialLabel: string;
  credentialHint: string;
}

/** The v1 descriptors, in offer order. The glyph is a plain inline element for now (§3.2 gap: no
 *  provider-mark atom yet). */
export const CONNECTOR_KIND_DESCRIPTORS: readonly ConnectorKindDescriptor[] = [
  {
    kind: 'claude-api',
    label: 'Claude API',
    glyph: '◆',
    credentialLabel: 'API key',
    credentialHint: 'Your Anthropic API key. Stored write-only — never shown again.',
  },
  {
    kind: 'github',
    label: 'GitHub',
    glyph: '⎇',
    credentialLabel: 'Access token',
    credentialHint: 'A GitHub token (classic or fine-grained). Stored write-only.',
  },
  {
    kind: 'openrouter',
    label: 'OpenRouter',
    glyph: '⇄',
    credentialLabel: 'API key',
    credentialHint: 'Your OpenRouter API key. Stored write-only — never shown again.',
  },
];

/** kindLabel resolves a kind to its human label (falls back to the raw kind for a value the client
 *  does not recognize — honest, never a crash). */
export function kindLabel(kind: string): string {
  return CONNECTOR_KIND_DESCRIPTORS.find((d) => d.kind === kind)?.label ?? kind;
}

/** kindGlyph resolves a kind to its provider glyph (a neutral bullet for an unknown kind). */
export function kindGlyph(kind: string): string {
  return CONNECTOR_KIND_DESCRIPTORS.find((d) => d.kind === kind)?.glyph ?? '•';
}

/** isConnectorKind narrows a raw string to the closed enum (used to gate the picker to WORKING kinds
 *  only — P-D6). */
export function isConnectorKind(value: string): value is ConnectorKind {
  return (CONNECTOR_KINDS as readonly string[]).includes(value);
}

// ── the §2 scope shape ─────────────────────────────────────────────────────────.

/** The scope level a connector is bound at (§2.2 `Scope`). `org` is the v1 DEFAULT (LOCKED call:
 *  org-scope default). `user` scopes to the uploading user; `project` to one project. */
export type ScopeLevel = 'org' | 'user' | 'project';

/** Scope is the resolved scope on a `ConnectorView` (§2.2): the level + an optional target id
 *  (user_id NULL ⇒ org-scoped, so `targetId` is absent for the org level). */
export interface Scope {
  level: ScopeLevel;
  targetId?: string;
}

/** ScopeInput is the scope a create/connect request carries (§2.2 `ScopeInput`). Mirrors `Scope`. */
export type ScopeInput = Scope;

// ── the §2 view shape (NEVER carries a value) ────────────────────────────────────.

/** The connector lifecycle state as the wire reports it (§2 `Connector.State`). `not-set` is the
 *  honest "no credential yet" (an offered-but-unconnected row); `healthy` a validated connector;
 *  `degraded`/`down` a connector whose last check failed. Mapped to a Badge status by
 *  {@link stateBadgeVariant}. */
export type ConnectorState = 'healthy' | 'degraded' | 'down' | 'not-set' | 'updating';

/** ConnectorView is the EXACT §2 wire projection of a stored connector — the binding FE↔BE shape.
 *  It NEVER carries the credential value: the plaintext crosses `connectProvider` once and is
 *  answered with this shape (fingerprint + account hint only, never the value). One concept, one
 *  home — this mirrors platformgateway's `view.Connector` (Brief A emits it via clients/go). */
export interface ConnectorView {
  id: string;
  kind: string;
  name: string;
  scope: Scope;
  state: ConnectorState;
  accountHint: string;
  fingerprint: string;
}

/** The body of GET /connectors (unwrapped from the data envelope): the caller-org connectors. */
export interface ListConnectorsResponse {
  connectors: ConnectorView[];
}

// ── the write-only display spine (the no-echo invariant) ─────────────────────────.

/** stateBadgeVariant maps a connector state to a Badge status variant (§3.2: real-status pill, never
 *  a decorative one — the WORD survives grayscale). `not-set` renders neutral (offered, uncredentialed);
 *  `updating` maps to the theme's updating hue while a validate is in flight. */
export function stateBadgeVariant(
  state: ConnectorState,
): 'healthy' | 'degraded' | 'down' | 'updating' | 'neutral' {
  switch (state) {
    case 'healthy':
      return 'healthy';
    case 'degraded':
      return 'degraded';
    case 'down':
      return 'down';
    case 'updating':
      return 'updating';
    case 'not-set':
    default:
      return 'neutral';
  }
}

/** stateLabel is the human WORD a state renders as (the Badge text — colour is never the only
 *  channel, doc 17 §1). */
export function stateLabel(state: ConnectorState): string {
  switch (state) {
    case 'healthy':
      return 'healthy';
    case 'degraded':
      return 'degraded';
    case 'down':
      return 'down';
    case 'updating':
      return 'validating';
    case 'not-set':
    default:
      return 'not set';
  }
}

/** scopeChipText renders a scope as the mono chip datum (§3.3: `scope:[org:acme]` style). It shows the
 *  level and, for a targeted scope, the short target id — the same honest-chrome mono voice the
 *  Clusters chip uses. An org scope shows just the level (no target: user_id NULL ⇒ org-wide). */
export function scopeChipText(scope: Scope): string {
  if (scope.level === 'org' || !scope.targetId) return scope.level;
  return `${scope.level}:${shortId(scope.targetId)}`;
}

/** shortId truncates an id/uuid to a scannable head (mono data voice), never the full opaque value. */
export function shortId(id: string): string {
  return id.length <= 8 ? id : id.slice(0, 8);
}

/** A connector is CONNECTED when it holds a stored credential — i.e. it has a fingerprint and is not
 *  in the `not-set` state. This gates the write-only display: a connected connector shows ONLY the
 *  fingerprint/last-4 (never a value + never a reveal affordance — there is no reveal, by design),
 *  and offers Manage/Disconnect; an unconnected one offers Connect. */
export function isConnected(view: Pick<ConnectorView, 'state' | 'fingerprint'>): boolean {
  return view.state !== 'not-set' && view.fingerprint.trim().length > 0;
}

/** fingerprintDisplay is THE no-echo helper — the ONLY thing a connected credential renders. It shows
 *  the server-provided fingerprint (a one-way truncated SHA-256 last-4 / short hex, §1.1) verbatim,
 *  prefixed for the mono chip. It NEVER receives, holds, or derives from the plaintext value — the
 *  value does not exist client-side after the connect POST resolves. An empty fingerprint (a wire
 *  that somehow omitted it) degrades to a neutral placeholder, never a blank that reads as "no
 *  secret". */
export function fingerprintDisplay(fingerprint: string): string {
  const trimmed = fingerprint.trim();
  return trimmed.length > 0 ? `••••${trimmed}` : '••••';
}
