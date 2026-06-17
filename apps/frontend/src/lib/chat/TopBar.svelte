<script lang="ts">
  // The workspace TOP BAR — the Eden brand + the active session's identity (agent type · harness ·
  // model · connection) + the ⌘K command-palette affordance. The web-native counterpart of a TUI's
  // top status line. Token-driven from @eden/theme.
  import type { Theme } from '@eden/theme';
  import type { ChatSession } from '$lib/gateway/session.svelte';
  import type { AgentTypeDescriptor } from '$lib/workspace/agentWorkspace';

  let {
    active,
    agentType,
    railOpen = true,
    panelOpen = true,
    showPanelToggle = false,
    onToggleRail,
    onTogglePanel,
    onPalette,
    onSettings,
    onConfig,
  }: {
    active: ChatSession | null;
    agentType: AgentTypeDescriptor | null;
    railOpen?: boolean;
    panelOpen?: boolean;
    showPanelToggle?: boolean;
    onToggleRail?: () => void;
    onTogglePanel?: () => void;
    onPalette: () => void;
    onSettings?: () => void;
    onConfig?: () => void;
    theme?: Theme;
  } = $props();

  const isMac =
    typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform || '');
</script>

<header class="topbar" data-testid="top-bar">
  {#if onToggleRail}
    <button
      class="topbar__icon-btn"
      data-testid="toggle-rail"
      aria-label={railOpen ? 'Collapse sessions' : 'Show sessions'}
      aria-pressed={railOpen}
      title="Sessions"
      onclick={onToggleRail}
    >
      <span aria-hidden="true">{railOpen ? '⟨' : '☰'}</span>
    </button>
  {/if}
  <a class="topbar__brand" href="/projects" data-testid="top-home" title="Back to Eden">
    <span class="topbar__mark" aria-hidden="true">◆</span>
    <span class="topbar__name">Eden</span>
  </a>

  {#if active && agentType}
    <!-- the session identity doubles as the agent-config affordance (config easily available) -->
    <button
      class="topbar__session"
      data-testid="top-session"
      title="Agent configuration"
      disabled={!onConfig}
      onclick={onConfig}
    >
      <span class="topbar__type">
        <span class="topbar__glyph" aria-hidden="true">{agentType.glyph}</span>
        {agentType.label}
      </span>
      <span class="topbar__sep" aria-hidden="true">/</span>
      <code class="topbar__id">{active.id}</code>
      {#if active.meter.model}
        <span class="topbar__sep" aria-hidden="true">·</span>
        <code class="topbar__model">{active.meter.model}</code>
      {/if}
      <span
        class="topbar__conn"
        data-state={active.connection}
        title="stream {active.connection}"
        aria-label="stream {active.connection}"
      ></span>
      {#if onConfig}<span class="topbar__cfg" aria-hidden="true">ⓘ</span>{/if}
    </button>
  {/if}

  <div class="topbar__actions">
    <button class="topbar__palette" data-testid="palette-open" onclick={onPalette}>
      <span aria-hidden="true">⌘K</span>
      <span class="topbar__palette-label">{isMac ? '⌘' : 'Ctrl'} K · commands</span>
    </button>
    {#if showPanelToggle && onTogglePanel}
      <button
        class="topbar__icon-btn"
        data-testid="toggle-panel"
        aria-label={panelOpen ? 'Collapse panel' : 'Show panel'}
        aria-pressed={panelOpen}
        title="Workspace panel"
        onclick={onTogglePanel}
      >
        <span aria-hidden="true">{panelOpen ? '⟩' : '◧'}</span>
      </button>
    {/if}
    {#if onSettings}
      <button
        class="topbar__icon-btn"
        data-testid="settings-open"
        aria-label="Settings"
        title="Settings"
        onclick={onSettings}
      >
        <span aria-hidden="true">⚙</span>
      </button>
    {/if}
  </div>
</header>

<style>
  .topbar {
    display: flex;
    align-items: center;
    gap: var(--space-4, 16px);
    padding: var(--space-2, 8px) var(--space-4, 16px);
    background: var(--eden-app-panel-bg);
    border-block-end: 1px solid var(--eden-app-line);
    min-block-size: calc(var(--space-8, 32px) + var(--space-1, 4px));
  }
  .topbar__brand {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2, 8px);
    text-decoration: none;
    color: inherit;
    border-radius: var(--eden-app-radius, 8px);
  }
  .topbar__brand:hover {
    opacity: 0.85;
  }
  .topbar__mark {
    color: var(--eden-app-accent);
    font-size: var(--font-size-body-large, 16px);
  }
  .topbar__name {
    font-weight: 700;
    letter-spacing: 0.02em;
  }
  .topbar__session {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2, 8px);
    font-size: var(--font-size-caption, 12px);
    color: var(--eden-app-muted);
    overflow: hidden;
    white-space: nowrap;
    background: none;
    border: 1px solid transparent;
    border-radius: var(--eden-app-radius, 4px);
    padding: var(--space-1, 4px) var(--space-2, 8px);
    cursor: pointer;
  }
  .topbar__session:hover:not(:disabled) {
    border-color: var(--eden-app-line);
    background: var(--eden-app-rail-bg);
  }
  .topbar__session:disabled {
    cursor: default;
  }
  .topbar__cfg {
    color: var(--eden-app-accent);
  }
  .topbar__type {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    color: var(--eden-app-fg);
    font-weight: 600;
  }
  .topbar__glyph {
    color: var(--eden-app-accent);
  }
  .topbar__id,
  .topbar__model {
    font-family: var(--font-code);
  }
  .topbar__sep {
    opacity: 0.4;
  }
  .topbar__conn {
    inline-size: 8px;
    block-size: 8px;
    border-radius: 50%;
    background: var(--eden-app-muted);
  }
  .topbar__conn[data-state='open'] {
    background: var(--color-info);
  }
  .topbar__conn[data-state='connecting'],
  .topbar__conn[data-state='reconnecting'] {
    background: var(--color-warning);
  }
  .topbar__conn[data-state='ended'] {
    background: var(--eden-app-muted);
  }
  .topbar__actions {
    margin-inline-start: auto;
    display: inline-flex;
    align-items: center;
    gap: var(--space-2, 8px);
  }
  .topbar__palette {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2, 8px);
    padding: var(--space-1, 4px) var(--space-3, 12px);
    background: var(--eden-app-rail-bg);
    border: 1px solid var(--eden-app-line);
    border-radius: var(--eden-app-radius, 4px);
    color: var(--eden-app-muted);
    font-family: var(--font-code);
    font-size: var(--font-size-caption, 12px);
    cursor: pointer;
  }
  .topbar__icon-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    inline-size: calc(var(--space-6, 24px) + var(--space-1, 4px));
    block-size: calc(var(--space-6, 24px) + var(--space-1, 4px));
    background: var(--eden-app-rail-bg);
    border: 1px solid var(--eden-app-line);
    border-radius: var(--eden-app-radius, 4px);
    color: var(--eden-app-muted);
    cursor: pointer;
  }
  .topbar__icon-btn:hover {
    color: var(--eden-app-fg);
    border-color: var(--eden-app-accent);
  }
  .topbar__palette:hover {
    color: var(--eden-app-fg);
    border-color: var(--eden-app-accent);
  }
  .topbar__palette > span:first-child {
    color: var(--eden-app-accent);
    font-weight: 700;
  }
  @media (max-width: 720px) {
    .topbar__palette-label,
    .topbar__session {
      display: none;
    }
  }
</style>
