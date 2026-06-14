<script lang="ts">
  // The chat slice — the live UI over the agentgateway backend (REAL REST + SSE). A "session" IS a
  // PRODUCT Eden builds via its 10-phase SDLC, so creation is the multi-step PRODUCT WIZARD
  // (ProductWizard.svelte): it AI-PROPOSES a ProductConfig from the prompt (POST /product/propose),
  // the user edits stack / capabilities / process / safety, and the assembled config rides
  // POST /sessions (the `product` field) which the gateway folds into the build agent's initial
  // context. Left rail: the project-scoped session list (GET /sessions) + the New product button.
  // Right: the chat view — the conversation streamed live via the per-session SSE stream
  // (GET /sessions/{id}/events), rendering EVERY event-taxonomy kind distinctly (assistant text,
  // foldable thinking, tool start/update/end, permission round-trips, a live usage/cost meter),
  // with the prompt / steer / abort control verbs (POST .../control), stop/resume
  // (POST .../stop|resume), and gap-free SSE reconnect via Last-Event-ID. The gateway picks the
  // live harness from its routing table; the claude/omp choice is recorded as a label and surfaced
  // here (the dev-serve routes both to its deterministic fake harness — from the UI's side the
  // HTTP/SSE is 100% real).
  import { onDestroy } from 'svelte';
  import { GatewayClient, GatewayError } from '$lib/gateway/client';
  import { resolveGatewayUrl } from '$lib/gateway/configuration';
  import { ChatSession } from '$lib/gateway/session.svelte';
  import type { AgentView, Harness, ProductConfig, ProductHarness } from '$lib/gateway/types';
  import UsageMeter from '$lib/chat/UsageMeter.svelte';
  import ToolCard from '$lib/chat/ToolCard.svelte';
  import PermissionCard from '$lib/chat/PermissionCard.svelte';
  import MessageBubble from '$lib/chat/MessageBubble.svelte';
  import ProductWizard from '$lib/chat/wizard/ProductWizard.svelte';

  const client = new GatewayClient(resolveGatewayUrl());

  // ── session-list state ───────────────────────────────────────────────────────.
  let sessions = $state<AgentView[]>([]);
  let listError = $state<string | null>(null);
  let healthy = $state<boolean | null>(null);

  // ── product-wizard state ─────────────────────────────────────────────────────.
  // The create flow is the multi-step PRODUCT wizard (a "session" IS a product Eden builds). It
  // proposes a ProductConfig from the prompt, the user edits it, then it rides POST /sessions.
  let showWizard = $state(false);

  /** Map the product harness onto the chat label set: the chat view + ChatSession know claude|omp
   *  (the SSE/control seam is harness-agnostic). `codex` is folded to a claude-tone label for the
   *  chrome only — the FULL product.capabilities.harness still rides the create body to the
   *  gateway, which honors it. */
  function chatHarness(harness: ProductHarness): Harness {
    return harness === 'omp' ? 'omp' : 'claude';
  }

  /** REVIEW → Launch: create the session carrying the edited ProductConfig, then open the chat
   *  view streaming the real agent. The session is created WITHOUT an opening prompt so it starts
   *  in `ready`; the synthesized first turn is then driven through the control channel, so the
   *  user bubble renders and the full event stream is observed from a clean state. */
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

  async function sendComposer(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    const text = composer.trim();
    if (!text || !active) return;
    composer = '';
    await active.send(text);
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
    try {
      await client.stop(id);
    } catch (cause) {
      // Surface but proceed — a stop on an already-terminal session is a no-op success.
      listError = cause instanceof GatewayError ? `${cause.kind}: ${cause.message}` : String(cause);
    }
    active.close();
    active = null;
    activeHarness = null;
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

  onDestroy(() => active?.close());
</script>

<svelte:head>
  <title>Eden — chat</title>
</svelte:head>

<div class="chat" data-testid="chat-app">
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

    <button
      class="btn btn--accent rail__new"
      data-testid="new-session"
      onclick={() => (showWizard = true)}
    >
      ＋ New product
    </button>

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
            <span class="session__id">{agent.id}</span>
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
          stream every event live: architecture, implementation, tool calls, and a token/cost meter.
        </p>
        <button class="btn btn--accent" onclick={() => (showWizard = true)}>＋ New product</button>
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
          <button class="btn" data-testid="steer" onclick={steer} disabled={active.terminal}
            >steer</button
          >
          <button class="btn" data-testid="abort" onclick={abort} disabled={active.terminal}
            >abort</button
          >
          <button class="btn" data-testid="resume" onclick={resumeSession}>resume</button>
          <button class="btn btn--danger" data-testid="stop" onclick={stopSession}>stop</button>
        </div>
      </header>

      <div class="view__body">
        <div class="transcript" bind:this={scroller} data-testid="transcript">
          {#each active.entries as entry (entry.id)}
            {#if entry.role === 'user'}
              <div class="bubble bubble--user" data-testid="user-message">
                <div class="bubble__role bubble__role--user">you</div>
                <div class="bubble__text">{entry.text}</div>
              </div>
            {:else if entry.role === 'assistant'}
              <MessageBubble
                text={entry.text}
                thinking={entry.thinking}
                streaming={entry.streaming}
              />
            {:else if entry.role === 'tool'}
              <ToolCard tool={entry.tool} />
            {:else if entry.role === 'permission'}
              <PermissionCard permission={entry.permission} />
            {:else if entry.role === 'notice'}
              <div class="notice notice--{entry.tone}" data-testid="notice">{entry.text}</div>
            {:else if entry.role === 'terminal'}
              <div class="terminal" data-testid="terminal-banner" data-outcome={entry.outcome}>
                <span class="chip chip--{entry.outcome === 'completed' ? 'ok' : 'warn'}">
                  {entry.outcome}
                </span>
                {#if entry.text}<span class="terminal__text">{entry.text}</span>{/if}
                {#if entry.reason}<span class="chip chip--warn">{entry.reason}</span>{/if}
              </div>
            {/if}
          {/each}
          {#if active.entries.length === 0}
            <p class="transcript__waiting" data-testid="transcript-waiting">
              Waiting for the first events…
            </p>
          {/if}
        </div>

        <aside class="meterrail">
          <UsageMeter meter={active.meter} />
        </aside>
      </div>

      <form class="composer" onsubmit={sendComposer}>
        <input
          class="composer__input"
          data-testid="composer-input"
          placeholder="Send a prompt…"
          bind:value={composer}
          autocomplete="off"
        />
        <button class="btn btn--accent" data-testid="composer-send" type="submit">Send</button>
      </form>
    {/if}
  </main>

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
    grid-template-columns: 300px 1fr;
    height: 100vh;
    overflow: hidden;
  }

  /* ── rail ── */
  .rail {
    background: var(--navbg);
    border-right: 1px solid var(--line);
    padding: 1.2rem 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.9rem;
    overflow-y: auto;
  }
  .rail__head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 0.6rem;
  }
  .eyebrow {
    font-family: var(--font-code);
    font-size: var(--type-micro);
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--muted);
    margin: 0 0 0.25rem;
  }
  .rail__title {
    font-size: 1.5rem;
    margin: 0;
  }
  .rail__new {
    width: 100%;
  }
  .rail__error {
    color: var(--chip-warn-fg);
    font-size: 0.85rem;
    margin: 0;
  }
  .rail__list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  .rail__empty {
    color: var(--muted);
    font-size: 0.9rem;
    padding: 0.5rem 0;
  }
  .session {
    width: 100%;
    text-align: left;
    background: var(--panel-bg);
    border: 1px solid var(--panel-line);
    border-radius: var(--radius);
    padding: 0.6rem 0.7rem;
    cursor: pointer;
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
    transition:
      border-color 0.12s ease,
      transform 0.12s ease;
    color: inherit;
    font: inherit;
  }
  .session:hover {
    border-color: var(--accent);
    transform: translateY(-1px);
  }
  .session--active {
    border-color: var(--accent);
    box-shadow: 0 0 0 1px var(--accent);
  }
  .session__id {
    font-family: var(--font-code);
    font-weight: 650;
    font-size: 0.92rem;
  }
  .session__meta {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    flex-wrap: wrap;
  }
  .session__template {
    font-size: var(--type-micro);
    color: var(--muted);
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
    max-width: 46ch;
    text-align: center;
    padding: 2rem;
    display: flex;
    flex-direction: column;
    gap: 1rem;
    align-items: center;
  }
  .empty p {
    color: var(--muted);
  }
  .view__head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding: 1rem 1.4rem;
    border-bottom: 1px solid var(--line);
    flex-wrap: wrap;
  }
  .view__id {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
  }
  .view__id h2 {
    margin: 0;
    font-family: var(--font-code);
    font-size: 1.1rem;
  }
  .view__controls {
    display: flex;
    gap: 0.4rem;
    flex-wrap: wrap;
  }
  .view__body {
    flex: 1;
    display: grid;
    grid-template-columns: 1fr 280px;
    min-height: 0;
    overflow: hidden;
  }
  .transcript {
    overflow-y: auto;
    padding: 1.4rem;
    display: flex;
    flex-direction: column;
    gap: 0.9rem;
  }
  .transcript__waiting {
    color: var(--muted);
    font-style: italic;
  }
  .meterrail {
    border-left: 1px solid var(--line);
    padding: 1.2rem 1rem;
    overflow-y: auto;
    background: var(--navbg);
  }

  /* ── bubbles ── */
  .bubble {
    border-radius: var(--radius);
    padding: 0.75rem 1rem;
    max-width: 78ch;
  }
  .bubble--user {
    align-self: flex-end;
    background: var(--color-surface-primary);
    color: var(--color-text-on-surface);
    border: 1px solid var(--color-surface-primary);
  }
  .bubble__role {
    font-family: var(--font-code);
    font-size: var(--type-micro);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--muted);
    margin-bottom: 0.35rem;
  }
  .bubble__role--user {
    color: var(--color-support);
  }
  .bubble__text {
    line-height: 1.55;
    white-space: pre-wrap;
    word-break: break-word;
  }

  .notice {
    border-radius: var(--radius);
    padding: 0.5rem 0.8rem;
    font-size: 0.9rem;
    border: 1px dashed var(--line);
    max-width: 78ch;
  }
  .notice--warn {
    border-color: var(--chip-warn-fg);
    color: var(--chip-warn-fg);
    background: var(--chip-warn-bg);
  }
  .notice--info {
    color: var(--muted);
  }

  .terminal {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    flex-wrap: wrap;
    padding: 0.6rem 0.9rem;
    border: 1px solid var(--line);
    border-radius: var(--radius);
    background: var(--chipbg);
    max-width: 78ch;
  }
  .terminal__text {
    font-weight: 600;
  }

  /* ── composer ── */
  .composer {
    display: flex;
    gap: 0.6rem;
    padding: 1rem 1.4rem;
    border-top: 1px solid var(--line);
  }
  .composer__input {
    flex: 1;
    padding: 0.7rem 0.9rem;
    border: 1px solid var(--panel-line);
    border-radius: var(--radius);
    font: inherit;
    background: var(--panel-bg);
    color: var(--fg);
  }
  .composer__input:focus {
    outline: 2px solid var(--accent);
    outline-offset: 1px;
  }

  /* ── buttons ── */
  .btn {
    font: inherit;
    font-size: 0.9rem;
    font-weight: 600;
    padding: 0.5rem 0.9rem;
    border-radius: var(--radius);
    border: 1px solid var(--panel-line);
    background: var(--panel-bg);
    color: var(--fg);
    cursor: pointer;
    transition:
      border-color 0.12s ease,
      background 0.12s ease;
  }
  .btn:hover {
    border-color: var(--accent);
  }
  .btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .btn--accent {
    background: var(--accent);
    color: var(--color-bone);
    border-color: var(--accent);
  }
  .btn--danger {
    border-color: var(--chip-warn-fg);
    color: var(--chip-warn-fg);
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
      border-left: none;
      border-top: 1px solid var(--line);
    }
  }
</style>
