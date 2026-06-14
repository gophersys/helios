// TypeScript mirror of the agentgateway wire contract — the REST DTOs and the per-kind SSE
// event projection the gateway emits (apps/agentgateway/internal/gateway/wire.go). One
// concept, one home: these shapes are a faithful, read-only projection of the Go DTOs, so the
// chat surface branches on the SAME stable lower-kebab vocabulary the gateway stamps onto each
// SSE frame's `event:` field and onto every event `kind`. No field here can carry a credential
// — the gateway projection is redaction-safe by construction (REQ-0021).

/** The normalized event taxonomy token (the SSE `event:` field + `eventView.kind`). Closed,
 *  additive-only — mirrors agentsession.EventKind.String() (libs/go/agentsession/types.go). */
export type EventKind =
  | 'session-state'
  | 'message-start'
  | 'thinking-delta'
  | 'text-delta'
  | 'message-end'
  | 'tool-start'
  | 'tool-update'
  | 'tool-end'
  | 'permission-request'
  | 'permission-resolved'
  | 'usage'
  | 'result'
  | 'failed'
  | 'aborted'
  | 'extension';

/** The session lifecycle state token (mirrors agentsession.State.String()). */
export type SessionState =
  | 'initializing'
  | 'ready'
  | 'running'
  | 'awaiting-input'
  | 'awaiting-permission'
  | 'completed'
  | 'failed'
  | 'aborted';

/** The three terminal event kinds end the stream (exactly one per session). */
export const TERMINAL_KINDS: ReadonlySet<EventKind> = new Set<EventKind>([
  'result',
  'failed',
  'aborted',
]);

/** A session-state transition (chat connection/idle/working chrome). */
export interface StateView {
  from: string;
  to: string;
}

/** A streamed assistant message / thinking fragment (Delta is incremental, not cumulative). */
export interface MessageView {
  role?: string;
  delta?: string;
}

/** A tool start / update / end — name, args summary, grant linkage, redacted result digest. */
export interface ToolView {
  callId?: string;
  name?: string;
  grantId?: string;
  argsSummary?: string;
  partialDigest?: string;
  outcome?: string;
  resultDigest?: string;
  durationMs?: number;
  isHostTool?: boolean;
}

/** A permission request / resolved record (the human/policy gate). */
export interface PermissionView {
  requestId: string;
  tool?: string;
  reason?: string;
  decision?: string;
  by?: string;
}

/** A token/cost tick — all four token kinds + per-model attribution. Cost is integer micros. */
export interface UsageView {
  model?: string;
  harness?: string;
  inputTokens: number;
  outputTokens: number;
  cacheReadTokens: number;
  cacheCreationTokens: number;
  costMicros: number;
  cumulative?: boolean;
}

/** The authoritative terminal TokenLedger (the final meter the UI reconciles against). */
export interface LedgerView extends UsageView {
  turns: number;
  toolUses: number;
  wallTimeMs: number;
  toolUsesByName?: Record<string, number>;
}

/** A terminal event projection (result / failed / aborted) + its authoritative ledger. */
export interface TerminalView {
  outcome: string;
  resultText?: string;
  stopReason?: string;
  reason?: string;
  detail?: string;
  by?: string;
  ledger: LedgerView;
}

/** The `data:` payload of one SSE frame — exactly the sub-payload for the kind is populated. */
export interface EventView {
  sessionId: string;
  seq: number;
  kind: EventKind;
  turn?: number;
  turnId?: string;
  time: string;
  state?: StateView;
  message?: MessageView;
  tool?: ToolView;
  permission?: PermissionView;
  usage?: UsageView;
  terminal?: TerminalView;
  extension?: string;
}

/** The session-list / get-one record projection (orchestrator.Agent). */
export interface AgentView {
  id: string;
  organizationId: string;
  projectId: string;
  template: string;
  runId?: string;
  status: string;
  desired: string;
  by?: string;
  detail?: string;
  createdAt: string;
  updatedAt: string;
  ledger: LedgerView;
}

/** GET /sessions — a page of agents + the opaque next cursor. */
export interface ListResponse {
  sessions: AgentView[];
  next?: string;
}

/** POST /sessions — the assigned AgentID + initial status. */
export interface CreateResponse {
  id: string;
  status: string;
}

/** POST /sessions/{id}/control — the Seq the verb was admitted at (the Ack). */
export interface ControlResponse {
  admittedSeq: number;
}

/** GET /sessions/{id}/transcript — the persisted Run's full ordered event list. */
export interface TranscriptResponse {
  id: string;
  events: EventView[];
  headSeq: number;
  complete: boolean;
}

/** The redaction-safe error envelope: a stable Kind token + an operator-safe message. */
export interface ErrorBody {
  kind: string;
  message: string;
}

/** The harness a session is created against. The dev-serve routes every session to its fake
 *  harness, so this is recorded as a label (and surfaced in the UI) — the gateway picks the
 *  live harness from its routing table, not from the create body. */
export type Harness = 'claude' | 'omp';

// ── the product-config contract (the create-flow wizard) ──────────────────────.
//
// A "session" IS a PRODUCT Eden builds via its 10-phase SDLC. The create flow is a wizard that,
// FROM the initial prompt, AI-PROPOSES a ProductConfig (POST /product/propose) the user then
// edits, before it rides POST /sessions as the optional `product` field. These shapes are a
// faithful TypeScript mirror of the Go DTOs in apps/agentgateway/internal/gateway/product.go —
// one concept, one home. No field carries a credential (the setup-token rides the gateway's
// opaque secrets.Reference, never this DTO).

/** The product artifact kind (mirrors gateway.ProductKind*). An unrecognized kind normalizes to
 *  `service` (the Eden default build target) server-side. */
export type ProductKind = 'service' | 'library' | 'application' | 'cli' | 'ui' | 'other';

/** The closed ProductKind set, in wizard display order. */
export const PRODUCT_KINDS: readonly ProductKind[] = [
  'service',
  'library',
  'application',
  'cli',
  'ui',
  'other',
];

/** The harness the build agent runs on (mirrors gateway.Harness*). Wider than the chat-label
 *  `Harness` type: the product capability accepts `codex` too. */
export type ProductHarness = 'claude' | 'omp' | 'codex';

/** The closed product-harness set, in wizard display order. */
export const PRODUCT_HARNESSES: readonly ProductHarness[] = ['claude', 'omp', 'codex'];

/** The sandbox egress posture (mirrors gateway.Posture*). Strict == default-deny, the safe
 *  posture for an unattended build agent. */
export type SandboxPosture = 'strict' | 'relaxed';

/** The language/framework selection of a ProductConfig (Eden defaults: Go 1.26 backend, Svelte 5
 *  UI). */
export interface ProductStack {
  languages: string[];
  frameworks: string[];
}

/** The agent capability binding of a ProductConfig: the harness+model the build runs on, the
 *  standing tool grants, and the injected skills/rules. No field is a secret. */
export interface ProductCapabilities {
  harness: ProductHarness;
  model: string;
  toolGrants: string[];
  skills: string[];
  rules: string[];
}

/** The egress posture of a ProductConfig build agent. */
export interface ProductSandbox {
  posture: SandboxPosture;
  egressAllow: string[];
}

/** ProductConfig is the product specification the create-flow wizard edits: what Eden will
 *  build, with which stack/services/capabilities, and which SDLC phases to run. It is the exact
 *  JSON the gateway exchanges (gateway.ProductConfig). */
export interface ProductConfig {
  productName: string;
  productKind: ProductKind;
  summary: string;
  stack: ProductStack;
  services: string[];
  capabilities: ProductCapabilities;
  sdlcPhases: string[];
  sandbox: ProductSandbox;
}

/** The full 10-phase SDLC pipeline the wizard's PROCESS step multi-selects from. The default
 *  proposal runs the four-phase library core (architecture..qa — gateway.DefaultSDLCPhases). */
export const SDLC_PHASES: readonly string[] = [
  'architecture',
  'implementation',
  'testing',
  'qa',
  'integration',
  'security',
  'performance',
  'documentation',
  'release',
  'operations',
];

/** The uniform Eden response envelope ({data, errors, kind}) the product-config surface returns
 *  (edenhttp.Envelope). The chat REST routes return bare JSON; only POST /product/propose is
 *  enveloped, so the propose client unwraps `.data`. */
export interface Envelope<T> {
  data: T;
  errors: string[];
  kind: string;
}
