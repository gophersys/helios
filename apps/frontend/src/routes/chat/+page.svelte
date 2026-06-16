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
  import { Button, Input, Message, CommandPalette } from '@eden/primitives';
  import type { CommandPaletteGroup } from '@eden/primitives';
  import { GatewayClient, GatewayError } from '$lib/gateway/client';
  import { resolveGatewayUrl } from '$lib/gateway/configuration';
  import { ChatSession } from '$lib/gateway/session.svelte';
  import type { AgentView, Harness, ProductConfig, ProductHarness } from '$lib/gateway/types';
  import { edenTheme } from '$lib/theme/edenTheme';
  import ChatMessage from '$lib/chat/ChatMessage.svelte';
  import ChatTool from '$lib/chat/ChatTool.svelte';
  import ChatPermission from '$lib/chat/ChatPermission.svelte';
  import ChatStatusBar from '$lib/chat/ChatStatusBar.svelte';
  import ChatContextBar from '$lib/chat/ChatContextBar.svelte';
  import RightPanel from '$lib/chat/RightPanel.svelte';
  import TopBar from '$lib/chat/TopBar.svelte';
  import SettingsPanel from '$lib/chat/SettingsPanel.svelte';
  import UsageDock from '$lib/chat/UsageDock.svelte';
  import Modal from '$lib/chat/Modal.svelte';
  import AgentConfigView from '$lib/chat/AgentConfigView.svelte';
  import CreateProjectFlow from '$lib/chat/wizard/CreateProjectFlow.svelte';
  import { agentTypeFor } from '$lib/workspace/agentWorkspace';

  const client = new GatewayClient(resolveGatewayUrl());
  const theme = edenTheme;

  // ── session-list state ───────────────────────────────────────────────────────.
  let sessions = $state<AgentView[]>([]);
  let listError = $state<string | null>(null);
  let healthy = $state<boolean | null>(null);

  // ── product-wizard state ─────────────────────────────────────────────────────.
  let showWizard = $state(false);
  // ── ⌘K command palette + settings + overlays ─────────────────────────────────.
  let paletteOpen = $state(false);
  let settingsOpen = $state(false);
  let configOpen = $state(false);

  // ── collapsible columns: the rail + the right panel fold away (top-bar toggles) so the chat can
  //    take the full width — "the widest amount of chat area". ──.
  let railOpen = $state(true);
  let panelOpen = $state(true);

  /** Map the product harness onto the chat label set (the SSE/control seam is harness-agnostic;
   *  `codex` folds to a claude-tone label for the chrome only — the full product still rides). */
  function chatHarness(harness: ProductHarness): Harness {
    return harness === 'omp' ? 'omp' : 'claude';
  }

  /** "Build it" → create the session carrying the proposed ProductConfig, then open the chat view
   *  streaming the real agent. Created WITHOUT an opening prompt so it starts in `ready`; the first
   *  turn is then driven through the control channel so the user bubble renders from a clean state. */
  async function launchProduct(payload: {
    product: ProductConfig;
    harness: ProductHarness;
    prompt: string;
  }): Promise<void> {
    const harness = chatHarness(payload.harness);
    const created = await client.createSession({ harness, product: payload.product });
    // Persist the Project (the dashboard reads these) linked to its build session. A persistence
    // fault must NOT block the build — the session is already live — so we log and continue.
    try {
      await client.createProject({
        product: payload.product,
        name: payload.product.productName,
        idea: payload.prompt,
        sessionId: created.id,
      });
    } catch (cause) {
      console.warn('eden: project persistence failed (build continues)', cause);
    }
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

  /** The command model the ⌘K palette renders: an Actions group (gated on whether a session is
   *  open) + a Sessions group to jump to any session. Derived, so it tracks the live session list. */
  const commandGroups = $derived<CommandPaletteGroup[]>([
    {
      value: 'actions',
      heading: 'Actions',
      items: [
        { value: 'new-product', label: 'New project…', keywords: ['create', 'start', 'session', 'product'] },
        { value: 'settings', label: 'Settings', keywords: ['preferences', 'theme', 'dark', 'density'] },
        ...(active
          ? [
              { value: 'agent-config', label: 'Agent configuration', keywords: ['config', 'model', 'tools', 'details'] },
              { value: 'stop', label: 'Stop session', keywords: ['end', 'kill'] },
              { value: 'steer', label: 'Steer the agent', keywords: ['interject', 'redirect'] },
              { value: 'abort', label: 'Abort the current turn', keywords: ['cancel'] },
              { value: 'resume', label: 'Resume session', keywords: ['reconnect'] },
              {
                value: 'request-tool',
                label: 'Request an out-of-grant tool (demo)',
                keywords: ['permission', 'gate'],
              },
            ]
          : []),
      ],
    },
    {
      value: 'sessions',
      heading: 'Sessions',
      items: sessions.map((agent) => ({
        value: `session:${agent.id}`,
        label: agent.id,
        keywords: [agent.template, agent.status],
      })),
    },
  ]);

  /** Dispatch a selected ⌘K command. Session jumps carry the `session:<id>` value. */
  function runCommand(value: string): void {
    paletteOpen = false;
    if (value === 'new-product') {
      showWizard = true;
      return;
    }
    if (value === 'settings') {
      settingsOpen = true;
      return;
    }
    if (value === 'agent-config') {
      configOpen = true;
      return;
    }
    if (value.startsWith('session:')) {
      const id = value.slice('session:'.length);
      const agent = sessions.find((s) => s.id === id);
      if (agent) openSession(agent);
      return;
    }
    if (value === 'stop') void stopSession();
    else if (value === 'steer') void steer();
    else if (value === 'abort') void abort();
    else if (value === 'resume') void resumeSession();
    else if (value === 'request-tool') void requestOutOfGrantTool();
  }

  /** ⌘K / Ctrl-K toggles the palette from anywhere in the workspace. */
  function onGlobalKey(event: KeyboardEvent): void {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      paletteOpen = !paletteOpen;
    }
  }
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

  // Deep-link from the Projects dashboard: ?new=1 opens the create flow; ?session=<id> attaches to
  // that project's session. Runs once (the guard keeps the non-reactive read from re-firing).
  let deepLinkHandled = false;
  $effect(() => {
    if (deepLinkHandled || typeof window === 'undefined') return;
    deepLinkHandled = true;
    const params = new URLSearchParams(window.location.search);
    if (params.get('new') === '1') showWizard = true;
    const sessionId = params.get('session');
    if (sessionId) void attach(sessionId, 'claude');
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

  /** The timeline-rail node glyph for a transcript entry — the marker on the connecting line that
   *  makes the conversation read as one threaded sequence (user → the agent's reasoning, tools, and
   *  result, all on the rail). */
  function railGlyph(role: string): string {
    if (role === 'user') return '▍';
    if (role === 'assistant') return '✦';
    if (role === 'tool') return '⎿';
    if (role === 'permission') return '?';
    if (role === 'terminal') return '■';
    return '·';
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

<svelte:window onkeydown={onGlobalKey} />
<svelte:head>
  <title>Eden — chat</title>
</svelte:head>

<div class="workspace-root">
  <TopBar
    {active}
    agentType={activeType}
    {railOpen}
    panelOpen={Boolean(active) && panelOpen}
    showPanelToggle={Boolean(active)}
    onToggleRail={() => (railOpen = !railOpen)}
    onTogglePanel={() => (panelOpen = !panelOpen)}
    onPalette={() => (paletteOpen = true)}
    onSettings={() => (settingsOpen = true)}
    onConfig={active ? () => (configOpen = true) : undefined}
    {theme}
  />

  <div
    class="chat"
    data-testid="chat-app"
    style="grid-template-columns: {railOpen
      ? 'minmax(240px, 280px)'
      : '0'} minmax(0, 1fr) {active && panelOpen ? 'clamp(300px, 26vw, 380px)' : '0'};"
  >
  <!-- ── left rail: sessions (collapsible) ─────────────────────────────────── -->
  {#if railOpen}
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
      <Button variant="primary" {theme} onclick={() => (showWizard = true)}>＋ New project</Button>
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
  {:else}
    <div class="collapsed-col" aria-hidden="true"></div>
  {/if}

  <!-- ── main: chat view ──────────────────────────────────────────────────── -->
  <main class="view">
    {#if !active}
      <div class="empty" data-testid="empty-state">
        <h2>Build a project with Eden</h2>
        <p>
          Every project is something Eden builds through its 10-phase SDLC. Start one — say what
          you're building in a sentence, watch Eden scope it, then watch the agent stream every event
          live: reasoning, tool calls, permission gates, and a token/cost meter.
        </p>
        <div class="empty__cta">
          <Button variant="primary" {theme} onclick={() => (showWizard = true)}
            >＋ New project</Button
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
              <li class="turn" data-role={entry.role} data-testid="turn">
                <span class="turn__rail" aria-hidden="true">
                  <span class="turn__node" data-role={entry.role}>{railGlyph(entry.role)}</span>
                </span>
                <div class="turn__main">
                  {#if entry.role === 'user'}
                    <div class="turn--user" data-testid="user-message">
                      <Message role="user" {theme}>{entry.text}</Message>
                    </div>
                  {:else if entry.role === 'assistant'}
                    <ChatMessage
                      text={entry.text}
                      thinking={entry.thinking}
                      streaming={entry.streaming}
                      {theme}
                    />
                  {:else if entry.role === 'tool'}
                    <ChatTool tool={entry.tool} {theme} />
                  {:else if entry.role === 'permission'}
                    <ChatPermission
                      permission={entry.permission}
                      {theme}
                      onresolve={(requestId, verdict, scope) =>
                        active?.resolve(requestId, verdict, scope)}
                    />
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
                </div>
              </li>
            {/each}
          </ul>
          {#if active.entries.length === 0}
            <p class="transcript__waiting" data-testid="transcript-waiting">
              Waiting for the first events…
            </p>
          {/if}
        </div>
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

  <!-- ── right panel: the agent-type-aware workspace (collapsible) ─────────────── -->
  {#if active && activeType && panelOpen}
    <RightPanel session={active} agentType={activeType} {theme} />
  {:else}
    <div class="collapsed-col" aria-hidden="true"></div>
  {/if}

    <!-- ── product wizard (the create flow) ───────────────────────────────────── -->
    {#if showWizard}
      <CreateProjectFlow
        propose={(prompt) => client.propose(prompt)}
        onlaunch={launchProduct}
        oncancel={() => (showWizard = false)}
      />
    {/if}
  </div>
</div>

<!-- ── ⌘K command palette + settings (overlay the whole workspace) ───────────── -->
<CommandPalette
  groups={commandGroups}
  bind:open={paletteOpen}
  onSelect={runCommand}
  {theme}
  label="Eden command palette"
  placeholder="Type a command or search sessions…"
/>
<SettingsPanel bind:open={settingsOpen} {theme} />

<!-- ── the agent-config detail view in the global modal shell ─────────────────── -->
{#if active && activeType}
  {@const cfgSession = active}
  {@const cfgType = activeType}
  <Modal bind:open={configOpen} title="Agent configuration" size="md" {theme}>
    {#snippet children()}
      <AgentConfigView session={cfgSession} agentType={cfgType} {theme} />
    {/snippet}
  </Modal>
{/if}

<!-- ── the concise usage/cost dock, pinned bottom-right ──────────────────────── -->
{#if active}
  <UsageDock meter={active.meter} {theme} />
{/if}

<style>
  .workspace-root {
    display: flex;
    flex-direction: column;
    height: 100vh;
    overflow: hidden;
  }
  /* The columns are set inline (rail · conversation · panel), each foldable to 0 via the top-bar
     toggles — the rail/panel collapse to a 0-width empty column so the chat takes the full width. */
  .chat {
    display: grid;
    flex: 1;
    min-block-size: 0;
    overflow: hidden;
  }
  .collapsed-col {
    inline-size: 0;
    overflow: hidden;
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
    /* Fill the grid cell (the workspace column height), NOT the whole viewport — the top bar +
       the status/context bars take their own rows, and .view__body flexes + scrolls so the
       composer stays pinned at the bottom of the visible area. */
    min-block-size: 0;
    overflow: hidden;
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
    display: flex;
    min-height: 0;
    overflow: hidden;
  }
  .transcript {
    flex: 1;
    min-inline-size: 0;
    overflow-y: auto;
    padding: var(--space-6, 24px);
    /* keep the prose readable + room for the bottom-right usage dock */
    max-inline-size: 100%;
  }
  .transcript :global(.turns) {
    max-inline-size: 56rem;
    margin-inline: auto;
  }
  .turns {
    list-style: none;
    margin: 0;
    padding: 0;
  }
  /* Each turn is laid on a CONNECTED timeline: a rail column (the continuous vertical line + a node
     marker) and the content. The line runs through the rail and into the inter-turn gaps so the
     whole conversation reads as one thread; the node's filled circle sits on the line. */
  .turn {
    display: grid;
    grid-template-columns: var(--space-6, 24px) minmax(0, 1fr);
    gap: var(--space-3, 12px);
    padding-block: var(--space-3, 12px);
  }
  .turn__rail {
    position: relative;
    display: flex;
    align-items: flex-start;
    justify-content: center;
  }
  .turn__rail::before {
    content: '';
    position: absolute;
    inset-block: calc(-1 * var(--space-3, 12px));
    inset-inline-start: 50%;
    inline-size: 1px;
    background: var(--eden-app-line);
    transform: translateX(-50%);
  }
  /* the first turn's line should not run above the first node, the last's not below — masked by the
     transcript's own padding + overflow; the node circle covers the line where the marker sits. */
  .turn:first-child .turn__rail::before {
    inset-block-start: var(--space-2, 8px);
  }
  .turn:last-child .turn__rail::before {
    inset-block-end: calc(100% - var(--space-5, 20px));
  }
  .turn__node {
    position: relative;
    z-index: 1;
    inline-size: var(--space-5, 20px);
    block-size: var(--space-5, 20px);
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--eden-app-bg);
    border-radius: 50%;
    font-family: var(--font-code);
    font-size: var(--font-size-caption, 12px);
    color: var(--eden-app-muted);
  }
  .turn__node[data-role='assistant'] {
    color: var(--eden-app-accent);
  }
  .turn__node[data-role='user'] {
    color: var(--eden-app-fg);
  }
  .turn__node[data-role='tool'] {
    color: color-mix(in oklab, var(--eden-app-muted) 80%, var(--eden-app-bg));
    font-size: var(--font-size-label, 13px);
  }
  .turn__main {
    min-inline-size: 0;
    padding-block-start: 1px;
  }
  .turn--user :global(.eden-message) {
    max-inline-size: 70ch;
  }
  .transcript__waiting {
    color: var(--eden-app-muted);
    font-style: italic;
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
    .rail {
      display: none;
    }
  }
</style>
