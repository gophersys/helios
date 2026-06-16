<script lang="ts">
  // SettingsModal — the USER-SETTINGS overlay, opened from the profile card. It is the ONE HOME for
  // the tabbed settings surface: a self-contained TAB strip (Agents / Profile / Appearance) rendered
  // inside the reusable centered Modal shell. The host owns nothing but `open` — this component owns
  // the tab state and the content of each tab. "Less is more": the first (and only real) tab today is
  // AGENTS = the default configuration for each supported agent type, read straight off the AGENT_TYPES
  // registry; Profile + Appearance are present-but-minimal so the tabbed structure reads as deliberate.
  //
  // The per-type config Eden has not yet wired to the UI (default model, tool grants, sandbox posture)
  // is shown as a deliberate, muted "wiring in progress" surface so the panel reads as honest-and-growing,
  // not broken-and-missing — the same epistemic stance as AgentConfigView. Fully token-driven from
  // @eden/theme: every color/size/space is a var() over the allowed app token vocabulary
  // (--eden-app-*, --space-*, --font-size-*, --font-code, --color-*); the only literals are token
  // fallbacks and hairline borders. Reduced-motion is honored.
  import type { Theme } from '@eden/theme';
  import Modal from '$lib/chat/Modal.svelte';
  import { AGENT_TYPES, type AgentTypeDescriptor } from '$lib/workspace/agentWorkspace';

  let { open = $bindable(false), theme }: { open?: boolean; theme?: Theme } = $props();

  // The tab strip is local: the host opens the modal, this component decides which tab is shown.
  type TabId = 'agents' | 'profile' | 'appearance';
  interface TabDescriptor {
    id: TabId;
    label: string;
    glyph: string;
  }
  const TABS: readonly TabDescriptor[] = [
    { id: 'agents', label: 'Agents', glyph: '⚙' },
    { id: 'profile', label: 'Profile', glyph: '◐' },
    { id: 'appearance', label: 'Appearance', glyph: '◈' },
  ];
  let activeTab = $state<TabId>('agents');

  // The agent types are a stable record; render them in declaration order as configuration rows.
  const agentTypes = $derived<AgentTypeDescriptor[]>(Object.values(AGENT_TYPES));

  // The per-type config Eden has not yet surfaced to the UI — one home for the list so the
  // "wiring in progress" rows read as a deliberate roadmap rather than missing fields. These land
  // when the git-backed AgentTemplate declares the default model / grants / sandbox posture.
  const PENDING_FIELDS: readonly { key: string; hint: string }[] = [
    { key: 'Tool grants', hint: 'capability allowlist' },
    { key: 'Sandbox posture', hint: 'isolation profile' },
  ];

  /** Roving-tabindex arrow-key navigation across the tab strip (a11y: tablist keyboard pattern). */
  function onTabKeydown(event: KeyboardEvent, index: number): void {
    let next = index;
    if (event.key === 'ArrowRight') next = (index + 1) % TABS.length;
    else if (event.key === 'ArrowLeft') next = (index - 1 + TABS.length) % TABS.length;
    else if (event.key === 'Home') next = 0;
    else if (event.key === 'End') next = TABS.length - 1;
    else return;
    event.preventDefault();
    activeTab = TABS[next].id;
  }
</script>

<Modal bind:open title="Settings" size="lg" {theme}>
  {#snippet children()}
    <div class="settings" data-testid="settings-modal">
      <!-- TAB STRIP: a self-contained tablist; roving tabindex + arrow-key navigation. -->
      <div class="tabs" role="tablist" aria-label="Settings sections" data-testid="settings-tabs">
        {#each TABS as tab, index (tab.id)}
          <button
            type="button"
            class="tab"
            role="tab"
            id={`settings-tab-${tab.id}`}
            data-testid={`settings-tab-${tab.id}`}
            data-active={activeTab === tab.id}
            aria-selected={activeTab === tab.id}
            aria-controls={`settings-tabpanel-${tab.id}`}
            tabindex={activeTab === tab.id ? 0 : -1}
            onclick={() => (activeTab = tab.id)}
            onkeydown={(event) => onTabKeydown(event, index)}
          >
            <span class="tab__glyph" aria-hidden="true">{tab.glyph}</span>
            <span class="tab__label">{tab.label}</span>
          </button>
        {/each}
      </div>

      <!-- AGENTS: the default configuration for each supported agent type. -->
      {#if activeTab === 'agents'}
        <div
          class="panel"
          role="tabpanel"
          id="settings-tabpanel-agents"
          aria-labelledby="settings-tab-agents"
          data-testid="settings-tab-agents"
          tabindex="0"
        >
          <header class="panel__intro">
            <h3 class="panel__title">Agent defaults</h3>
            <p class="panel__subtitle">
              The out-of-the-box configuration each agent type starts from.
            </p>
          </header>

          <ul class="agents" role="list">
            {#each agentTypes as agentType (agentType.id)}
              <li
                class="agent"
                data-testid="agent-type-config"
                data-agent-type={agentType.id}
              >
                <header class="agent__head">
                  <span class="agent__glyph" aria-hidden="true">{agentType.glyph}</span>
                  <span class="agent__label" data-testid="agent-type-config-label">
                    {agentType.label}
                  </span>
                </header>

                <dl class="agent__grid">
                  <div class="row row--wide" data-testid="agent-type-config-widgets">
                    <dt class="row__key">Panel widgets</dt>
                    <dd class="row__val">
                      {#if agentType.widgets.length > 0}
                        <ul class="chips" role="list">
                          {#each agentType.widgets as widget (widget)}
                            <li class="chip">{widget}</li>
                          {/each}
                        </ul>
                      {:else}
                        <span class="unset">none</span>
                      {/if}
                    </dd>
                  </div>

                  <div class="row" data-testid="agent-type-config-model">
                    <dt class="row__key">Default model</dt>
                    <dd class="row__val">
                      <!-- Editable-LOOKING, but read-only / disabled until the AgentTemplate is wired. -->
                      <input
                        class="field"
                        type="text"
                        value="inherit (from AgentTemplate)"
                        readonly
                        disabled
                        aria-label={`Default model for ${agentType.label}`}
                      />
                      <span class="pending-tag">
                        <span class="pending-tag__mark" aria-hidden="true">◌</span>
                        wiring in progress
                      </span>
                    </dd>
                  </div>

                  {#each PENDING_FIELDS as pending (pending.key)}
                    <div class="row row--pending" data-testid="agent-type-config-pending">
                      <dt class="row__key">{pending.key}</dt>
                      <dd class="row__val">
                        <span class="pending">
                          <span class="pending__mark" aria-hidden="true">◌</span>
                          <span class="pending__hint">{pending.hint}</span>
                          <span class="pending-tag">wiring in progress</span>
                        </span>
                      </dd>
                    </div>
                  {/each}
                </dl>
              </li>
            {/each}
          </ul>
        </div>
      {/if}

      <!-- PROFILE: present-but-minimal so the tabbed structure reads as deliberate. -->
      {#if activeTab === 'profile'}
        <div
          class="panel"
          role="tabpanel"
          id="settings-tabpanel-profile"
          aria-labelledby="settings-tab-profile"
          data-testid="settings-tab-profile"
          tabindex="0"
        >
          <header class="panel__intro">
            <h3 class="panel__title">Profile</h3>
            <p class="panel__subtitle">Your account identity and preferences.</p>
          </header>
          <p class="placeholder">
            <span class="pending__mark" aria-hidden="true">◌</span>
            Profile settings — wiring in progress.
          </p>
        </div>
      {/if}

      <!-- APPEARANCE: present-but-minimal so the tabbed structure reads as deliberate. -->
      {#if activeTab === 'appearance'}
        <div
          class="panel"
          role="tabpanel"
          id="settings-tabpanel-appearance"
          aria-labelledby="settings-tab-appearance"
          data-testid="settings-tab-appearance"
          tabindex="0"
        >
          <header class="panel__intro">
            <h3 class="panel__title">Appearance</h3>
            <p class="panel__subtitle">Color mode, density, and theme.</p>
          </header>
          <p class="placeholder">
            <span class="pending__mark" aria-hidden="true">◌</span>
            Appearance settings — wiring in progress.
          </p>
        </div>
      {/if}
    </div>
  {/snippet}
</Modal>

<style>
  .settings {
    display: flex;
    flex-direction: column;
    gap: var(--space-4, 16px);
    inline-size: 100%;
    color: var(--eden-app-fg);
    font-size: var(--font-size-body-large, 15px);
  }

  /* ── tab strip ── */
  .tabs {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1, 4px);
    padding-block-end: var(--space-2, 8px);
    border-block-end: 1px solid var(--eden-app-line);
  }
  .tab {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2, 8px);
    padding: var(--space-2, 8px) var(--space-3, 12px);
    background: none;
    border: 1px solid transparent;
    border-radius: var(--eden-app-radius, 6px);
    color: var(--eden-app-muted);
    cursor: pointer;
    font-family: var(--font-code);
    font-size: var(--font-size-label, 13px);
    font-weight: 600;
    letter-spacing: 0.02em;
    transition:
      color 120ms ease,
      background 120ms ease,
      border-color 120ms ease;
  }
  .tab:hover {
    color: var(--eden-app-fg);
  }
  .tab[data-active='true'] {
    color: var(--eden-app-accent);
    background: var(--eden-app-rail-bg);
    border-color: var(--eden-app-line);
  }
  .tab:focus-visible {
    outline: 2px solid var(--eden-app-accent);
    outline-offset: 2px;
  }
  .tab__glyph {
    color: var(--eden-app-accent);
    font-size: var(--font-size-body-large, 15px);
  }

  /* ── tab panels ── */
  .panel {
    display: flex;
    flex-direction: column;
    gap: var(--space-4, 16px);
    min-inline-size: 0;
  }
  .panel:focus-visible {
    outline: none;
  }
  .panel__intro {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .panel__title {
    margin: 0;
    font-size: var(--font-size-title, 20px);
    font-weight: 600;
    color: var(--eden-app-fg);
  }
  .panel__subtitle {
    margin: 0;
    font-size: var(--font-size-caption, 12px);
    color: var(--eden-app-muted);
  }

  /* ── agent-type cards ── */
  .agents {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-4, 16px);
  }
  .agent {
    display: flex;
    flex-direction: column;
    gap: var(--space-3, 12px);
    padding: var(--space-4, 16px);
    background: var(--eden-app-panel-bg);
    border: 1px solid var(--eden-app-line);
    border-radius: var(--eden-app-radius, 6px);
  }
  .agent__head {
    display: flex;
    align-items: center;
    gap: var(--space-3, 12px);
    padding-block-end: var(--space-2, 8px);
    border-block-end: 1px solid var(--eden-app-line);
  }
  .agent__glyph {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    inline-size: var(--space-7, 28px);
    block-size: var(--space-7, 28px);
    flex: none;
    border: 1px solid var(--eden-app-line);
    border-radius: var(--eden-app-radius, 4px);
    background: var(--eden-app-rail-bg);
    color: var(--eden-app-accent);
    font-size: var(--font-size-body-large, 15px);
  }
  .agent__label {
    font-size: var(--font-size-body-large, 15px);
    font-weight: 600;
    color: var(--eden-app-fg);
  }

  /* ── the per-card definition grid ── */
  .agent__grid {
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
  .row--wide .row__val {
    align-items: flex-start;
  }

  .unset {
    font-size: var(--font-size-label, 13px);
    color: var(--eden-app-muted);
    font-style: italic;
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

  /* ── the editable-looking (but disabled) default-model field ── */
  .field {
    flex: 1 1 14rem;
    min-inline-size: 0;
    padding: var(--space-2, 8px) var(--space-3, 12px);
    background: var(--eden-app-rail-bg);
    color: var(--eden-app-muted);
    border: 1px solid var(--eden-app-line);
    border-radius: var(--eden-app-radius, 4px);
    font-family: var(--font-code);
    font-size: var(--font-size-label, 13px);
    cursor: not-allowed;
  }
  .field:disabled {
    opacity: 0.7;
  }

  /* ── pending / "wiring in progress" affordances ── */
  .pending {
    display: inline-flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--space-2, 8px);
    font-size: var(--font-size-label, 13px);
    color: var(--eden-app-muted);
  }
  .pending__hint {
    font-style: italic;
  }
  .row--pending .row__key {
    color: var(--eden-app-muted);
  }
  .pending__mark {
    color: var(--eden-app-accent);
    opacity: 0.7;
  }
  .pending-tag {
    display: inline-flex;
    align-items: center;
    gap: var(--space-1, 4px);
    padding: 1px var(--space-2, 8px);
    border: 1px solid var(--eden-app-line);
    border-radius: var(--eden-app-radius, 4px);
    background: var(--eden-app-rail-bg);
    color: var(--eden-app-muted);
    font-family: var(--font-code);
    font-size: var(--font-size-caption, 12px);
    letter-spacing: 0.02em;
    text-transform: lowercase;
  }
  .pending-tag__mark {
    color: var(--eden-app-accent);
    opacity: 0.7;
  }

  /* ── placeholder tab bodies ── */
  .placeholder {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2, 8px);
    margin: 0;
    padding: var(--space-4, 16px);
    background: var(--eden-app-panel-bg);
    border: 1px dashed var(--eden-app-line);
    border-radius: var(--eden-app-radius, 6px);
    color: var(--eden-app-muted);
    font-size: var(--font-size-label, 13px);
    font-style: italic;
  }

  @media (prefers-reduced-motion: reduce) {
    .tab {
      transition: none;
    }
  }
</style>
