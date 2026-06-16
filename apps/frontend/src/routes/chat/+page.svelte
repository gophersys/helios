<script lang="ts">
  // The chat slice — the demo centerpiece, rebuilt on the Eden design system (@eden/primitives +
  // @eden/theme, ADR-0024) and wired to the LIVE agent + permission flow (ADR-0025). It talks to the
  // agentgateway backend over REAL REST + SSE: a "session" IS a PRODUCT Eden builds via its 10-phase
  // SDLC, so creation is the multi-step PRODUCT WIZARD. The right pane streams the conversation via
  // the per-session SSE stream, rendering the agent event taxonomy with the primitives — Message
  // (user/assistant bubbles), StreamingText (the live token stream), ThinkingBlock (reasoning),
  // ToolCall (tool events), UsageMeter (the live cost/token meter), and the INTERACTIVE
  // PermissionRequest card (the human-in-the-loop gate). A permission decision flows
  // GatewayClient.resolve(...) -> session.Resolve -> the native control_response, so the agent
  // proceeds or is blocked, and the resolved state reflects on the card. The prompt/steer/abort
  // control verbs, the session list, and the SSE/Last-Event-ID reconnect (B7) are preserved.
  import { onDestroy } from 'svelte';
  import { Button, Input, Message } from '@eden/primitives';
  import { GatewayClient, GatewayError } from '$lib/gateway/client';
  import { resolveGatewayUrl } from '$lib/gateway/configuration';
  import { ChatSession } from '$lib/gateway/session.svelte';
  import type { AgentView, Harness, ProductConfig, ProductHarness } from '$lib/gateway/types';
  import { edenTheme } from '$lib/theme/edenTheme';
  import ChatMessage from '$lib/chat/ChatMessage.svelte';
  import ChatTool from '$lib/chat/ChatTool.svelte';
  import ChatPermission from '$lib/chat/ChatPermission.svelte';
  import ChatUsageMeter from '$lib/chat/ChatUsageMeter.svelte';
  import ChatStatusBar from '$lib/chat/ChatStatusBar.svelte';
  import ChatContextBar from '$lib/chat/ChatContextBar.svelte';
  import RightPanel from '$lib/chat/RightPanel.svelte';
  import ProductWizard from '$lib/chat/wizard/ProductWizard.svelte';
  import { agentTypeFor } from '$lib/workspace/agentWorkspace';

  const client = new GatewayClient(resolveGatewayUrl());
  const theme = edenTheme;

  // ── session-list state ───────────────────────────────────────────────────────.
  let sessions = $state<AgentView[]>([]);
  let listError = $state<string | null>(null);
  let healthy = $state<boolean | null>(null);

  // ── product-wizard state ─────────────────────────────────────────────────────.
  let showWizard = $state(false);

  /** Map the product harness onto the chat label set (the SSE/control seam is harness-agnostic;
   *  `codex` folds to a claude-tone label for the chrome only — the full product still rides). */
  function chatHarness(harness: ProductHarness): Harness {
    return harness === 'omp' ? 'omp' : 'claude';
  }

  /** REVIEW → Launch: create the session carrying the edited ProductConfig, then open the chat view
   *  streaming the real agent. Created WITHOUT an opening prompt so it starts in `ready`; the first
   *  turn is then driven through the control channel so the user bubble renders from a clean state. */
  async function launchProduct(payload: {
    product: ProductConfig;
    harness: ProductHarness;
    prompt: string;
  }): Promise<void> {
    const harness = chatHarness(payload.harness);
    const created = await client.createSession({ harness, product: payload.product });
    await refreshList();
    showWizard = false;
    await attach(created.id, harness);
    const opening = payload.prompt.trim();
    if (opening && active) await active.send(opening);
  }

  // ── open-session state ───────────────────────────────────────────────────────.
  let active = $state<ChatSession | null>(null);
  let activeHarness = $state<Harness | null>(null);

  // The active session's AGENT TYPE drives the right panel's widget stack. Derived from the
  // session's template (carried on the session-list record); defaults to implementer.
  const activeType = $derived(
    active ? agentTypeFor(sessions.find((s) => s.id === active?.id)?.template, active.harness) : null,
  );
  let composer = $state('');
  let scroller = $state<HTMLElement | null>(null);

  async function refreshHealth() {
    healthy = await client.health();
  }

  async function refreshList() {
    try {
      const page = await client.listSessions();
      sessions = page.sessions;
      listError = null;
    } catch (cause) {
      listError = cause instanceof GatewayError ? `${cause.kind}: ${cause.message}` : String(cause);
    }
  }

  // Initial load (client-only route).
  $effect(() => {
    void refreshHealth();
    void refreshList();
  });

  // Autoscroll the transcript as entries stream in.
  $effect(() => {
    if (active && active.entries.length >= 0 && scroller) {
      queueMicrotask(() => {
        if (scroller) scroller.scrollTop = scroller.scrollHeight;
      });
    }
  });

  function openSession(agent: AgentView): void {
    const harness = (agent as { labels?: Record<string, string> }).labels?.harness as
      | Harness
      | undefined;
    void attach(agent.id, harness ?? 'claude');
  }

  async function attach(id: string, harness: Harness): Promise<void> {
    active?.close();
    const session = new ChatSession(client, id, harness);
    active = session;
    activeHarness = harness;
    session.open();
  }

  async function sendComposer(): Promise<void> {
    const text = composer.trim();
    if (!text || !active) return;
    composer = '';
    await active.send(text);
  }

  function onComposerKey(event: KeyboardEvent): void {
    // Enter sends; Shift+Enter would insert a newline (the input is single-line, so this is plain Enter).
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      void sendComposer();
    }
  }

  // The dev-plane permission-demo sentinel (mirrors devserve.permissionDemoSentinel). Sending a
  // prompt carrying it drives the agent to request an OUT-OF-GRANT tool, so the demo can exercise
  // the live permission round-trip on demand. The LIVE gateway ignores it (a real agent asks for a
  // tool on its own when it needs one) — this affordance is the dev-plane trigger for the gate.
  const PERMISSION_DEMO_PROMPT = 'eden:demo:permission — clean the build directory';

  async function requestOutOfGrantTool(): Promise<void> {
    if (!active) return;
    await active.send(PERMISSION_DEMO_PROMPT);
  }

  async function steer(): Promise<void> {
    const text = composer.trim() || 'Refocus on the primary objective.';
    composer = '';
    await active?.steer(text);
  }

  async function abort(): Promise<void> {
    await active?.abort();
  }

  async function stopSession(): Promise<void> {
    if (!active) return;
    const id = active.id;
    // Clear the UI OPTIMISTICALLY so stop feels instant (responsive UX): close the SSE stream and
    // drop the active session immediately, THEN record the stop intent + reap server-side. Awaiting
    // the reap first would freeze the UI for as long as it takes to terminate a real harness child
    // mid-turn (tens of seconds) — the stop intent is durable regardless, so the UI must not block.
    active.close();
    active = null;
    activeHarness = null;
    try {
      await client.stop(id);
    } catch (cause) {
      listError = cause instanceof GatewayError ? `${cause.kind}: ${cause.message}` : String(cause);
    }
    await refreshList();
  }

  async function resumeSession(): Promise<void> {
    if (!active) return;
    try {
      await client.resume(active.id);
    } catch (cause) {
      listError = cause instanceof GatewayError ? `${cause.kind}: ${cause.message}` : String(cause);
    }
  }

  function connectionTone(status: string): 'ok' | 'info' | 'warn' | 'muted' {
    if (status === 'open') return 'ok';
    if (status === 'connecting' || status === 'reconnecting') return 'info';
    if (status === 'ended') return 'muted';
    return 'warn';
  }

  /** The session-navigator status dot: the ACTIVE session reflects its LIVE activity in real time;
   *  the others show their last-known lifecycle from the session list. Drives the dot's colour + pulse. */
  function sessionDotState(agent: AgentView): string {
    if (active?.id === agent.id) {
      const a = active.activity;
      if (a === 'thinking' || a === 'responding' || a === 'tool') return 'working';
      if (a === 'done') return 'done';
      if (a === 'failed') return 'error';
      return active.connection === 'open' ? 'ready' : 'connecting';
    }
    if (agent.status === 'running') return 'working';
    if (agent.status === 'completed') return 'done';
    if (agent.status === 'failed' || agent.status === 'aborted') return 'error';
    return 'idle';
  }

  onDestroy(() => active?.close());
</script>

<svelte:head>
  <title>Eden — chat</title>
</svelte:head>

<div class="chat" class:chat--panel={active} data-testid="chat-app">
  <!-- ── left rail: sessions ──────────────────────────────────────────────── -->
  <aside class="rail">
    <header class="rail__head">
      <div>
        <p class="eyebrow">Eden · agent gateway</p>
        <h1 class="rail__title">Sessions</h1>
      </div>
      <span
        class="chip chip--{healthy === null ? 'muted' : healthy ? 'ok' : 'warn'}"
        data-testid="gateway-health"
      >
        {healthy === null ? '…' : healthy ? 'gateway up' : 'gateway down'}
      </span>
    </header>

    <div class="rail__new" data-testid="new-session">
      <Button variant="primary" {theme} onclick={() => (showWizard = true)}>＋ New product</Button>
    </div>

    {#if listError}
      <p class="rail__error">{listError}</p>
    {/if}

    <ul class="rail__list" data-testid="session-list">
      {#each sessions as agent (agent.id)}
        <li>
          <button
            class="session"
            class:session--active={active?.id === agent.id}
            data-testid="session-item"
            data-session-id={agent.id}
            onclick={() => openSession(agent)}
          >
            <span class="session__id">
              <span
                class="session__dot"
                data-testid="session-dot"
                data-state={sessionDotState(agent)}
                aria-hidden="true"
              ></span>
              {agent.id}
            </span>
            <span class="session__meta">
              <span class="chip chip--muted">{agent.status}</span>
              <span class="session__template">{agent.template}</span>
            </span>
          </button>
        </li>
      {/each}
      {#if sessions.length === 0}
        <li class="rail__empty">No sessions yet — create one to start.</li>
      {/if}
    </ul>
  </aside>

  <!-- ── main: chat view ──────────────────────────────────────────────────── -->
  <main class="view">
    {#if !active}
      <div class="empty" data-testid="empty-state">
        <h2>Build a product with Eden</h2>
        <p>
          Every session is a product Eden builds through its 10-phase SDLC. Start a new product —
          describe what you're building, edit the configuration Eden proposes, then watch the agent
          stream every event live: reasoning, tool calls, permission gates, and a token/cost meter.
        </p>
        <div class="empty__cta">
          <Button variant="primary" {theme} onclick={() => (showWizard = true)}
            >＋ New product</Button
          >
        </div>
      </div>
    {:else}
      <header class="view__head">
        <div class="view__id">
          <h2>{active.id}</h2>
          <span class="chip chip--info" data-testid="active-harness">{activeHarness}</span>
          <span class="chip chip--muted" data-testid="session-state">{active.sessionState}</span>
          <span class="chip chip--{connectionTone(active.connection)}" data-testid="sse-status">
            {active.connection}
          </span>
        </div>
        <div class="view__controls">
          <span class="control" data-testid="request-tool">
            <Button
              variant="secondary"
              {theme}
              disabled={active.terminal}
              onclick={requestOutOfGrantTool}>request tool</Button
            >
          </span>
          <span class="control" data-testid="steer">
            <Button variant="ghost" {theme} disabled={active.terminal} onclick={steer}>steer</Button
            >
          </span>
          <span class="control" data-testid="abort">
            <Button variant="ghost" {theme} disabled={active.terminal} onclick={abort}>abort</Button
            >
          </span>
          <span class="control" data-testid="resume">
            <Button variant="ghost" {theme} onclick={resumeSession}>resume</Button>
          </span>
          <span class="control" data-testid="stop">
            <Button variant="danger" {theme} onclick={stopSession}>stop</Button>
          </span>
        </div>
      </header>

      <div class="view__body">
        <div class="transcript" bind:this={scroller} data-testid="transcript">
          <ul class="turns" role="list">
            {#each active.entries as entry (entry.id)}
              {#if entry.role === 'user'}
                <li class="turn turn--user" data-testid="user-message">
                  <Message role="user" {theme}>{entry.text}</Message>
                </li>
              {:else if entry.role === 'assistant'}
                <li class="turn">
                  <ChatMessage
                    text={entry.text}
                    thinking={entry.thinking}
                    streaming={entry.streaming}
                    {theme}
                  />
                </li>
              {:else if entry.role === 'tool'}
                <li class="turn"><ChatTool tool={entry.tool} {theme} /></li>
              {:else if entry.role === 'permission'}
                <li class="turn">
                  <ChatPermission
                    permission={entry.permission}
                    {theme}
                    onresolve={(requestId, verdict, scope) =>
                      active?.resolve(requestId, verdict, scope)}
                  />
                </li>
              {:else if entry.role === 'notice'}
                <li class="turn">
                  <div class="notice notice--{entry.tone}" data-testid="notice">{entry.text}</div>
                </li>
              {:else if entry.role === 'terminal'}
                <li class="turn">
                  <div class="terminal" data-testid="terminal-banner" data-outcome={entry.outcome}>
                    <span class="chip chip--{entry.outcome === 'completed' ? 'ok' : 'warn'}">
                      {entry.outcome}
                    </span>
                    {#if entry.text}<span class="terminal__text">{entry.text}</span>{/if}
                    {#if entry.reason}<span class="chip chip--warn">{entry.reason}</span>{/if}
                  </div>
                </li>
              {/if}
            {/each}
          </ul>
          {#if active.entries.length === 0}
            <p class="transcript__waiting" data-testid="transcript-waiting">
              Waiting for the first events…
            </p>
          {/if}
        </div>

        <aside class="meterrail">
          <ChatUsageMeter meter={active.meter} {theme} />
        </aside>
      </div>

      <!-- the live agent status bar (the TUI status line): spinner + verb + thinking tokens + clock -->
      <ChatStatusBar session={active} {theme} />
      <!-- the context/observability bar (Claude-Code-style): model · ctx gauge · tokens · cost · live turns/tools -->
      <ChatContextBar meter={active.meter} {theme} />

      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <div class="composer" data-testid="composer-input" onkeydown={onComposerKey}>
        <div class="composer__input">
          <Input
            bind:value={composer}
            placeholder="Send a prompt…"
            aria-label="Send a prompt"
            {theme}
          />
        </div>
        <span class="control" data-testid="composer-send">
          <Button variant="primary" {theme} onclick={sendComposer}>Send</Button>
        </span>
      </div>
    {/if}
  </main>

  <!-- ── right panel: the agent-type-aware workspace (files/assets the agent generates) ────── -->
  {#if active && activeType}
    <RightPanel session={active} agentType={activeType} {theme} />
  {/if}

  <!-- ── product wizard (the create flow) ───────────────────────────────────── -->
  {#if showWizard}
    <ProductWizard
      propose={(prompt) => client.propose(prompt)}
      onlaunch={launchProduct}
      oncancel={() => (showWizard = false)}
    />
  {/if}
</div>

<style>
  .chat {
    display: grid;
    grid-template-columns: 300px minmax(0, 1fr);
    height: 100vh;
    overflow: hidden;
  }
  /* When a session is active the workspace opens its third region: the agent-type-aware panel. */
  .chat--panel {
    grid-template-columns: 280px minmax(0, 1fr) clamp(300px, 26vw, 380px);
  }
  @media (max-width: 1100px) {
    .chat--panel {
      grid-template-columns: 240px minmax(0, 1fr);
    }
    .chat--panel :global([data-testid='agent-panel']) {
      display: none;
    }
  }

  /* ── rail ── */
  .rail {
    background: var(--eden-app-rail-bg);
    border-inline-end: 1px solid var(--eden-app-line);
    padding: var(--space-5, 20px) var(--space-4, 16px);
    display: flex;
    flex-direction: column;
    gap: var(--space-3, 12px);
    overflow-y: auto;
  }
  .rail__head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-2, 8px);
  }
  .eyebrow {
    font-family: var(--font-code);
    font-size: var(--font-size-caption, 12px);
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--eden-app-muted);
    margin: 0 0 var(--space-1, 4px);
  }
  .rail__title {
    font-size: var(--font-size-title, 23px);
    margin: 0;
  }
  .rail__new {
    display: flex;
  }
  .rail__new :global(button) {
    inline-size: 100%;
  }
  .rail__error {
    color: var(--color-error);
    font-size: var(--font-size-label, 13px);
    margin: 0;
  }
  .rail__list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-2, 8px);
  }
  .rail__empty {
    color: var(--eden-app-muted);
    font-size: var(--font-size-label, 13px);
    padding: var(--space-2, 8px) 0;
  }
  .session {
    inline-size: 100%;
    text-align: start;
    background: var(--eden-app-panel-bg);
    border: 1px solid var(--eden-app-panel-line);
    border-radius: var(--eden-app-radius, 8px);
    padding: var(--space-3, 12px);
    cursor: pointer;
    display: flex;
    flex-direction: column;
    gap: var(--space-1, 4px);
    transition:
      border-color var(--duration-short-3, 150ms) var(--ease-standard, ease),
      transform var(--duration-short-3, 150ms) var(--ease-standard, ease);
    color: inherit;
    font: inherit;
  }
  .session:hover {
    border-color: var(--eden-app-accent);
    transform: translateY(-1px);
  }
  .session--active {
    border-color: var(--eden-app-accent);
    box-shadow: 0 0 0 1px var(--eden-app-accent);
  }
  .session__id {
    font-family: var(--font-code);
    font-weight: 650;
    font-size: var(--font-size-label, 13px);
    display: flex;
    align-items: center;
    gap: var(--space-2, 8px);
  }
  /* The live status dot: a calm colour at rest, a pulsing accent while the agent is working. */
  .session__dot {
    inline-size: 8px;
    block-size: 8px;
    border-radius: 50%;
    flex: none;
    background: var(--eden-app-muted);
  }
  .session__dot[data-state='working'] {
    background: var(--eden-app-accent);
    animation: session-dot-pulse 1.1s ease-in-out infinite;
  }
  .session__dot[data-state='ready'] {
    background: var(--color-info);
  }
  .session__dot[data-state='done'] {
    background: color-mix(in oklab, var(--color-info) 60%, var(--eden-app-muted));
  }
  .session__dot[data-state='error'] {
    background: var(--color-error);
  }
  .session__dot[data-state='connecting'] {
    background: var(--color-warning);
  }
  @keyframes session-dot-pulse {
    50% {
      opacity: 0.35;
      transform: scale(0.85);
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .session__dot[data-state='working'] {
      animation: none;
    }
  }
  .session__meta {
    display: flex;
    align-items: center;
    gap: var(--space-2, 8px);
    flex-wrap: wrap;
  }
  .session__template {
    font-size: var(--font-size-caption, 12px);
    color: var(--eden-app-muted);
    font-family: var(--font-code);
  }

  /* ── view ── */
  .view {
    display: flex;
    flex-direction: column;
    min-width: 0;
    height: 100vh;
  }
  .empty {
    margin: auto;
    max-width: 52ch;
    text-align: center;
    padding: var(--space-8, 32px);
    display: flex;
    flex-direction: column;
    gap: var(--space-4, 16px);
    align-items: center;
  }
  .empty p {
    color: var(--eden-app-muted);
  }
  .empty__cta {
    display: flex;
  }
  .view__head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-4, 16px);
    padding: var(--space-4, 16px) var(--space-6, 24px);
    border-block-end: 1px solid var(--eden-app-line);
    flex-wrap: wrap;
  }
  .view__id {
    display: flex;
    align-items: center;
    gap: var(--space-2, 8px);
    flex-wrap: wrap;
  }
  .view__id h2 {
    margin: 0;
    font-family: var(--font-code);
    font-size: var(--font-size-body-large, 19px);
  }
  .view__controls {
    display: flex;
    align-items: center;
    gap: var(--space-2, 8px);
    flex-wrap: wrap;
  }
  /* A `control` is a thin inline wrapper carrying a stable data-testid over an @eden/primitives
     Button: a testid click lands on the Button it contains, and `toBeDisabled()` reads the inner
     native <button> (bits-ui forwards the disabled attribute). The visible affordance is the Button. */
  .control {
    display: inline-flex;
  }
  .view__body {
    flex: 1;
    display: grid;
    grid-template-columns: 1fr 300px;
    min-height: 0;
    overflow: hidden;
  }
  .transcript {
    overflow-y: auto;
    padding: var(--space-6, 24px);
  }
  .turns {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-4, 16px);
  }
  .turn {
    display: flex;
    flex-direction: column;
  }
  .turn--user {
    align-items: flex-end;
  }
  .turn--user :global(.eden-message) {
    max-inline-size: 70ch;
  }
  .transcript__waiting {
    color: var(--eden-app-muted);
    font-style: italic;
  }
  .meterrail {
    border-inline-start: 1px solid var(--eden-app-line);
    padding: var(--space-5, 20px) var(--space-4, 16px);
    overflow-y: auto;
    background: var(--eden-app-rail-bg);
  }

  .notice {
    border-radius: var(--eden-app-radius, 8px);
    padding: var(--space-2, 8px) var(--space-3, 12px);
    font-size: var(--font-size-label, 13px);
    border: 1px dashed var(--eden-app-line);
    max-width: 78ch;
  }
  .notice--warn {
    border-color: var(--color-error);
    color: var(--color-error);
    background: color-mix(in oklab, var(--color-error) 8%, var(--color-surface));
  }
  .notice--info {
    color: var(--eden-app-muted);
  }

  .terminal {
    display: flex;
    align-items: center;
    gap: var(--space-3, 12px);
    flex-wrap: wrap;
    padding: var(--space-3, 12px) var(--space-4, 16px);
    border: 1px solid var(--eden-app-line);
    border-radius: var(--eden-app-radius, 8px);
    background: var(--eden-app-panel-bg);
    max-width: 78ch;
  }
  .terminal__text {
    font-weight: 600;
  }

  /* ── composer ── */
  .composer {
    display: flex;
    align-items: center;
    gap: var(--space-3, 12px);
    padding: var(--space-4, 16px) var(--space-6, 24px);
    border-block-start: 1px solid var(--eden-app-line);
  }
  .composer__input {
    flex: 1;
  }
  .composer__input :global(input) {
    inline-size: 100%;
  }

  /* ── chips (app-chrome micro-labels, token-driven off the generated roles) ── */
  .chip {
    display: inline-flex;
    align-items: center;
    gap: 0.35em;
    background: color-mix(in oklab, var(--color-secondary) 22%, var(--color-surface));
    color: var(--color-on-surface);
    font-family: var(--font-code);
    font-size: var(--font-size-caption, 12px);
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    border-radius: 999px;
    padding: 0.18rem 0.6rem;
    line-height: 1.4;
    white-space: nowrap;
  }
  .chip--info {
    background: color-mix(in oklab, var(--color-info) 16%, var(--color-surface));
    color: var(--color-info);
  }
  .chip--ok {
    background: var(--color-primary);
    color: var(--color-on-primary);
  }
  .chip--warn {
    background: color-mix(in oklab, var(--color-warning) 22%, var(--color-surface));
    color: var(--color-warning);
  }
  .chip--muted {
    background: color-mix(in oklab, var(--color-on-surface) 8%, var(--color-surface));
    color: var(--eden-app-muted);
  }

  @media (max-width: 760px) {
    .chat {
      grid-template-columns: 1fr;
    }
    .rail {
      display: none;
    }
    .view__body {
      grid-template-columns: 1fr;
    }
    .meterrail {
      border-inline-start: none;
      border-block-start: 1px solid var(--eden-app-line);
    }
  }
</style>
