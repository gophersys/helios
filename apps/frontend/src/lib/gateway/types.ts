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
