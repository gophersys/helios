// The chat session store — a Svelte 5 runes ($state/$derived) reducer that folds the live event
// stream into renderable chat state. It is the single normalization point between the gateway's
// per-kind SSE events and the chat view: text-delta fragments accrete into an assistant message;
// thinking-delta fragments accrete into a foldable reasoning block; tool start/update/end
// correlate by callId into a tool-call timeline; usage ticks update a live token/cost meter; the
// terminal event freezes the authoritative ledger. The store owns the SSE subscription lifecycle
// (connect on open, reconnect via Last-Event-ID, close on teardown) so the view stays declarative.

import { GatewayClient, GatewayError } from './client';
import { subscribeEvents, type Subscription, type SseStatus } from './sse';
import type {
  Activity,
  EventView,
  Harness,
  LedgerView,
  PermissionScope,
  PermissionVerdict,
  SessionState,
  UsageView,
} from './types';

/** A single rendered turn-entry in the conversation timeline. The tagged `role` drives which
 *  chat component renders it; the fields are accreted from the streamed events. */
export type Entry =
  | { id: string; role: 'user'; text: string }
  | {
      id: string;
      role: 'assistant';
      text: string;
      thinking: string;
      streaming: boolean;
    }
  | { id: string; role: 'tool'; tool: ToolEntry }
  | { id: string; role: 'permission'; permission: PermissionEntry }
  | { id: string; role: 'notice'; tone: 'info' | 'warn'; text: string }
  | { id: string; role: 'terminal'; outcome: string; text: string; reason?: string };

/** A tool-call entry correlated across tool-start / tool-update / tool-end by callId. */
export interface ToolEntry {
  callId: string;
  name: string;
  grantId?: string;
  argsSummary?: string;
  isHostTool: boolean;
  status: 'running' | 'ok' | 'error' | 'denied';
  partialDigest?: string;
  resultDigest?: string;
  durationMs?: number;
}

/** A permission round-trip entry correlated across request / resolved by requestId. `decision` is
 *  the gateway's resolution token (`pending` until resolved, then `allowed`/`denied`); `resolving`
 *  is the optimistic in-flight flag set the instant the human clicks (so the card disables its
 *  actions before the `permission-resolved` event lands); `rationale` is the advisor's audit
 *  reasoning when the policy (not the human) decided. */
export interface PermissionEntry {
  requestId: string;
  tool?: string;
  reason?: string;
  decision: string;
  by?: string;
  rationale?: string;
  resolving: boolean;
}

/** The live token/cost meter the usage ticks update and the terminal ledger reconciles. */
export interface Meter {
  model: string;
  harness: string;
  inputTokens: number;
  outputTokens: number;
  cacheReadTokens: number;
  cacheCreationTokens: number;
  costMicros: number;
  turns: number;
  toolUses: number;
}

const EMPTY_METER: Meter = {
  model: '',
  harness: '',
  inputTokens: 0,
  outputTokens: 0,
  cacheReadTokens: 0,
  cacheCreationTokens: 0,
  costMicros: 0,
  turns: 0,
  toolUses: 0,
};

/** ChatSession owns the live state for ONE open session: the entry timeline, the meter, the
 *  lifecycle state, and the SSE subscription. Construct it with the gateway client + the agent
 *  id, then call open(); call close() on teardown (idempotent, leak-free). */
export class ChatSession {
  readonly id: string;
  readonly harness: Harness;
  private readonly client: GatewayClient;

  // Reactive surface ($state). The view reads these directly.
  entries = $state<Entry[]>([]);
  meter = $state<Meter>({ ...EMPTY_METER });
  sessionState = $state<SessionState>('initializing');
  connection = $state<SseStatus>('connecting');
  terminal = $state<boolean>(false);
  error = $state<string | null>(null);

  // ── status-bar surface (the JS representation of the harness TUI) ──
  /** The live agent activity the bottom status bar renders (thinking/responding/tool/…). */
  activity = $state<Activity>('idle');
  /** The running ESTIMATED reasoning-token count of the current/last turn (thinking-progress
   *  heartbeats). Reset when a new turn begins; retained after terminal so the bar can show the
   *  "thought for N tokens" summary. NOT a billed figure — that is the usage meter. */
  thinkingTokens = $state<number>(0);
  /** Epoch ms when the current turn began (its first activity); null when idle/terminal. The
   *  status bar ticks an elapsed clock from it. */
  turnStartedAt = $state<number | null>(null);
  /** The name of the currently running tool (for the "Running <tool>…" status), else null. */
  activeTool = $state<string | null>(null);

  private subscription: Subscription | null = null;
  // The callIds of tools currently running (start without end), so the activity reflects tool work.
  private runningTools = new Set<string>();
  // The streaming assistant entry being accreted (by turnId), so deltas land on one bubble.
  private liveAssistantIndex = new Map<string, number>();
  // The tool entries by callId, so update/end land on the same timeline entry.
  private toolIndex = new Map<string, number>();
  // The permission entries by requestId.
  private permissionIndex = new Map<string, number>();
  private counter = 0;

  constructor(client: GatewayClient, id: string, harness: Harness) {
    this.client = client;
    this.id = id;
    this.harness = harness;
  }

  /** open subscribes to the live SSE stream and folds events into state until terminal/close. */
  open(): void {
    this.subscription = subscribeEvents(
      this.client.url(`/sessions/${encodeURIComponent(this.id)}/events`),
      {
        fromSeq: 0,
        onEvent: (event) => this.fold(event),
        onStatus: (status) => {
          this.connection = status;
        },
      },
    );
  }

  /** close tears down the SSE subscription (idempotent, leak-free). */
  close(): void {
    this.subscription?.close();
    this.subscription = null;
  }

  /** send issues a prompt turn. It records the user bubble optimistically and surfaces a typed
   *  gateway fault (e.g. a 409 once the single-turn fake script is terminal) as a notice. */
  async send(text: string): Promise<void> {
    this.pushUser(text);
    try {
      await this.client.prompt(this.id, text);
      this.error = null;
    } catch (cause) {
      this.surface(cause, 'prompt');
    }
  }

  /** steer interjects into a running turn (CapSteer). */
  async steer(text: string): Promise<void> {
    try {
      await this.client.steer(this.id, text);
      this.pushNotice('info', `steer admitted: ${text}`);
      this.error = null;
    } catch (cause) {
      this.surface(cause, 'steer');
    }
  }

  /** abort cancels the in-flight turn. */
  async abort(): Promise<void> {
    try {
      await this.client.abort(this.id);
      this.pushNotice('info', 'abort admitted');
      this.error = null;
    } catch (cause) {
      this.surface(cause, 'abort');
    }
  }

  // ── the event reducer ──────────────────────────────────────────────────────.

  private fold(event: EventView): void {
    switch (event.kind) {
      case 'session-state':
        if (event.state) this.sessionState = event.state.to as SessionState;
        break;
      case 'thinking-progress':
        // The pre-message reasoning heartbeat: surface the running estimated token count and drive
        // the live "thinking…" status — the signal that turns the dead "Waiting for events…" screen
        // into a Claude-Code-style status bar during a long think.
        this.beginTurn();
        if (event.message?.tokens) this.thinkingTokens = event.message.tokens;
        this.activity = 'thinking';
        break;
      case 'message-start':
        this.beginTurn();
        this.ensureAssistant(this.turnKey(event));
        break;
      case 'thinking-delta':
        this.beginTurn();
        this.activity = 'thinking';
        if (event.message?.delta) this.appendThinking(this.turnKey(event), event.message.delta);
        break;
      case 'text-delta':
        this.beginTurn();
        this.activity = 'responding';
        if (event.message?.delta) this.appendText(this.turnKey(event), event.message.delta);
        break;
      case 'message-end':
        this.finishAssistant(this.turnKey(event));
        break;
      case 'tool-start':
        this.beginTurn();
        this.toolStart(event);
        break;
      case 'tool-update':
        this.toolUpdate(event);
        break;
      case 'tool-end':
        this.toolEnd(event);
        break;
      case 'permission-request':
        this.permission(event);
        break;
      case 'permission-resolved':
        this.permission(event);
        break;
      case 'usage':
        if (event.usage) this.applyUsage(event.usage);
        break;
      case 'result':
      case 'failed':
      case 'aborted':
        this.applyTerminal(event);
        break;
      case 'extension':
        // Preserved verbatim by the gateway; the chat surface ignores what it does not model.
        break;
    }
  }

  private turnKey(event: EventView): string {
    return event.turnId || `turn-${event.turn ?? 0}`;
  }

  /** beginTurn marks the start of a turn on the FIRST activity of that turn (thinking-progress,
   *  message-start, a delta, or a tool) — including the wizard's server-side opening prompt, which
   *  never goes through pushUser. It stamps the elapsed clock and resets the per-turn thinking
   *  counter, so the status bar reflects THIS turn. Idempotent within a turn. */
  private beginTurn(): void {
    if (this.turnStartedAt === null) {
      this.turnStartedAt = Date.now();
      this.thinkingTokens = 0;
    }
  }

  /** endTurn freezes the status bar on a terminal outcome: it stops the elapsed clock and clears
   *  any running-tool state, but RETAINS thinkingTokens so the bar can show the turn's summary. */
  private endTurn(activity: Activity): void {
    this.activity = activity;
    this.turnStartedAt = null;
    this.runningTools.clear();
    this.activeTool = null;
  }

  private ensureAssistant(turnKey: string): number {
    const existing = this.liveAssistantIndex.get(turnKey);
    if (existing != null) return existing;
    const id = this.nextId('a');
    this.entries = [
      ...this.entries,
      { id, role: 'assistant', text: '', thinking: '', streaming: true },
    ];
    const index = this.entries.length - 1;
    this.liveAssistantIndex.set(turnKey, index);
    return index;
  }

  private appendText(turnKey: string, delta: string): void {
    const index = this.ensureAssistant(turnKey);
    const entry = this.entries[index];
    if (entry.role !== 'assistant') return;
    this.entries[index] = { ...entry, text: entry.text + delta };
    this.entries = [...this.entries];
  }

  private appendThinking(turnKey: string, delta: string): void {
    const index = this.ensureAssistant(turnKey);
    const entry = this.entries[index];
    if (entry.role !== 'assistant') return;
    this.entries[index] = { ...entry, thinking: entry.thinking + delta };
    this.entries = [...this.entries];
  }

  private finishAssistant(turnKey: string): void {
    const index = this.liveAssistantIndex.get(turnKey);
    if (index == null) return;
    const entry = this.entries[index];
    if (entry.role !== 'assistant') return;
    this.entries[index] = { ...entry, streaming: false };
    this.entries = [...this.entries];
    this.liveAssistantIndex.delete(turnKey);
  }

  private toolStart(event: EventView): void {
    const tool = event.tool;
    if (!tool?.callId) return;
    const entry: ToolEntry = {
      callId: tool.callId,
      name: tool.name ?? 'tool',
      grantId: tool.grantId,
      argsSummary: tool.argsSummary,
      isHostTool: tool.isHostTool ?? false,
      status: 'running',
    };
    const id = this.nextId('t');
    this.entries = [...this.entries, { id, role: 'tool', tool: entry }];
    this.toolIndex.set(tool.callId, this.entries.length - 1);
    this.runningTools.add(tool.callId);
    this.activeTool = entry.name;
    this.activity = 'tool';
  }

  private toolUpdate(event: EventView): void {
    const tool = event.tool;
    if (!tool?.callId) return;
    const index = this.toolIndex.get(tool.callId);
    if (index == null) return;
    const entry = this.entries[index];
    if (entry.role !== 'tool') return;
    this.entries[index] = { ...entry, tool: { ...entry.tool, partialDigest: tool.partialDigest } };
    this.entries = [...this.entries];
  }

  private toolEnd(event: EventView): void {
    const tool = event.tool;
    if (!tool?.callId) return;
    const index = this.toolIndex.get(tool.callId);
    if (index == null) return;
    const entry = this.entries[index];
    if (entry.role !== 'tool') return;
    const status = this.toolStatus(tool.outcome);
    this.entries[index] = {
      ...entry,
      tool: {
        ...entry.tool,
        status,
        resultDigest: tool.resultDigest ?? entry.tool.resultDigest,
        durationMs: tool.durationMs,
      },
    };
    this.entries = [...this.entries];
    // The tool finished: if it was the last running tool and the turn is still live, the agent
    // resumes responding (more text/thinking usually follows until the terminal event).
    this.runningTools.delete(tool.callId);
    if (this.runningTools.size === 0) {
      this.activeTool = null;
      if (!this.terminal) this.activity = 'responding';
    }
  }

  private toolStatus(outcome?: string): ToolEntry['status'] {
    if (outcome === 'error') return 'error';
    if (outcome === 'denied') return 'denied';
    return 'ok';
  }

  private permission(event: EventView): void {
    const permission = event.permission;
    if (!permission?.requestId) return;
    const resolved = event.kind === 'permission-resolved';
    const index = this.permissionIndex.get(permission.requestId);
    if (index != null) {
      const entry = this.entries[index];
      if (entry.role === 'permission') {
        // Merge the resolved record onto the live request: the decision token lands, the optimistic
        // `resolving` flag clears, and any advisor rationale is surfaced. Only overwrite the request
        // fields (tool/reason) when the incoming event actually carries them.
        this.entries[index] = {
          ...entry,
          permission: {
            ...entry.permission,
            tool: permission.tool ?? entry.permission.tool,
            reason: permission.reason ?? entry.permission.reason,
            decision: permission.decision ?? entry.permission.decision,
            by: permission.by ?? entry.permission.by,
            rationale: permission.rationale ?? entry.permission.rationale,
            resolving: resolved ? false : entry.permission.resolving,
          },
        };
        this.entries = [...this.entries];
        return;
      }
    }
    const next: PermissionEntry = {
      requestId: permission.requestId,
      tool: permission.tool,
      reason: permission.reason,
      decision: permission.decision ?? 'pending',
      by: permission.by,
      rationale: permission.rationale,
      resolving: false,
    };
    const id = this.nextId('p');
    this.entries = [...this.entries, { id, role: 'permission', permission: next }];
    this.permissionIndex.set(permission.requestId, this.entries.length - 1);
  }

  /** resolve answers a pending out-of-grant permission request (ADR-0025). It marks the card
   *  `resolving` optimistically (so its actions disable the instant the human clicks), POSTs the
   *  verdict to the gateway's Resolve endpoint (NOT a prompt/steer/abort control verb), and lets the
   *  resulting `permission-resolved` SSE event flip the decision token + clear `resolving`. A typed
   *  gateway fault (404 already-resolved/unknown, 403 policy-refused, 400 invalid) is surfaced as a
   *  notice and the optimistic flag is rolled back so the human can retry. */
  async resolve(
    requestId: string,
    verdict: PermissionVerdict,
    scope: PermissionScope,
  ): Promise<void> {
    this.markResolving(requestId, true);
    try {
      await this.client.resolve(this.id, requestId, verdict, scope);
      this.error = null;
    } catch (cause) {
      this.markResolving(requestId, false);
      this.surface(cause, 'resolve');
    }
  }

  /** markResolving toggles the optimistic in-flight flag on a permission entry by requestId. */
  private markResolving(requestId: string, resolving: boolean): void {
    const index = this.permissionIndex.get(requestId);
    if (index == null) return;
    const entry = this.entries[index];
    if (entry.role !== 'permission') return;
    this.entries[index] = { ...entry, permission: { ...entry.permission, resolving } };
    this.entries = [...this.entries];
  }

  private applyUsage(usage: UsageView): void {
    // Usage ticks are cumulative (the running prefix of the terminal ledger); take them as the
    // authoritative running total when `cumulative`, otherwise add the delta.
    if (usage.cumulative) {
      this.meter = {
        ...this.meter,
        model: usage.model || this.meter.model,
        harness: usage.harness || this.meter.harness,
        inputTokens: usage.inputTokens,
        outputTokens: usage.outputTokens,
        cacheReadTokens: usage.cacheReadTokens,
        cacheCreationTokens: usage.cacheCreationTokens,
        costMicros: usage.costMicros,
      };
    } else {
      this.meter = {
        ...this.meter,
        model: usage.model || this.meter.model,
        harness: usage.harness || this.meter.harness,
        inputTokens: this.meter.inputTokens + usage.inputTokens,
        outputTokens: this.meter.outputTokens + usage.outputTokens,
        cacheReadTokens: this.meter.cacheReadTokens + usage.cacheReadTokens,
        cacheCreationTokens: this.meter.cacheCreationTokens + usage.cacheCreationTokens,
        costMicros: this.meter.costMicros + usage.costMicros,
      };
    }
  }

  private applyTerminal(event: EventView): void {
    this.terminal = true;
    // Freeze the status bar on the matching terminal verb (done/failed/stopped); the elapsed clock
    // stops but the turn's thinking-token summary is retained.
    this.endTurn(
      event.kind === 'result' ? 'done' : event.kind === 'aborted' ? 'stopped' : 'failed',
    );
    const terminal = event.terminal;
    if (terminal) {
      this.reconcileLedger(terminal.ledger);
      this.entries = [
        ...this.entries,
        {
          id: this.nextId('term'),
          role: 'terminal',
          outcome: terminal.outcome,
          text: terminal.resultText || terminal.detail || '',
          reason: terminal.reason || undefined,
        },
      ];
    }
  }

  private reconcileLedger(ledger: LedgerView): void {
    this.meter = {
      model: ledger.model || this.meter.model,
      harness: ledger.harness || this.meter.harness,
      inputTokens: ledger.inputTokens,
      outputTokens: ledger.outputTokens,
      cacheReadTokens: ledger.cacheReadTokens,
      cacheCreationTokens: ledger.cacheCreationTokens,
      costMicros: ledger.costMicros,
      turns: ledger.turns,
      toolUses: ledger.toolUses,
    };
  }

  private pushUser(text: string): void {
    this.entries = [...this.entries, { id: this.nextId('u'), role: 'user', text }];
    // A new turn begins: clear any terminal freeze and start the status bar on "thinking" (the
    // agent will reason before it answers) with a fresh elapsed clock.
    this.terminal = false;
    this.turnStartedAt = null;
    this.beginTurn();
    this.activity = 'thinking';
  }

  private pushNotice(tone: 'info' | 'warn', text: string): void {
    this.entries = [...this.entries, { id: this.nextId('n'), role: 'notice', tone, text }];
  }

  private surface(cause: unknown, verb: string): void {
    const message =
      cause instanceof GatewayError
        ? `${verb} ${cause.kind}: ${cause.message}`
        : `${verb} failed: ${String(cause)}`;
    this.error = message;
    this.pushNotice('warn', message);
  }

  private nextId(prefix: string): string {
    this.counter += 1;
    return `${prefix}-${this.counter}`;
  }
}

/** A formatted dollar string from integer cost micros (1e6 micros == $1; no float drift on
 *  display because the source is integer micros). */
export function formatCost(costMicros: number): string {
  return `$${(costMicros / 1_000_000).toFixed(6)}`;
}
