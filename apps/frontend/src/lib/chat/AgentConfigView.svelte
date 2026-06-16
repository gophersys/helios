<script lang="ts">
  // AgentConfigView — the AGENT-SESSION configuration surface. Presents what Eden knows about a
  // live session's configuration as a clean, scannable definition grid, grouped into IDENTITY (who
  // this agent is + how it is wired today) and CAPABILITIES (the panel widget set it mounts). It is
  // a self-contained CONTENT component: it renders inside a centered Modal (the top-of-chat "agent
  // config" control opens it) but is equally happy inline — it owns no overlay/scrim of its own.
  //
  // Config Eden does not yet expose to the UI (tool grants, sandbox posture, the git-backed
  // AgentTemplate) is shown as a deliberate, muted "wiring in progress" row so the surface reads as
  // honest-and-growing, not broken-and-missing. Fully token-driven from @eden/theme — every
  // color/size is a var(); the only literals are token fallbacks and hairline borders.
  import type { Theme } from '@eden/theme';
  import type { ChatSession } from '$lib/gateway/session.svelte';
  import type { AgentTypeDescriptor } from '$lib/workspace/agentWorkspace';

  let {
    session,
    agentType,
    theme: _theme,
  }: { session: ChatSession; agentType: AgentTypeDescriptor; theme?: Theme } = $props();

  // The live model is the meter's (reconciled from usage/ledger); empty until the first usage tick.
  const model = $derived(session.meter.model || '');
  // The lifecycle state drives a tone so the row reads at a glance (working / settled / faulted).
  const stateTone = $derived(stateToneOf(session.sessionState));

  /** stateToneOf maps a SessionState to a presentational tone for the live-state pill. */
  function stateToneOf(state: string): 'idle' | 'active' | 'good' | 'bad' {
    switch (state) {
      case 'running':
      case 'awaiting-input':
      case 'awaiting-permission':
        return 'active';
      case 'completed':
      case 'ready':
        return 'good';
      case 'failed':
      case 'aborted':
        return 'bad';
      default:
        return 'idle';
    }
  }

  // The config Eden has not yet surfaced — declared here so the "wiring in progress" rows read as a
  // deliberate roadmap, one home for the list. These land when the git-backed AgentTemplate is wired.
  const PENDING: readonly string[] = ['Tool grants', 'Sandbox posture', 'Agent template'];
</script>

<section class="config" data-testid="agent-config" aria-label="agent session configuration">
  <header class="config__head">
    <span class="config__glyph" data-testid="config-glyph" aria-hidden="true">{agentType.glyph}</span>
    <div class="config__heading">
      <h2 class="config__title">Agent configuration</h2>
      <p class="config__subtitle">What Eden knows about this session</p>
    </div>
  </header>

  <!-- IDENTITY: who this agent is + how it is wired today -->
  <section class="group" data-testid="config-group-identity" aria-label="identity">
    <h3 class="group__label">Identity</h3>
    <dl class="grid">
      <div class="row" data-testid="config-type">
        <dt class="row__key">Agent type</dt>
        <dd class="row__val">
          <span class="agenttype">
            <span class="agenttype__glyph" aria-hidden="true">{agentType.glyph}</span>
            <span class="agenttype__label">{agentType.label}</span>
          </span>
        </dd>
      </div>

      <div class="row" data-testid="config-session">
        <dt class="row__key">Session id</dt>
        <dd class="row__val"><code class="mono">{session.id}</code></dd>
      </div>

      <div class="row" data-testid="config-harness">
        <dt class="row__key">Harness</dt>
        <dd class="row__val"><code class="mono">{session.harness}</code></dd>
      </div>

      <div class="row" data-testid="config-model">
        <dt class="row__key">Model</dt>
        <dd class="row__val">
          {#if model}
            <code class="mono">{model}</code>
          {:else}
            <span class="unset" data-testid="config-model-unset">resolving…</span>
          {/if}
        </dd>
      </div>

      <div class="row" data-testid="config-state">
        <dt class="row__key">Live state</dt>
        <dd class="row__val">
          <span class="state" data-tone={stateTone} data-testid="config-state-pill">
            <span class="state__dot" data-tone={stateTone} aria-hidden="true"></span>
            <span class="state__text">{session.sessionState}</span>
          </span>
        </dd>
      </div>
    </dl>
  </section>

  <!-- CAPABILITIES: the panel widget set this agent type mounts -->
  <section class="group" data-testid="config-group-capabilities" aria-label="capabilities">
    <h3 class="group__label">Capabilities</h3>
    <dl class="grid">
      <div class="row row--wide" data-testid="config-widgets">
        <dt class="row__key">Panel widgets</dt>
        <dd class="row__val">
          {#if agentType.widgets.length > 0}
            <ul class="chips" role="list">
              {#each agentType.widgets as widget (widget)}
                <li class="chip" data-testid="config-widget-chip">{widget}</li>
              {/each}
            </ul>
          {:else}
            <span class="unset">none</span>
          {/if}
        </dd>
      </div>
    </dl>
  </section>

  <!-- ROADMAP: config the git-backed AgentTemplate carries that Eden has not yet surfaced to the UI -->
  <section class="group" data-testid="config-group-pending" aria-label="not yet surfaced">
    <h3 class="group__label">From the AgentTemplate</h3>
    <dl class="grid">
      {#each PENDING as item (item)}
        <div class="row row--pending" data-testid="config-pending-row">
          <dt class="row__key">{item}</dt>
          <dd class="row__val">
            <span class="pending">
              <span class="pending__mark" aria-hidden="true">◌</span>
              from the AgentTemplate — wiring in progress
            </span>
          </dd>
        </div>
      {/each}
    </dl>
  </section>
</section>

<style>
  .config {
    display: flex;
    flex-direction: column;
    gap: var(--space-5, 24px);
    inline-size: 100%;
    color: var(--eden-app-fg);
    font-size: var(--font-size-body-large, 15px);
  }

  /* ── header ── */
  .config__head {
    display: flex;
    align-items: center;
    gap: var(--space-3, 12px);
    padding-block-end: var(--space-3, 12px);
    border-block-end: 1px solid var(--eden-app-line);
  }
  .config__glyph {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    inline-size: var(--space-7, 40px);
    block-size: var(--space-7, 40px);
    flex: none;
    border: 1px solid var(--eden-app-line);
    border-radius: var(--eden-app-radius, 4px);
    background: var(--eden-app-panel-bg);
    color: var(--eden-app-accent);
    font-size: var(--font-size-title, 20px);
  }
  .config__heading {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-inline-size: 0;
  }
  .config__title {
    margin: 0;
    font-size: var(--font-size-title, 20px);
    font-weight: 600;
    color: var(--eden-app-fg);
  }
  .config__subtitle {
    margin: 0;
    font-size: var(--font-size-caption, 12px);
    color: var(--eden-app-muted);
  }

  /* ── grouped sections ── */
  .group {
    display: flex;
    flex-direction: column;
    gap: var(--space-2, 8px);
    min-inline-size: 0;
  }
  .group__label {
    margin: 0;
    font-family: var(--font-code);
    font-size: var(--font-size-caption, 12px);
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--eden-app-muted);
  }

  /* ── the definition grid ── */
  .grid {
    margin: 0;
    display: grid;
    grid-template-columns: minmax(8rem, max-content) 1fr;
    gap: 1px;
    background: var(--eden-app-line);
    border: 1px solid var(--eden-app-line);
    border-radius: var(--eden-app-radius, 4px);
    overflow: hidden;
  }
  .row {
    display: contents;
  }
  .row__key,
  .row__val {
    background: var(--eden-app-panel-bg);
    padding: var(--space-2, 8px) var(--space-3, 12px);
    min-inline-size: 0;
  }
  .row__key {
    font-size: var(--font-size-label, 13px);
    color: var(--eden-app-muted);
    white-space: nowrap;
  }
  .row__val {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--space-2, 8px);
    color: var(--eden-app-fg);
    overflow-wrap: anywhere;
  }
  /* a full-bleed row whose value wraps freely (the chip set) */
  .row--wide .row__val {
    align-items: flex-start;
  }

  .mono {
    font-family: var(--font-code);
    font-size: var(--font-size-label, 13px);
    color: var(--eden-app-fg);
    font-variant-numeric: tabular-nums;
    overflow-wrap: anywhere;
  }
  .unset {
    font-size: var(--font-size-label, 13px);
    color: var(--eden-app-muted);
    font-style: italic;
  }

  /* ── agent type cell ── */
  .agenttype {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2, 8px);
  }
  .agenttype__glyph {
    color: var(--eden-app-accent);
    font-size: var(--font-size-body-large, 15px);
  }
  .agenttype__label {
    font-weight: 600;
    color: var(--eden-app-fg);
  }

  /* ── live-state pill ── */
  .state {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2, 8px);
    padding: 2px var(--space-2, 8px);
    border-radius: var(--eden-app-radius, 4px);
    border: 1px solid var(--eden-app-line);
    font-family: var(--font-code);
    font-size: var(--font-size-caption, 12px);
    letter-spacing: 0.02em;
    background: var(--eden-app-panel-bg);
  }
  .state__dot {
    inline-size: 7px;
    block-size: 7px;
    border-radius: 50%;
    flex: none;
    background: var(--eden-app-muted);
  }
  .state__dot[data-tone='active'] {
    background: var(--eden-app-accent);
    animation: config-pulse 1.2s ease-in-out infinite;
  }
  .state__dot[data-tone='good'] {
    background: var(--color-info);
  }
  .state__dot[data-tone='bad'] {
    background: var(--color-error);
  }
  .state[data-tone='active'] .state__text {
    color: var(--eden-app-accent);
  }
  .state[data-tone='good'] .state__text {
    color: var(--eden-app-fg);
  }
  .state[data-tone='bad'] .state__text {
    color: var(--color-error);
  }

  /* ── capability chips ── */
  .chips {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2, 8px);
  }
  .chip {
    display: inline-flex;
    align-items: center;
    padding: 2px var(--space-2, 8px);
    border: 1px solid var(--eden-app-line);
    border-radius: var(--eden-app-radius, 4px);
    background: var(--eden-app-rail-bg);
    color: var(--eden-app-fg);
    font-family: var(--font-code);
    font-size: var(--font-size-caption, 12px);
    letter-spacing: 0.02em;
  }

  /* ── pending / roadmap rows ── */
  .row--pending .row__key {
    color: var(--eden-app-muted);
  }
  .pending {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2, 8px);
    font-size: var(--font-size-label, 13px);
    font-style: italic;
    color: var(--eden-app-muted);
  }
  .pending__mark {
    color: var(--eden-app-accent);
    font-style: normal;
    opacity: 0.7;
  }

  @keyframes config-pulse {
    50% {
      opacity: 0.4;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .state__dot[data-tone='active'] {
      animation: none;
    }
  }
</style>
