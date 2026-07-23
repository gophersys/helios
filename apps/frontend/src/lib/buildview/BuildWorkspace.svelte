<script lang="ts">
  // BuildWorkspace — THE Build view (doc 17 §5): the chat/conversation surface that used to be the
  // parallel `/chat` app, now a REUSABLE view mounted INSIDE the one (app) shell. It hosts the
  // session rail, the transcript timeline, the composer, the agent-type-aware RightPanel, the live
  // status/context bars, the docked usage meter, the create-project wizard, the per-session config
  // modal, and (via `settings-open`) the ONE Settings surface. It talks to the agentgateway backend over REAL REST +
  // SSE (a "session" IS a PRODUCT Eden builds via its 10-phase SDLC), streaming the agent event
  // taxonomy through @eden/primitives (Message, StreamingText, ThinkingBlock, ToolCall, UsageMeter,
  // and the interactive PermissionRequest gate).
  //
  // Two things that used to be LOCAL /chat-shell chrome now lift OUT into the app shell: the ⌘K
  // palette (mounted ONCE in the shell; this view REGISTERS its session commands on the shared
  // paletteBus) and — conceptually — the gateway-health chip (kept in the rail here where the e2e
  // asserts it, and mirrored on the shell header). The rail toggle, ⌘K affordance, and settings mount
  // stay wired here through the TopBar so the Build view is self-contained wherever it is mounted:
  // `/chat`, `/projects/[id]/build`, and `/sessions/[id]` all render this one component.
  import { onDestroy, onMount } from 'svelte';
  import { Button, Input, Message, CommandPalette } from '@eden/primitives';
  import type { CommandPaletteGroup } from '@eden/primitives';
  import { GatewayClient, GatewayError } from '$lib/gateway/client';
  import { resolveGatewayUrl } from '$lib/gateway/configuration';
  import { ChatSession } from '$lib/gateway/session.svelte';
  import type { AgentView, Harness, ProductConfig, ProductHarness } from '$lib/gateway/types';
  import { edenLightTheme, edenDarkTheme } from '$lib/theme/edenTheme';
  import { themePreference } from '$lib/theme/themePreference.svelte';
  import ChatMessage from '$lib/chat/ChatMessage.svelte';
  import ChatTool from '$lib/chat/ChatTool.svelte';
  import ChatPermission from '$lib/chat/ChatPermission.svelte';
  import ChatStatusBar from '$lib/chat/ChatStatusBar.svelte';
  import ChatContextBar from '$lib/chat/ChatContextBar.svelte';
  import RightPanel from '$lib/chat/RightPanel.svelte';
  import TopBar from '$lib/chat/TopBar.svelte';
  import SettingsSurface from '$lib/settings/SettingsSurface.svelte';
  import UsageDock from '$lib/chat/UsageDock.svelte';
  import Modal from '$lib/chat/Modal.svelte';
  import AgentConfigView from '$lib/chat/AgentConfigView.svelte';
  import CreateProjectFlow from '$lib/chat/wizard/CreateProjectFlow.svelte';
  import { agentTypeFor } from '$lib/workspace/agentWorkspace';
  import { usePaletteBus, type PaletteProvider } from '$lib/buildview/paletteBus.svelte';
  import { currentUser } from '$lib/platform/currentUser.svelte';

  // ── deep-link intent (the ?new / ?session / ?harness contract, resolved by the host route) ──
  //    A host route (/chat, /projects/[id]/build, /sessions/[id]) resolves the URL into this intent
  //    and passes it in, so this view is route-agnostic. `onLaunched` is the saga handoff seam: after
  //    a product is created + persisted, the host decides where to route (the project loading route).
  let {
    deepLink = {},
    onLaunched,
  }: {
    deepLink?: { new?: boolean; sessionId?: string | null; harness?: ProductHarness | null };
    onLaunched?: (result: { projectId: string | null; sessionId: string }) => void;
  } = $props();

  const client = new GatewayClient(resolveGatewayUrl());
  const gatewayUrl = resolveGatewayUrl();
  // The Theme OBJECT tracks the resolved colour mode so a component derived from it (the Settings sheet)
  // flips WITH the app when Appearance switches (doc 17 §3). Light-first (the founder's paper anchor).
  const theme = $derived(themePreference.resolvedMode === 'dark' ? edenDarkTheme : edenLightTheme);
  const palette = usePaletteBus();

  // ── session-list state ───────────────────────────────────────────────────────.
  let sessions = $state<AgentView[]>([]);
  let listError = $state<string | null>(null);
  let healthy = $state<boolean | null>(null);

  // ── product-wizard state ─────────────────────────────────────────────────────.
  let showWizard = $state(false);
  // ── settings + per-session config overlays (the palette lives in the shell now) ─────────────.
  // The Build top bar's `settings-open` opens the ONE Settings surface on Appearance (colour mode —
  // the setting the Build view's affordance historically surfaced). The per-session agent-config
  // detail (configOpen) is a distinct overlay (this session's model/grants), left as-is.
  let settingsOpen = $state(false);
  let settingsSection = $state<string>('appearance');
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
   *  streaming the real agent. The GATEWAY drives the SINGLE opening turn server-side: it folds the
   *  product preamble (which already carries the user's idea) into the first prompt at create. The
   *  client therefore only RECORDS the user's spark as a local bubble — issuing a second prompt here
   *  would be an illegal turn (the session has already left `ready`) and 409. One home: the gateway
   *  drives the opening turn, the client mirrors it. */
  async function launchProduct(payload: {
    product: ProductConfig;
    harness: ProductHarness;
    prompt: string;
  }): Promise<void> {
    const harness = chatHarness(payload.harness);
    const created = await client.createSession({ harness, product: payload.product });
    // Persist the Project (the dashboard reads these) linked to its build session. A persistence
    // fault must NOT block the build — the session is already live — so we log and continue.
    let persistedId: string | null = null;
    try {
      const persisted = await client.createProject({
        product: payload.product,
        name: payload.product.productName,
        idea: payload.prompt,
        sessionId: created.id,
      });
      persistedId = persisted?.id ?? null;
    } catch (cause) {
      console.warn('eden: project persistence failed (build continues)', cause);
    }
    await refreshList();
    showWizard = false;
    // HANDOFF (doc 17 §5, chat/+page.svelte:78 intent now wired): once the project persists, hand
    // OFF to the host, which routes into the project's loading route (/projects/<id>) so the saga
    // lifecycle drives. When no host handoff is provided (or persistence failed), attach inline —
    // the pre-saga demo path the create-product e2e still drives on `/chat`.
    if (onLaunched && persistedId) {
      onLaunched({ projectId: persistedId, sessionId: created.id });
      return;
    }
    await attach(created.id, harness);
    const opening = payload.prompt.trim();
    if (opening && active) active.recordOpeningPrompt(opening);
  }

  // ── open-session state ───────────────────────────────────────────────────────.
  let active = $state<ChatSession | null>(null);
  let activeHarness = $state<Harness | null>(null);

  // The active session's AGENT TYPE drives the right panel's widget stack. Derived from the
  // session's template (carried on the session-list record); defaults to implementer.
  const activeType = $derived(
    active
      ? agentTypeFor(sessions.find((s) => s.id === active?.id)?.template, active.harness)
      : null,
  );

  /** The command model the ⌘K palette renders for THIS build (an Actions group gated on whether a
   *  session is open + a Sessions group to jump to any session). Registered on the shared bus so the
   *  ONE shell-mounted palette carries it alongside the app-navigation commands. */
  const commandGroups = $derived<CommandPaletteGroup[]>([
    {
      value: 'build-actions',
      heading: 'Build',
      items: [
        {
          value: 'new-product',
          label: 'New project…',
          keywords: ['create', 'start', 'session', 'product'],
        },
        {
          value: 'build-settings',
          label: 'Settings',
          keywords: ['preferences', 'theme', 'dark', 'density'],
        },
        ...(active
          ? [
              {
                value: 'agent-config',
                label: 'Agent configuration',
                keywords: ['config', 'model', 'tools', 'details'],
              },
              { value: 'stop', label: 'Stop session', keywords: ['end', 'kill'] },
              // The control items DERIVE disabled from the same allowed-set as the inline buttons —
              // one source of truth, two render sites — so the palette can never dispatch an illegal
              // control either.
              {
                value: 'steer',
                label: 'Steer the agent',
                keywords: ['interject', 'redirect'],
                disabled: !active.allowed.has('steer'),
              },
              {
                value: 'abort',
                label: 'Abort the current turn',
                keywords: ['cancel'],
                disabled: !active.allowed.has('abort'),
              },
              {
                value: 'resume',
                label: 'Resume session',
                keywords: ['reconnect'],
                disabled: !active.canResume,
              },
              {
                value: 'request-tool',
                label: 'Request an out-of-grant tool (demo)',
                keywords: ['permission', 'gate'],
                disabled: !active.allowed.has('prompt'),
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

  /** Dispatch a selected ⌘K command owned by this build. Returns true if handled (so the shell's
   *  bus knows not to fall through to an app-navigation command). Session jumps carry `session:<id>`. */
  function runCommand(value: string): boolean {
    if (value === 'new-product') {
      showWizard = true;
      return true;
    }
    if (value === 'build-settings') {
      settingsSection = 'appearance';
      settingsOpen = true;
      return true;
    }
    if (value === 'agent-config') {
      configOpen = true;
      return true;
    }
    if (value.startsWith('session:')) {
      const id = value.slice('session:'.length);
      const agent = sessions.find((s) => s.id === id);
      if (agent) openSession(agent);
      return true;
    }
    // Defense-in-depth: even though the disabled palette items above are not selectable, guard the
    // dispatch against the live allowed-set so a TOCTOU (state changed between render and select)
    // can never fire an illegal control. Stop is always allowed (idempotent).
    if (value === 'stop') {
      void stopSession();
      return true;
    }
    if (value === 'steer' && active?.allowed.has('steer')) {
      void steer();
      return true;
    }
    if (value === 'abort' && active?.allowed.has('abort')) {
      void abort();
      return true;
    }
    if (value === 'resume' && active?.canResume) {
      void resumeSession();
      return true;
    }
    if (value === 'request-tool' && active?.allowed.has('prompt')) {
      void requestOutOfGrantTool();
      return true;
    }
    return false;
  }

  // Register this build's commands on the shared palette bus while mounted; clear on destroy so the
  // shell palette reverts to the app-navigation commands alone. When rendered OUTSIDE the shell (no
  // bus), fall back to a local palette (below) so the Build view still works standalone.
  const provider: PaletteProvider = { groups: () => commandGroups, run: runCommand };
  onMount(() => palette?.register(provider));
  onDestroy(() => palette?.clear(provider));

  // ── fallback local palette (only when there is no shell bus — never in the (app) shell) ──
  let localPaletteOpen = $state(false);
  function openPalette(): void {
    if (palette) palette.show();
    else localPaletteOpen = true;
  }
  /** ⌘K / Ctrl-K toggles the palette. When mounted in the shell the layout owns the global key; this
   *  local handler only fires for the standalone (no-bus) fallback. */
  function onGlobalKey(event: KeyboardEvent): void {
    if (palette) return;
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      localPaletteOpen = !localPaletteOpen;
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

  // Deep-link intent, resolved by the host route: ?new=1 opens the create flow; ?session=<id>
  // attaches to that project's session; ?harness=<h> labels it. Runs once per mount.
  let deepLinkHandled = false;
  $effect(() => {
    if (deepLinkHandled) return;
    deepLinkHandled = true;
    if (deepLink.new) showWizard = true;
    if (deepLink.sessionId) {
      void attach(deepLink.sessionId, deepLink.harness ? chatHarness(deepLink.harness) : 'claude');
    }
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
    // Prompt is legal only in ready/awaiting-input — the allowed-set guards both the Send button and
    // the Enter key, so the composer can never fire an illegal Prompt (which would 409).
    if (!text || !active || !active.allowed.has('prompt')) return;
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

<div class="workspace-root">
  <TopBar
    {active}
    agentType={activeType}
    {railOpen}
    panelOpen={Boolean(active) && panelOpen}
    showPanelToggle={Boolean(active)}
    onToggleRail={() => (railOpen = !railOpen)}
    onTogglePanel={() => (panelOpen = !panelOpen)}
    onPalette={openPalette}
    onSettings={() => {
      settingsSection = 'appearance';
      settingsOpen = true;
    }}
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
        <!-- W5 (doc 17 §2 dedup): the shell rail already labels "Sessions" (the nav item), so this rail's
         own "Sessions" title + "Eden · agent gateway" eyebrow were a duplicate header. Removed; the
         rail now leads with the live gateway-health chip + the New-project action + the session list.
         The gateway-health chip (the e2e-asserted `gateway-health` / 'gateway up' — DO NOT weaken) is
         kept where it still reads at a glance as the rail's live status. -->
        <header class="rail__head">
          <span
            class="chip chip--{healthy === null ? 'muted' : healthy ? 'ok' : 'warn'}"
            data-testid="gateway-health"
          >
            {healthy === null ? '…' : healthy ? 'gateway up' : 'gateway down'}
          </span>
        </header>

        <div class="rail__new" data-testid="new-session">
          <Button variant="primary" {theme} onclick={() => (showWizard = true)}
            >＋ New project</Button
          >
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
            you're building in a sentence, watch Eden scope it, then watch the agent stream every
            event live: reasoning, tool calls, permission gates, and a token/cost meter.
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
          <!-- Every control DERIVES its enablement from the session's projected allowed-set (the one
             source of truth, the agentsession (state × command) matrix) — never a hand-guessed
             condition. A control absent from the set is disabled, so an illegal action (e.g. steer in
             awaiting-permission) is impossible to trigger. -->
          <div class="view__controls">
            <span class="control" data-testid="request-tool">
              <Button
                variant="secondary"
                {theme}
                disabled={!active.allowed.has('prompt')}
                onclick={requestOutOfGrantTool}>request tool</Button
              >
            </span>
            <span class="control" data-testid="steer">
              <Button
                variant="ghost"
                {theme}
                disabled={!active.allowed.has('steer')}
                onclick={steer}>steer</Button
              >
            </span>
            <span class="control" data-testid="abort">
              <Button
                variant="ghost"
                {theme}
                disabled={!active.allowed.has('abort')}
                onclick={abort}>abort</Button
              >
            </span>
            <span class="control" data-testid="resume">
              <Button variant="ghost" {theme} disabled={!active.canResume} onclick={resumeSession}
                >resume</Button
              >
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
                      <div class="notice notice--{entry.tone}" data-testid="notice">
                        {entry.text}
                      </div>
                    {:else if entry.role === 'terminal'}
                      <div
                        class="terminal"
                        data-testid="terminal-banner"
                        data-outcome={entry.outcome}
                      >
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
            <Button
              variant="primary"
              {theme}
              disabled={!active.allowed.has('prompt')}
              onclick={sendComposer}>Send</Button
            >
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
        {theme}
      />
    {/if}
  </div>
</div>

<!-- ── ⌘K palette: only the STANDALONE (no-shell) fallback renders one here; in the (app) shell the
     ONE palette lives in the layout and this build registered its commands on the bus. ────────── -->
{#if !palette}
  <CommandPalette
    groups={commandGroups}
    bind:open={localPaletteOpen}
    onSelect={(v) => {
      localPaletteOpen = false;
      runCommand(v);
    }}
    {theme}
    label="Eden command palette"
    placeholder="Type a command or search sessions…"
  />
{/if}

<SettingsSurface
  bind:open={settingsOpen}
  bind:section={settingsSection}
  {theme}
  loadConfigs={() => client.listAgentConfigs()}
  saveConfig={(agentType, body) => client.saveAgentConfig(agentType, body)}
  gatewayHealthy={healthy}
  platformSignedIn={currentUser.signedIn}
  gatewayLabel={gatewayUrl}
  platformLabel="/platform"
/>

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
    /* Fill the shell content cell (the app shell gives us a full-height column). Standalone hosts
       (/chat wrapped by the app group) also give a 100%-height cell, so 100% here — not 100vh —
       keeps the Build view inside its host without a double-scroll. */
    height: 100%;
    min-block-size: 0;
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

  /* ── rail ── the shadcn sidebar: a --surface-muted tone against the --border divider. */
  .rail {
    background: var(--surface-muted, var(--eden-app-rail-bg));
    border-inline-end: 1px solid var(--border, var(--eden-app-line));
    padding: var(--space-5, 20px) var(--space-4, 16px);
    display: flex;
    flex-direction: column;
    gap: var(--space-3, 12px);
    overflow-y: auto;
  }
  .rail__head {
    display: flex;
    align-items: center;
  }
  .rail__new {
    display: flex;
  }
  /* The rail's primary action gets the shadcn solid-button geometry (overriding the pill radius). */
  .rail__new :global(button) {
    inline-size: 100%;
    border-radius: var(--radius-md);
    background: var(--primary);
    border-color: var(--primary);
    color: var(--primary-foreground);
    font-weight: 600;
    box-shadow: var(--shadow-sm);
  }
  .rail__new :global(button:hover:not(:disabled)) {
    filter: brightness(1.08);
    box-shadow: var(--shadow-md);
  }
  .rail__error {
    color: var(--destructive);
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
    color: var(--muted-foreground);
    font-size: var(--font-size-label, 13px);
    padding: var(--space-2, 8px) 0;
  }
  /* A session row is a shadcn selectable card — a --card fill, 1px --border, --radius-md corners;
     hover raises the --border-strong edge, the active row rides a --ring 1px ring + tint. */
  .session {
    inline-size: 100%;
    text-align: start;
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    padding: var(--space-3, 12px);
    cursor: pointer;
    display: flex;
    flex-direction: column;
    gap: var(--space-1, 4px);
    transition:
      border-color var(--duration-short-3, 150ms) var(--ease-standard, ease),
      background var(--duration-short-3, 150ms) var(--ease-standard, ease),
      transform var(--duration-short-3, 150ms) var(--ease-standard, ease);
    color: inherit;
    font: inherit;
  }
  .session:hover {
    border-color: var(--border-strong);
    background: var(--accent-surface);
    transform: translateY(-1px);
  }
  .session--active {
    border-color: var(--primary);
    background: var(--accent-surface);
    box-shadow: 0 0 0 1px var(--ring);
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
    background: var(--muted-foreground);
  }
  .session__dot[data-state='working'] {
    background: var(--primary);
    animation: session-dot-pulse 1.1s ease-in-out infinite;
  }
  .session__dot[data-state='ready'] {
    background: var(--color-info);
  }
  .session__dot[data-state='done'] {
    background: color-mix(in oklab, var(--color-info) 60%, var(--muted-foreground));
  }
  .session__dot[data-state='error'] {
    background: var(--destructive);
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
    color: var(--muted-foreground);
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
    color: var(--muted-foreground);
  }
  .empty__cta {
    display: flex;
  }
  /* The empty-state primary CTA gets the shadcn solid-button geometry. */
  .empty__cta :global(.eden-button) {
    border-radius: var(--radius-md);
    background: var(--primary);
    border-color: var(--primary);
    color: var(--primary-foreground);
    font-weight: 600;
    box-shadow: var(--shadow-sm);
  }
  .empty__cta :global(.eden-button:hover:not(:disabled)) {
    filter: brightness(1.08);
    box-shadow: var(--shadow-md);
  }
  .view__head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-4, 16px);
    padding: var(--space-4, 16px) var(--space-6, 24px);
    border-block-end: 1px solid var(--border, var(--eden-app-line));
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
    background: var(--border, var(--eden-app-line));
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
    background: var(--background, var(--eden-app-bg));
    border-radius: 50%;
    font-family: var(--font-code);
    font-size: var(--font-size-caption, 12px);
    color: var(--muted-foreground);
  }
  .turn__node[data-role='assistant'] {
    color: var(--primary);
  }
  .turn__node[data-role='user'] {
    color: var(--foreground, var(--eden-app-fg));
  }
  .turn__node[data-role='tool'] {
    color: color-mix(in oklab, var(--muted-foreground) 80%, var(--background));
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
    color: var(--muted-foreground);
    font-style: italic;
  }

  .notice {
    border-radius: var(--radius-md, 8px);
    padding: var(--space-2, 8px) var(--space-3, 12px);
    font-size: var(--font-size-label, 13px);
    border: 1px dashed var(--border, var(--eden-app-line));
    max-width: 78ch;
  }
  .notice--warn {
    border-color: var(--destructive);
    color: var(--destructive);
    background: var(--destructive-surface);
  }
  .notice--info {
    color: var(--muted-foreground);
  }

  .terminal {
    display: flex;
    align-items: center;
    gap: var(--space-3, 12px);
    flex-wrap: wrap;
    padding: var(--space-3, 12px) var(--space-4, 16px);
    border: 1px solid var(--border, var(--eden-app-line));
    border-radius: var(--radius-md, 8px);
    background: var(--card, var(--eden-app-panel-bg));
    max-width: 78ch;
  }
  .terminal__text {
    font-weight: 600;
  }

  /* ── composer ── the shadcn input-row footer: a --border top divider, a --card ground, and the
     shadcn input geometry (a 1px --input edge, --radius-sm corners, a --ring focus halo). */
  .composer {
    display: flex;
    align-items: center;
    gap: var(--space-3, 12px);
    padding: var(--space-4, 16px) var(--space-6, 24px);
    border-block-start: 1px solid var(--border, var(--eden-app-line));
    background: var(--card);
  }
  .composer__input {
    flex: 1;
  }
  .composer__input :global(input),
  .composer__input :global(.eden-input) {
    inline-size: 100%;
    border-radius: var(--radius-sm);
    border: 1px solid var(--input);
    background: var(--background);
    transition:
      border-color var(--duration-short-2, 120ms) var(--ease-standard, ease),
      box-shadow var(--duration-short-2, 120ms) var(--ease-standard, ease);
  }
  .composer__input :global(input:focus-visible),
  .composer__input :global(input:focus),
  .composer__input :global(.eden-input:focus-visible) {
    outline: none;
    border-color: var(--ring);
    box-shadow: 0 0 0 3px color-mix(in oklab, var(--ring) 30%, transparent);
  }
  /* The composer Send button gets the shadcn solid-button geometry. */
  .composer :global(.eden-button) {
    border-radius: var(--radius-md);
    background: var(--primary);
    border-color: var(--primary);
    color: var(--primary-foreground);
    font-weight: 600;
    box-shadow: var(--shadow-sm);
  }
  .composer :global(.eden-button:hover:not(:disabled)) {
    filter: brightness(1.08);
    box-shadow: var(--shadow-md);
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
    background: var(--surface-muted);
    color: var(--muted-foreground);
    border: 1px solid var(--border);
  }

  @media (max-width: 760px) {
    .rail {
      display: none;
    }
  }
</style>
