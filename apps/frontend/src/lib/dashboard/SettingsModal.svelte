<script lang="ts">
  // SettingsModal — the USER-SETTINGS overlay, opened from the profile card. It is the ONE HOME for
  // the tabbed settings surface: a self-contained TAB strip (Agents / Profile / Appearance) rendered
  // inside the reusable centered Modal shell. The host owns nothing but `open` + the config seam —
  // this component owns the tab state and the content of each tab.
  //
  // The AGENTS tab is a REAL editor: per supported agent type (read off the AGENT_TYPES registry) the
  // user edits the default model, the tool grants, and the sandbox posture, and Saves — the host's
  // injected loadConfigs/saveConfig persist each through the gateway (GET/PUT /agent-configs), a user-
  // PREFERENCE layer folded under the AgentTemplate ceiling (an empty field inherits). Profile +
  // Appearance stay present-but-minimal so the tabbed structure reads as deliberate. Fully token-driven
  // from @eden/theme: every color/size/space is a var() over the allowed app token vocabulary
  // (--eden-app-*, --space-*, --font-size-*, --font-code, --color-*); the only literals are token
  // fallbacks and hairline borders. Reduced-motion is honored.
  import type { Theme } from '@eden/theme';
  import type { AgentConfigView } from '$lib/gateway/types';
  import Modal from '$lib/chat/Modal.svelte';
  import { AGENT_TYPES, type AgentTypeDescriptor } from '$lib/workspace/agentWorkspace';

  // The configuration seam is injected as callbacks (the host wires them to its GatewayClient), so
  // this component stays decoupled from the gateway value layer — the same seam the create flow uses.
  // When they are absent the Agents tab degrades to read-only "inherit" defaults (graceful).
  interface SaveBody {
    model: string;
    toolGrants: string[];
    sandboxPosture: string;
  }
  let {
    open = $bindable(false),
    theme,
    loadConfigs,
    saveConfig,
  }: {
    open?: boolean;
    theme?: Theme;
    loadConfigs?: () => Promise<AgentConfigView[]>;
    saveConfig?: (agentType: string, body: SaveBody) => Promise<AgentConfigView>;
  } = $props();

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

  // ── the editable per-agent-type draft state ─────────────────────────────────────.
  // One draft per agent type: the editable model, comma-separated tool grants, sandbox posture, and a
  // save status. Initialized empty (= inherit) so every binding has a stable target before the load
  // resolves; loadAll() then folds in any saved configuration.
  type SaveStatus = 'idle' | 'saving' | 'saved' | 'error';
  interface Draft {
    model: string;
    grants: string;
    posture: string;
    status: SaveStatus;
    message?: string;
  }
  const emptyDraft = (): Draft => ({ model: '', grants: '', posture: '', status: 'idle' });
  let drafts = $state<Record<string, Draft>>(
    Object.fromEntries(Object.values(AGENT_TYPES).map((type) => [type.id, emptyDraft()])),
  );
  let loaded = $state(false);
  let loadError = $state<string | null>(null);

  /** Load the saved per-agent-type configurations into the drafts (an agent type with no saved
   *  config keeps its empty/inherit draft). */
  async function loadAll(): Promise<void> {
    if (!loadConfigs) {
      loaded = true;
      return;
    }
    try {
      const configs = await loadConfigs();
      const next: Record<string, Draft> = {};
      for (const type of agentTypes) next[type.id] = emptyDraft();
      for (const config of configs) {
        next[config.agentType] = {
          model: config.model,
          grants: config.toolGrants.join(', '),
          posture: config.sandboxPosture,
          status: 'idle',
        };
      }
      drafts = next;
      loadError = null;
    } catch (cause) {
      loadError = cause instanceof Error ? cause.message : String(cause);
    } finally {
      loaded = true;
    }
  }

  // Load once per open; reset on close so a re-open re-reads fresh.
  $effect(() => {
    if (open && !loaded) void loadAll();
    if (!open) loaded = false;
  });

  /** Persist one agent type's draft (parse the comma-separated grants into the array the API wants),
   *  then reflect the server-normalized result back into the draft. */
  async function save(agentTypeId: string): Promise<void> {
    if (!saveConfig) return;
    const draft = drafts[agentTypeId];
    if (!draft) return;
    draft.status = 'saving';
    draft.message = undefined;
    const toolGrants = draft.grants
      .split(',')
      .map((grant) => grant.trim())
      .filter(Boolean);
    try {
      const stored = await saveConfig(agentTypeId, {
        model: draft.model.trim(),
        toolGrants,
        sandboxPosture: draft.posture,
      });
      drafts[agentTypeId] = {
        model: stored.model,
        grants: stored.toolGrants.join(', '),
        posture: stored.sandboxPosture,
        status: 'saved',
      };
    } catch (cause) {
      draft.status = 'error';
      draft.message = cause instanceof Error ? cause.message : String(cause);
    }
  }

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
          data-testid="settings-panel-agents"
          tabindex="0"
        >
          <header class="panel__intro">
            <h3 class="panel__title">Agent defaults</h3>
            <p class="panel__subtitle">
              The out-of-the-box configuration each agent type starts from.
            </p>
          </header>

          {#if loadError}
            <p class="load-error" data-testid="settings-load-error" role="alert">{loadError}</p>
          {/if}

          <ul class="agents" role="list">
            {#each agentTypes as agentType (agentType.id)}
              {@const draft = drafts[agentType.id]}
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
                      <input
                        class="field field--editable"
                        type="text"
                        bind:value={draft.model}
                        placeholder="inherit (from AgentTemplate)"
                        aria-label={`Default model for ${agentType.label}`}
                        data-testid="agent-type-config-model-input"
                        disabled={!saveConfig}
                        autocomplete="off"
                        spellcheck="false"
                      />
                    </dd>
                  </div>

                  <div class="row" data-testid="agent-type-config-grants">
                    <dt class="row__key">Tool grants</dt>
                    <dd class="row__val">
                      <input
                        class="field field--editable"
                        type="text"
                        bind:value={draft.grants}
                        placeholder="Read, Write, Bash…"
                        aria-label={`Tool grants for ${agentType.label} (comma separated)`}
                        data-testid="agent-type-config-grants-input"
                        disabled={!saveConfig}
                        autocomplete="off"
                        spellcheck="false"
                      />
                    </dd>
                  </div>

                  <div class="row" data-testid="agent-type-config-posture">
                    <dt class="row__key">Sandbox posture</dt>
                    <dd class="row__val">
                      <select
                        class="field field--select"
                        bind:value={draft.posture}
                        aria-label={`Sandbox posture for ${agentType.label}`}
                        data-testid="agent-type-config-posture-input"
                        disabled={!saveConfig}
                      >
                        <option value="">inherit</option>
                        <option value="strict">strict</option>
                        <option value="relaxed">relaxed</option>
                      </select>
                    </dd>
                  </div>

                  <div class="row" data-testid="agent-type-config-actions">
                    <dt class="row__key" aria-hidden="true"></dt>
                    <dd class="row__val agent__save">
                      <button
                        type="button"
                        class="save-btn"
                        data-testid="agent-type-config-save"
                        disabled={!saveConfig || draft.status === 'saving'}
                        onclick={() => save(agentType.id)}
                      >
                        {draft.status === 'saving' ? 'Saving…' : 'Save'}
                      </button>
                      {#if draft.status === 'saved'}
                        <span class="save-status save-status--ok" data-testid="agent-type-config-saved">
                          ✓ saved
                        </span>
                      {:else if draft.status === 'error'}
                        <span class="save-status save-status--error" role="alert">
                          {draft.message ?? 'failed'}
                        </span>
                      {/if}
                    </dd>
                  </div>
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
          data-testid="settings-panel-profile"
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
          data-testid="settings-panel-appearance"
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

  /* ── the editable per-agent-type fields ── */
  .field {
    flex: 1 1 14rem;
    min-inline-size: 0;
    padding: var(--space-2, 8px) var(--space-3, 12px);
    background: var(--eden-app-bg);
    color: var(--eden-app-fg);
    border: 1px solid var(--eden-app-line);
    border-radius: var(--eden-app-radius, 4px);
    font-family: var(--font-code);
    font-size: var(--font-size-label, 13px);
  }
  .field:focus-visible {
    outline: none;
    border-color: var(--eden-app-accent);
    box-shadow: 0 0 0 1px var(--eden-app-accent);
  }
  .field:disabled {
    color: var(--eden-app-muted);
    cursor: not-allowed;
    opacity: 0.7;
  }
  .field--select {
    flex: 0 0 auto;
    cursor: pointer;
  }
  .field--select:disabled {
    cursor: not-allowed;
  }

  /* ── the ◌ mark on the present-but-minimal Profile/Appearance placeholders ── */
  .pending__mark {
    color: var(--eden-app-accent);
    opacity: 0.7;
  }

  /* ── save action + status ── */
  .agent__save {
    align-items: center;
  }
  .save-btn {
    padding: var(--space-2, 8px) var(--space-4, 16px);
    border: 1px solid var(--eden-app-accent);
    border-radius: var(--eden-app-radius, 6px);
    background: var(--eden-app-accent);
    color: var(--color-on-primary, var(--eden-app-bg));
    font-family: var(--font-code);
    font-size: var(--font-size-label, 13px);
    font-weight: 600;
    cursor: pointer;
    transition: opacity 120ms ease;
  }
  .save-btn:hover:not(:disabled) {
    opacity: 0.9;
  }
  .save-btn:focus-visible {
    outline: 2px solid var(--eden-app-accent);
    outline-offset: 2px;
  }
  .save-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .save-status {
    font-size: var(--font-size-caption, 12px);
    font-family: var(--font-code);
  }
  .save-status--ok {
    color: var(--color-success, var(--eden-app-accent));
  }
  .save-status--error {
    color: var(--color-error);
  }
  .load-error {
    margin: 0;
    padding: var(--space-2, 8px) var(--space-3, 12px);
    border: 1px solid var(--color-error);
    border-radius: var(--eden-app-radius, 6px);
    color: var(--color-error);
    font-size: var(--font-size-label, 13px);
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
