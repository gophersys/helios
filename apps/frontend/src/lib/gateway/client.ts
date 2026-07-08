// The agentgateway REST client — a thin, typed fetch wrapper over the gateway's HTTP surface
// (apps/agentgateway/internal/gateway/router.go). It owns NO state: it translates a typed call
// into one request and decodes the redaction-safe JSON projection (or throws a typed
// GatewayError carrying the gateway's stable Kind token). The live SSE stream is a separate
// seam (sse.ts) — this client covers create / list / get / control / stop / resume / transcript.

import type { Report } from '@eden/visualization';
import type {
  AgentConfigView,
  AgentView,
  ControlResponse,
  CreateResponse,
  Envelope,
  ErrorBody,
  Harness,
  ListAgentConfigsResponse,
  ListProjectsResponse,
  ListResponse,
  PermissionScope,
  PermissionVerdict,
  ProductConfig,
  ProjectView,
  ResolveResponse,
  TranscriptResponse,
} from './types';

/** GatewayError carries the gateway's stable Kind token and operator-safe message so a caller
 *  branches on `kind` (the wire contract), never on a substring. The HTTP status is retained
 *  for the rare case a caller needs it (e.g. a 409 conflict on an out-of-phase control verb). */
export class GatewayError extends Error {
  readonly kind: string;
  readonly status: number;

  constructor(kind: string, message: string, status: number) {
    super(message);
    this.name = 'GatewayError';
    this.kind = kind;
    this.status = status;
  }
}

/** The tenancy + template the chat surface scopes every create/list call to. The dev-serve's
 *  seeded record plane resolves exactly this template; the org/project are free-form scopes. */
export interface Tenancy {
  organizationId: string;
  projectId: string;
  templateName: string;
  templateVersion: string;
}

/** The default dev tenancy — scoped to the dev-serve's seeded `implementer-go@1.0.0` template
 *  (orchestratortest.DefaultTemplate). Org/project are arbitrary dev scopes. */
export const DEV_TENANCY: Tenancy = {
  organizationId: 'eden-dev',
  projectId: 'chat-slice',
  templateName: 'implementer-go',
  templateVersion: '1.0.0',
};

/** EditorView is the read-only VS Code coordinates GET /sessions/{id}/editor returns: `url` is the
 *  code-server URL (open in a new tab on web); `worktreePath` is the dir the editor opens; `sshHost` is
 *  the optional ssh-remote host the desktop app builds a vscode:// URI against ("" == web-only). */
export interface EditorView {
  url: string;
  worktreePath: string;
  sshHost: string;
}

/** GatewayClient is constructed with the gateway base URL (e.g. http://127.0.0.1:8080). It
 *  holds no session state — each method is one request. */
export class GatewayClient {
  readonly baseUrl: string;
  private readonly tenancy: Tenancy;

  constructor(baseUrl: string, tenancy: Tenancy = DEV_TENANCY) {
    // Normalize: drop a trailing slash so path joins are unambiguous.
    this.baseUrl = baseUrl.replace(/\/+$/, '');
    this.tenancy = tenancy;
  }

  /** The absolute URL for a gateway path (so the SSE seam can build the EventSource URL too). */
  url(path: string): string {
    return `${this.baseUrl}${path}`;
  }

  /** GET /healthz — liveness. Returns true on a 200 {status:"ok"}, false on any fault. */
  async health(): Promise<boolean> {
    try {
      const response = await fetch(this.url('/healthz'), { method: 'GET' });
      return response.ok;
    } catch {
      return false;
    }
  }

  /** POST /product/propose — the create-flow wizard's first step: from the user's initial prompt,
   *  Eden AI-PROPOSES a ProductConfig the user then edits. In the LIVE gateway this runs ONE real
   *  harness turn instructed to return ProductConfig JSON; in the dev-serve it is a deterministic,
   *  prompt-derived fake (so the E2E is stable). The route returns the uniform Eden envelope
   *  ({data, errors, kind}); this unwraps `.data` — a complete, normalized, wizard-ready config. */
  async propose(prompt: string): Promise<ProductConfig> {
    const envelope = await this.requestJSON<Envelope<ProductConfig>>('POST', '/product/propose', {
      prompt,
    });
    return envelope.data;
  }

  /** POST /sessions — create a session. The harness is recorded as a label (the dev-serve picks
   *  the live harness from its routing table). When `prompt` is supplied the gateway sends it as
   *  the opening turn; the chat surface creates WITHOUT a prompt and drives the first turn via
   *  the control channel, so the live stream is observed from a clean `ready` state. When the
   *  create-flow wizard supplies a `product` ProductConfig, it rides alongside: the gateway folds
   *  it into the build agent's initial-context preamble (a "session" IS a PRODUCT Eden builds). */
  async createSession(options: {
    harness: Harness;
    prompt?: string;
    runId?: string;
    product?: ProductConfig;
  }): Promise<CreateResponse> {
    const body: Record<string, unknown> = {
      organizationId: this.tenancy.organizationId,
      projectId: this.tenancy.projectId,
      templateName: this.tenancy.templateName,
      templateVersion: this.tenancy.templateVersion,
      by: 'chat-slice-ui',
      labels: { harness: options.harness },
    };
    if (options.prompt) body.prompt = options.prompt;
    if (options.runId) body.runId = options.runId;
    if (options.product) body.product = options.product;
    return this.requestJSON<CreateResponse>('POST', '/sessions', body);
  }

  /** POST /projects — persist a Project from the scoped product (the create-flow's "Build it"). The
   *  route is enveloped; this unwraps `.data` (the stored projectView). When `sessionId` is supplied
   *  the gateway records the project as BUILDING (a build session was spawned), DRAFT otherwise. */
  async createProject(options: {
    product: ProductConfig;
    name?: string;
    idea?: string;
    sessionId?: string;
  }): Promise<ProjectView> {
    const body: Record<string, unknown> = { product: options.product };
    if (options.name) body.name = options.name;
    if (options.idea) body.idea = options.idea;
    if (options.sessionId) body.sessionId = options.sessionId;
    const envelope = await this.requestJSON<Envelope<ProjectView>>('POST', '/projects', body);
    return envelope.data;
  }

  /** GET /projects — the dashboard grid: persisted projects, newest first. Enveloped; unwraps
   *  `.data`. `limit`/`cursor` page the list. */
  async listProjects(
    options: { limit?: number; cursor?: string } = {},
  ): Promise<ListProjectsResponse> {
    const query = new URLSearchParams();
    if (options.limit != null) query.set('limit', String(options.limit));
    if (options.cursor) query.set('cursor', options.cursor);
    const suffix = query.toString() ? `?${query.toString()}` : '';
    const envelope = await this.requestJSON<Envelope<ListProjectsResponse>>(
      'GET',
      `/projects${suffix}`,
    );
    return envelope.data;
  }

  /** GET /projects/{id} — one persisted project (enveloped; unwraps `.data`). */
  async getProject(id: string): Promise<ProjectView> {
    const envelope = await this.requestJSON<Envelope<ProjectView>>(
      'GET',
      `/projects/${encodeURIComponent(id)}`,
    );
    return envelope.data;
  }

  /** GET /projects/{id}/insight — the codeinsight Report over the project's worktree (the self-feeding
   *  seam; apps/agentgateway insight_handler.go). NOT enveloped: the handler writes the bare Report at
   *  200 (a redaction-safe projection @eden/visualization renders). It throws a typed GatewayError on the
   *  documented fault arms (not-found 404 when the project id is unknown; unavailable 503 when no worktree
   *  is materialized, the analysis exceeds its 60s budget, or persistence is unconfigured) — the Insight
   *  view branches on `kind` to degrade honestly (an EmptyState, never a spinner-forever). The analysis is
   *  synchronous and can be slow on a large repo, so it is bounded server-side (60s) not here. */
  async insight(id: string): Promise<Report> {
    return this.requestJSON<Report>('GET', `/projects/${encodeURIComponent(id)}/insight`);
  }

  /** GET /sessions/{id}/editor — read-only VS Code coordinates for the session's project worktree.
   *  NOT enveloped (mirrors the workspace surface): { url, worktreePath, sshHost }. Throws when the
   *  editor is not configured (503) so the caller surfaces an inline notice instead of opening a blank tab. */
  async getEditor(sessionId: string): Promise<EditorView> {
    const response = await fetch(this.url(`/sessions/${encodeURIComponent(sessionId)}/editor`));
    if (!response.ok) {
      throw new Error(`the editor is unavailable (${response.status})`);
    }
    return (await response.json()) as EditorView;
  }

  /** Retry a stalled project's build: re-POST `POST /projects` from the surfaced view fields. The
   *  create-saga is idempotency-keyed per project (saga.go: CreateStep.IdempotencyKey), so a re-create
   *  RESUMES the provisioning walk from where it stalled rather than double-applying a committed step.
   *  The view does not carry the full ProductConfig (the wire projection flattens it), so this rebuilds
   *  a MINIMAL product from the surfaced kind/harness/stacks/services/idea; the gateway re-normalizes
   *  every empty field to its Eden default (NormalizeProductConfig), yielding a complete, valid spec —
   *  no fabricated capability. Returns the refreshed projectView (its status re-enters the walk). */
  async resumeProject(project: ProjectView): Promise<ProjectView> {
    const languages = project.stacks ?? [];
    const product: ProductConfig = {
      productName: project.name,
      productKind: project.kind,
      summary: (project.idea ?? '').trim(),
      // The view flattens languages + frameworks into one `stacks` list; hand them back as languages
      // and let NormalizeProductConfig redistribute/default frameworks for the kind (no guess here).
      stack: { languages, frameworks: [] },
      services: project.services ?? [],
      capabilities: {
        harness: project.harness,
        model: '',
        toolGrants: [],
        skills: [],
        rules: [],
      },
      sdlcPhases: [],
      sandbox: { posture: 'strict', egressAllow: [] },
    };
    return this.createProject({ product, name: project.name, idea: project.idea });
  }

  /** GET /agent-configs — the saved per-agent-type configurations (the Settings → Agents loader).
   *  Enveloped; unwraps `.data.configs`. An agent type with no saved config is simply absent. */
  async listAgentConfigs(): Promise<AgentConfigView[]> {
    const envelope = await this.requestJSON<Envelope<ListAgentConfigsResponse>>(
      'GET',
      '/agent-configs',
    );
    return envelope.data.configs;
  }

  /** PUT /agent-configs/{agentType} — upsert one agent type's configuration. Enveloped; unwraps
   *  `.data` (the stored config). The server normalizes (posture constrained, fields trimmed). */
  async saveAgentConfig(
    agentType: string,
    body: { model: string; toolGrants: string[]; sandboxPosture: string },
  ): Promise<AgentConfigView> {
    const envelope = await this.requestJSON<Envelope<AgentConfigView>>(
      'PUT',
      `/agent-configs/${encodeURIComponent(agentType)}`,
      body,
    );
    return envelope.data;
  }

  /** GET /sessions — the project-scoped session list. `active` narrows to live sessions. */
  async listSessions(options: { active?: boolean; cursor?: string } = {}): Promise<ListResponse> {
    const query = new URLSearchParams({
      organizationId: this.tenancy.organizationId,
      projectId: this.tenancy.projectId,
    });
    if (options.active) query.set('active', 'true');
    if (options.cursor) query.set('cursor', options.cursor);
    return this.requestJSON<ListResponse>('GET', `/sessions?${query.toString()}`);
  }

  /** GET /sessions/{id} — one session record. */
  async getSession(id: string): Promise<AgentView> {
    return this.requestJSON<AgentView>('GET', `/sessions/${encodeURIComponent(id)}`);
  }

  /** POST /sessions/{id}/control verb=prompt — send a turn (valid in ready/awaiting-input). */
  async prompt(id: string, text: string): Promise<ControlResponse> {
    return this.control(id, { command: 'prompt', text });
  }

  /** POST /sessions/{id}/control verb=steer — interject into a running turn (CapSteer). */
  async steer(id: string, text: string): Promise<ControlResponse> {
    return this.control(id, { command: 'steer', text });
  }

  /** POST /sessions/{id}/control verb=abort — cancel the in-flight turn. */
  async abort(id: string): Promise<ControlResponse> {
    return this.control(id, { command: 'abort' });
  }

  /** POST /sessions/{id}/permissions/{requestId} — answer a pending out-of-grant permission
   *  the SSE stream surfaced (ADR-0025). `verdict` is allow|deny; `scope` bounds an allow to
   *  this request only ("once", the default) or the running session ("session"). This is a
   *  Resolve, NOT a control verb: it calls the live session's distinct Resolve method, and the
   *  resulting EventPermissionResolved arrives on the stream (the returned `admittedSeq`
   *  correlates it). An unknown/already-resolved requestId is a 404 (GatewayError kind
   *  "not-found"); a verdict the policy wall refuses is a 403 (kind "permission"). */
  async resolve(
    sessionId: string,
    requestId: string,
    verdict: PermissionVerdict,
    scope: PermissionScope = 'once',
  ): Promise<ResolveResponse> {
    return this.requestJSON<ResolveResponse>(
      'POST',
      `/sessions/${encodeURIComponent(sessionId)}/permissions/${encodeURIComponent(requestId)}`,
      { verdict, scope },
    );
  }

  /** POST /sessions/{id}/stop — record the terminal stop intent and reap the live session. */
  async stop(id: string): Promise<void> {
    await this.requestJSON<{ status: string }>('POST', `/sessions/${encodeURIComponent(id)}/stop`);
  }

  /** POST /sessions/{id}/resume — record the resume intent (the stream is reconstructed by the
   *  client reconnecting to the SSE route with its last-seen seq). */
  async resume(id: string): Promise<void> {
    await this.requestJSON<{ status: string }>(
      'POST',
      `/sessions/${encodeURIComponent(id)}/resume`,
    );
  }

  /** GET /sessions/{id}/transcript — the persisted Run, queryable after the session ends. */
  async transcript(id: string, fromSeq?: number): Promise<TranscriptResponse> {
    const suffix = fromSeq != null ? `?from-seq=${fromSeq}` : '';
    return this.requestJSON<TranscriptResponse>(
      'GET',
      `/sessions/${encodeURIComponent(id)}/transcript${suffix}`,
    );
  }

  private async control(
    id: string,
    body: { command: 'prompt' | 'steer' | 'abort'; text?: string },
  ): Promise<ControlResponse> {
    return this.requestJSON<ControlResponse>(
      'POST',
      `/sessions/${encodeURIComponent(id)}/control`,
      body,
    );
  }

  /** requestJSON issues one request and decodes the JSON body, or throws a typed GatewayError
   *  built from the gateway's {kind,message} envelope (falling back to the status text). */
  private async requestJSON<T>(method: string, path: string, body?: unknown): Promise<T> {
    let response: Response;
    try {
      response = await fetch(this.url(path), {
        method,
        headers: body !== undefined ? { 'content-type': 'application/json' } : undefined,
        body: body !== undefined ? JSON.stringify(body) : undefined,
      });
    } catch (cause) {
      throw new GatewayError('unavailable', `gateway unreachable: ${String(cause)}`, 0);
    }
    if (!response.ok) {
      throw await this.toError(response);
    }
    return (await response.json()) as T;
  }

  /** toError decodes the redaction-safe error envelope into a typed GatewayError. */
  private async toError(response: Response): Promise<GatewayError> {
    let kind = 'unknown';
    let message = `${response.status} ${response.statusText}`;
    try {
      const envelope = (await response.json()) as ErrorBody;
      if (envelope.kind) kind = envelope.kind;
      if (envelope.message) message = envelope.message;
    } catch {
      // The body was not the standard envelope; the status line message stands.
    }
    return new GatewayError(kind, message, response.status);
  }
}
