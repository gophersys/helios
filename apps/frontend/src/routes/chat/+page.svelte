<script lang="ts">
  // The chat slice — the live UI that tests the whole agentgateway backend over REAL REST + SSE
  // (apps/agentgateway). Left rail: the project-scoped session list (GET /sessions) + a create
  // form picking the harness (claude | omp) and an opening prompt. Right: the chat view — the
  // conversation streamed live via the per-session SSE stream (GET /sessions/{id}/events),
  // rendering EVERY event-taxonomy kind distinctly (assistant text, foldable thinking, tool
  // start/update/end, permission round-trips, a live usage/cost meter), with the prompt / steer /
  // abort control verbs (POST .../control), stop/resume (POST .../stop|resume), and gap-free SSE
  // reconnect via Last-Event-ID. The gateway picks the live harness from its routing table; the
  // claude/omp choice is recorded as a label and surfaced here (the dev-serve routes both to its
  // deterministic fake harness — from the UI's side the HTTP/SSE is 100% real).
  import { onDestroy } from 'svelte';
  import { GatewayClient, GatewayError } from '$lib/gateway/client';
  import { resolveGatewayUrl } from '$lib/gateway/configuration';
  import { ChatSession } from '$lib/gateway/session.svelte';
  import type { AgentView, Harness } from '$lib/gateway/types';
  import UsageMeter from '$lib/chat/UsageMeter.svelte';
  import ToolCard from '$lib/chat/ToolCard.svelte';
  import PermissionCard from '$lib/chat/PermissionCard.svelte';
  import MessageBubble from '$lib/chat/MessageBubble.svelte';

  const client = new GatewayClient(resolveGatewayUrl());

  // ── session-list state ───────────────────────────────────────────────────────.
  let sessions = $state<AgentView[]>([]);
  let listError = $state<string | null>(null);
  let healthy = $state<boolean | null>(null);

  // ── create-form state ────────────────────────────────────────────────────────.
  let showCreate = $state(false);
  let createHarness = $state<Harness>('claude');
  let createPrompt = $state('Write a short note and say hello.');
  let creating = $state(false);
  let createError = $state<string | null>(null);

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

  async function submitCreate(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    creating = true;
    createError = null;
    try {
      // Create WITHOUT an opening prompt so the live session starts in `ready`; the opening
      // prompt is then driven through the control channel, so the chat surface observes the
      // full event stream from a clean state (and the user bubble renders).
      const created = await client.createSession({ harness: createHarness });
      await refreshList();
      showCreate = false;
      await attach(created.id, createHarness);
      // Drive the first turn through the control channel (the real prompt path).
      const opening = createPrompt.trim();
      if (opening && active) {
        await active.send(opening);
      }
    } catch (cause) {
      createError =
        cause instanceof GatewayError ? `${cause.kind}: ${cause.message}` : String(cause);
    } finally {
      creating = false;
    }
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
      onclick={() => (showCreate = true)}
    >
      ＋ New session
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
        <h2>Live agent chat</h2>
        <p>
          A working surface over the agent gateway — create a session, send a prompt, and watch the
          backend stream every event: assistant text, reasoning, tool calls, permissions, and a live
          token/cost meter.
        </p>
        <button class="btn btn--accent" onclick={() => (showCreate = true)}>＋ New session</button>
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

  <!-- ── create modal ─────────────────────────────────────────────────────── -->
  {#if showCreate}
    <div
      class="modal__scrim"
      role="presentation"
      onclick={() => (showCreate = false)}
      onkeydown={(event) => {
        if (event.key === 'Escape') showCreate = false;
      }}
    >
      <div
        class="modal panel"
        role="dialog"
        tabindex="-1"
        aria-modal="true"
        aria-label="Create session"
        data-testid="create-modal"
        onclick={(event) => event.stopPropagation()}
        onkeydown={(event) => event.stopPropagation()}
      >
        <h2>New session</h2>
        <form onsubmit={submitCreate}>
          <fieldset class="harness">
            <legend>Harness</legend>
            <div class="harness__group" role="radiogroup" aria-label="Harness">
              <button
                type="button"
                class="harness__opt"
                class:harness__opt--on={createHarness === 'claude'}
                role="radio"
                aria-checked={createHarness === 'claude'}
                data-testid="harness-claude"
                onclick={() => (createHarness = 'claude')}
              >
                <span class="harness__name">claude</span>
                <span class="harness__hint">Claude Code</span>
              </button>
              <button
                type="button"
                class="harness__opt"
                class:harness__opt--on={createHarness === 'omp'}
                role="radio"
                aria-checked={createHarness === 'omp'}
                data-testid="harness-omp"
                onclick={() => (createHarness = 'omp')}
              >
                <span class="harness__name">omp</span>
                <span class="harness__hint">OpenRouter / omp</span>
              </button>
            </div>
          </fieldset>

          <label class="field">
            <span class="field__label">Opening prompt</span>
            <textarea
              class="field__input"
              data-testid="create-prompt"
              rows="3"
              bind:value={createPrompt}
            ></textarea>
          </label>

          {#if createError}
            <p class="modal__error" data-testid="create-error">{createError}</p>
          {/if}

          <div class="modal__actions">
            <button type="button" class="btn" onclick={() => (showCreate = false)}>Cancel</button>
            <button
              type="submit"
              class="btn btn--accent"
              data-testid="create-submit"
              disabled={creating}
            >
              {creating ? 'Creating…' : 'Create & open'}
            </button>
          </div>
        </form>
      </div>
    </div>
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

  /* ── modal ── */
  .modal__scrim {
    position: fixed;
    inset: 0;
    background: color-mix(in srgb, var(--color-ink) 55%, transparent);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 1.5rem;
    z-index: 10;
  }
  .modal {
    width: min(480px, 100%);
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }
  .modal h2 {
    margin: 0;
  }
  .modal form {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }
  .harness {
    border: none;
    margin: 0;
    padding: 0;
  }
  .harness legend {
    font-size: var(--type-micro);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--muted);
    margin-bottom: 0.4rem;
    padding: 0;
  }
  .harness__group {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.6rem;
  }
  .harness__opt {
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
    border: 1px solid var(--panel-line);
    border-radius: var(--radius);
    padding: 0.6rem 0.8rem;
    cursor: pointer;
    background: var(--panel-bg);
    color: inherit;
    font: inherit;
    text-align: left;
  }
  .harness__opt--on {
    border-color: var(--accent);
    box-shadow: 0 0 0 1px var(--accent);
  }
  .harness__name {
    font-family: var(--font-code);
    font-weight: 650;
  }
  .harness__hint {
    font-size: var(--type-micro);
    color: var(--muted);
  }
  .field {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
  }
  .field__label {
    font-size: var(--type-micro);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--muted);
  }
  .field__input {
    font: inherit;
    padding: 0.6rem 0.8rem;
    border: 1px solid var(--panel-line);
    border-radius: var(--radius);
    background: var(--panel-bg);
    color: var(--fg);
    resize: vertical;
  }
  .modal__error {
    color: var(--chip-warn-fg);
    font-size: 0.88rem;
    margin: 0;
  }
  .modal__actions {
    display: flex;
    justify-content: flex-end;
    gap: 0.6rem;
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
