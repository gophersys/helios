<script lang="ts">
  // SupervisorConversation — the workspace LEFT pane: the live conversation with the project's
  // SUPERVISOR agent. It REUSES the chat SSE rails wholesale — it takes an already-open ChatSession
  // (the host binds it to project.supervisorAgentId and calls open()) and renders the SAME agentsession
  // event taxonomy the chat slice does, with the SAME components: ChatMessage (assistant text +
  // thinking), ChatTool (tool calls), ChatPermission (the human-in-the-loop gate), plus the user
  // bubble (Message), notices, and the terminal banner — all laid on the connected timeline rail. The
  // live status bar (ChatStatusBar) + the context/cost bar (ChatContextBar) sit under the transcript,
  // and a composer sends prompts (its enablement DERIVES from the session's projected allowed-set, the
  // one source of truth, so an illegal turn is never offerable).
  //
  // REUSABLE + promotion-ready (agent-UI lib principle): it is the chat transcript extracted as a
  // self-contained pane, so the workspace and the standalone chat surface share ONE conversation
  // renderer. It owns no session lifecycle (the host opens/closes the ChatSession) — one home for the
  // taxonomy fold is session.svelte.ts; this only renders it. Token-driven from @eden/theme.
  //
  // PROMOTION NOTE: staged in apps/frontend/src/lib/workspace pending the lib pipeline (ADR-0020); it
  // cites the chat components in $lib/chat (one home — never re-implemented), which promote together.
  import { Button, Input, Message } from '@eden/primitives';
  import type { Theme } from '@eden/theme';
  import type { ChatSession } from '$lib/gateway/session.svelte';
  import ChatMessage from '$lib/chat/ChatMessage.svelte';
  import ChatTool from '$lib/chat/ChatTool.svelte';
  import ChatPermission from '$lib/chat/ChatPermission.svelte';
  import ChatStatusBar from '$lib/chat/ChatStatusBar.svelte';
  import ChatContextBar from '$lib/chat/ChatContextBar.svelte';

  let {
    session,
    theme,
  }: {
    /** The OPEN supervisor ChatSession (the host binds + opens it; this only renders). */
    session: ChatSession;
    /** The active generated theme — required, since the cited chat components (ChatMessage,
     *  ChatPermission) take a non-optional Theme; the host always supplies the page's edenTheme. */
    theme: Theme;
  } = $props();

  let composer = $state('');
  let scroller = $state<HTMLElement | null>(null);

  // Autoscroll the transcript as entries stream in (mirrors the chat slice).
  $effect(() => {
    if (session.entries.length >= 0 && scroller) {
      queueMicrotask(() => {
        if (scroller) scroller.scrollTop = scroller.scrollHeight;
      });
    }
  });

  async function sendComposer(): Promise<void> {
    const text = composer.trim();
    // Prompt is legal only in ready/awaiting-input — the projected allowed-set guards both the Send
    // button and the Enter key, so the composer can never fire an illegal Prompt (which would 409).
    if (!text || !session.allowed.has('prompt')) return;
    composer = '';
    await session.send(text);
  }

  function onComposerKey(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      void sendComposer();
    }
  }

  /** The timeline-rail node glyph for a transcript entry (the marker on the connecting line). Same
   *  vocabulary as the chat slice so the conversation reads identically across surfaces. */
  function railGlyph(role: string): string {
    if (role === 'user') return '▍';
    if (role === 'assistant') return '✦';
    if (role === 'tool') return '⎿';
    if (role === 'permission') return '?';
    if (role === 'terminal') return '■';
    return '·';
  }

  function connectionTone(status: string): 'ok' | 'info' | 'warn' | 'muted' {
    if (status === 'open') return 'ok';
    if (status === 'connecting' || status === 'reconnecting') return 'info';
    if (status === 'ended') return 'muted';
    return 'warn';
  }
</script>

<div class="conversation" data-testid="supervisor-conversation">
  <header class="conversation__head">
    <span class="conversation__label">
      <span class="conversation__glyph" aria-hidden="true">⌖</span>
      Supervisor
    </span>
    <code class="conversation__id" data-testid="supervisor-session-id">{session.id}</code>
    <span class="conversation__chip" data-testid="supervisor-state">{session.sessionState}</span>
    <span
      class="conversation__chip conversation__chip--{connectionTone(session.connection)}"
      data-testid="supervisor-connection"
    >
      {session.connection}
    </span>
  </header>

  <div class="conversation__body" bind:this={scroller} data-testid="supervisor-transcript">
    <ul class="turns" role="list">
      {#each session.entries as entry (entry.id)}
        <li class="turn" data-role={entry.role} data-testid="supervisor-turn">
          <span class="turn__rail" aria-hidden="true">
            <span class="turn__node" data-role={entry.role}>{railGlyph(entry.role)}</span>
          </span>
          <div class="turn__main">
            {#if entry.role === 'user'}
              <div class="turn--user" data-testid="supervisor-user-message">
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
                onresolve={(requestId, verdict, scope) => session.resolve(requestId, verdict, scope)}
              />
            {:else if entry.role === 'notice'}
              <div class="notice notice--{entry.tone}" data-testid="supervisor-notice">
                {entry.text}
              </div>
            {:else if entry.role === 'terminal'}
              <div
                class="terminal"
                data-testid="supervisor-terminal"
                data-outcome={entry.outcome}
              >
                <span class="conversation__chip conversation__chip--{entry.outcome === 'completed' ? 'ok' : 'warn'}">
                  {entry.outcome}
                </span>
                {#if entry.text}<span class="terminal__text">{entry.text}</span>{/if}
              </div>
            {/if}
          </div>
        </li>
      {/each}
    </ul>
    {#if session.entries.length === 0}
      <p class="conversation__waiting" data-testid="supervisor-waiting">
        Waiting for the supervisor's first events…
      </p>
    {/if}
  </div>

  <ChatStatusBar {session} {theme} />
  <ChatContextBar meter={session.meter} {theme} />

  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="composer" data-testid="supervisor-composer" onkeydown={onComposerKey}>
    <div class="composer__input">
      <Input
        bind:value={composer}
        placeholder="Message the supervisor…"
        aria-label="Message the supervisor"
        {theme}
      />
    </div>
    <span class="composer__send" data-testid="supervisor-send">
      <Button
        variant="primary"
        {theme}
        disabled={!session.allowed.has('prompt')}
        onclick={sendComposer}>Send</Button
      >
    </span>
  </div>
</div>

<style>
  .conversation {
    display: flex;
    flex-direction: column;
    min-block-size: 0;
    block-size: 100%;
    overflow: hidden;
  }
  .conversation__head {
    display: flex;
    align-items: center;
    gap: var(--space-2, 8px);
    padding: var(--space-2, 8px) var(--space-4, 16px);
    border-block-end: 1px solid var(--eden-app-line);
    flex: none;
    flex-wrap: wrap;
  }
  .conversation__label {
    display: inline-flex;
    align-items: center;
    gap: var(--space-1, 4px);
    font-weight: 650;
    color: var(--eden-app-fg);
  }
  .conversation__glyph {
    color: var(--eden-app-accent);
  }
  .conversation__id {
    font-family: var(--font-code);
    font-size: var(--font-size-caption, 12px);
    color: var(--eden-app-muted);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-inline-size: 18ch;
  }
  .conversation__chip {
    font-family: var(--font-code);
    font-size: var(--font-size-caption, 12px);
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    border-radius: 999px;
    padding: 0.14rem 0.5rem;
    line-height: 1.4;
    background: color-mix(in oklab, var(--color-on-surface) 8%, var(--color-surface));
    color: var(--eden-app-muted);
    white-space: nowrap;
  }
  .conversation__chip--ok {
    background: var(--color-primary);
    color: var(--color-on-primary);
  }
  .conversation__chip--info {
    background: color-mix(in oklab, var(--color-info) 16%, var(--color-surface));
    color: var(--color-info);
  }
  .conversation__chip--warn {
    background: color-mix(in oklab, var(--color-warning) 22%, var(--color-surface));
    color: var(--color-warning);
  }
  .conversation__chip--muted {
    background: color-mix(in oklab, var(--color-on-surface) 8%, var(--color-surface));
    color: var(--eden-app-muted);
  }
  .conversation__body {
    flex: 1;
    min-block-size: 0;
    overflow-y: auto;
    padding: var(--space-4, 16px);
  }
  .conversation__waiting {
    color: var(--eden-app-muted);
    font-style: italic;
    font-size: var(--font-size-label, 13px);
  }
  .turns {
    list-style: none;
    margin: 0;
    padding: 0;
  }
  /* Each turn on a connected timeline rail (the same thread shape as the chat slice). */
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
  .turn__main {
    min-inline-size: 0;
    padding-block-start: 1px;
  }
  .turn--user :global(.eden-message) {
    max-inline-size: 60ch;
  }
  .notice {
    border-radius: var(--eden-app-radius, 8px);
    padding: var(--space-2, 8px) var(--space-3, 12px);
    font-size: var(--font-size-label, 13px);
    border: 1px dashed var(--eden-app-line);
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
  }
  .terminal__text {
    font-weight: 600;
  }
  .composer {
    display: flex;
    align-items: center;
    gap: var(--space-3, 12px);
    padding: var(--space-3, 12px) var(--space-4, 16px);
    border-block-start: 1px solid var(--eden-app-line);
    flex: none;
  }
  .composer__input {
    flex: 1;
  }
  .composer__input :global(input) {
    inline-size: 100%;
  }
  .composer__send {
    display: inline-flex;
  }
</style>
