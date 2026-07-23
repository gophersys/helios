<script lang="ts">
  // The ONE Settings surface (doc 17 §7 · W-UI-4). Replaces BOTH legacy surfaces — the dashboard's
  // SettingsModal (Agents CRUD) and the Build top-bar SettingsPanel (colour mode) — with a single
  // sheet-hosted Settings shell composed from @eden/primitives' SettingsSurface organism (the reusable
  // left section-rail + per-section content area; the focus trap / Escape / portal are the bits-ui
  // Dialog layer, reinvented nowhere). Four sections per §7:
  //
  //   • Profile      — the platform identity read from currentUser (read-only display).
  //   • Appearance   — theme light/dark/system driving the REAL themePreference store (live retheme).
  //   • Agents       — the existing per-agent-type config cards (GET/PUT /agent-configs), with the
  //                    EXACT testids + PUT wire shape the e2e pins ({model, toolGrants[], sandboxPosture}).
  //   • Connectors   — the user-secrets manager (design §3): a write-only connector list + add flow.
  //                    The credential crosses connectProvider ONCE; a row shows only fingerprint/hint.
  //   • Connections  — the gateway/platform endpoint status, read-only + honest (real health, no fake
  //                    controls per P-D6).
  //
  // Both app entry points open the SAME surface, deep-linking to a section: settings-open → Appearance,
  // user-settings-open → Agents. Token-driven: the sheet chrome + rail come from the primitive's
  // @eden/theme derivation; this component's own content styles bridge the generated role tokens to the
  // app's --eden-app-* / --color-* / --space-* / --font-size-* vocabulary (the same math-sourced bridge
  // the create flow's token-bridge comment names — one hue source, no hand-set hex/px on a painted role).
  import type { Theme } from '@eden/theme';
  import { SettingsSurface as SettingsSheet, type SettingsSection } from '@eden/primitives';
  import type { AgentConfigView } from '$lib/gateway/types';
  import { AGENT_TYPES, type AgentTypeDescriptor } from '$lib/workspace/agentWorkspace';
  import { currentUser } from '$lib/platform/currentUser.svelte';
  import { themePreference, type ThemePreference } from '$lib/theme/themePreference.svelte';
  import ConnectorsSection from './connectors/ConnectorsSection.svelte';
  import type { ConnectorKind, ConnectorView, ScopeInput } from './connectors/connectors';

  // The configuration seam is injected as callbacks (the host wires them to its GatewayClient), so this
  // component stays decoupled from the gateway value layer — the same seam the create flow uses. When
  // they are absent the Agents section degrades to read-only "inherit" defaults (graceful, P-D6).
  interface SaveBody {
    model: string;
    toolGrants: string[];
    sandboxPosture: string;
  }
  let {
    open = $bindable(false),
    section = $bindable<string>('appearance'),
    theme,
    loadConfigs,
    saveConfig,
    loadConnectors,
    connectProvider,
    disconnectConnector,
    gatewayHealthy = null,
    platformSignedIn = false,
    gatewayLabel = 'gateway',
    platformLabel = 'platform',
  }: {
    open?: boolean;
    section?: string;
    theme?: Theme;
    loadConfigs?: () => Promise<AgentConfigView[]>;
    saveConfig?: (agentType: string, body: SaveBody) => Promise<AgentConfigView>;
    // The Connectors data seam (design §3.1), injected the same way as loadConfigs/saveConfig. The
    // credential crosses connectProvider ONCE; a ConnectorView NEVER carries the value. Absent ⇒ the
    // Connectors section degrades read-only (graceful, P-D6).
    loadConnectors?: () => Promise<ConnectorView[]>;
    connectProvider?: (
      kind: ConnectorKind,
      credential: string,
      scope: ScopeInput,
    ) => Promise<ConnectorView>;
    disconnectConnector?: (id: string) => Promise<void>;
    gatewayHealthy?: boolean | null;
    platformSignedIn?: boolean;
    gatewayLabel?: string;
    platformLabel?: string;
  } = $props();

  // The four sections, in §7 order. The rail renders these mono labels; the content snippet keys off the
  // active id (deep-linked from the two entry points).
  const SECTIONS: readonly SettingsSection[] = [
    { id: 'profile', label: 'Profile' },
    { id: 'appearance', label: 'Appearance' },
    { id: 'agents', label: 'Agents' },
    // Connectors (design §3.1) — the user-secrets manager: connect Eden to the tools agents use.
    // Sits after Agents, before the read-only Connections catch-all.
    { id: 'connectors', label: 'Connectors' },
    { id: 'connections', label: 'Connections' },
  ];

  // ── Appearance: the colour-mode control, a thin view over the REAL themePreference store ──.
  // The store speaks lowercase ('light'|'dark'|'system'); the control's user-visible copy is capitalized.
  // Setting it rethemes LIVE (the store persists + reflects onto <html data-theme> in one step).
  type ColorMode = 'System' | 'Light' | 'Dark';
  const COLOR_MODES: readonly ColorMode[] = ['System', 'Light', 'Dark'];
  const modeToPreference = (mode: ColorMode): ThemePreference =>
    mode.toLowerCase() as ThemePreference;
  const preferenceToMode = (preference: ThemePreference): ColorMode =>
    (preference.charAt(0).toUpperCase() + preference.slice(1)) as ColorMode;
  const colorMode = $derived<ColorMode>(preferenceToMode(themePreference.value));
  function chooseColorMode(mode: ColorMode): void {
    themePreference.set(modeToPreference(mode));
  }

  // ── Profile: the platform identity, read-only (the shell restores currentUser from the token). ──.
  const profile = $derived(currentUser.user);

  // ── Agents: the editable per-agent-type draft state (unchanged wire shape from the legacy modal). ──.
  const agentTypes = $derived<AgentTypeDescriptor[]>(Object.values(AGENT_TYPES));
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

  /** Load the saved per-agent-type configurations into the drafts (an agent type with no saved config
   *  keeps its empty/inherit draft). */
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
   *  then reflect the server-normalized result back into the draft. The PUT body is EXACTLY
   *  {model, toolGrants[], sandboxPosture} — the shape the e2e pins. */
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

  /** Clear a draft's saved/error confirmation once the user edits a field, so the "✓ saved" badge never
   *  lingers next to a now-dirty, unsaved draft. */
  function markDirty(agentTypeId: string): void {
    const draft = drafts[agentTypeId];
    if (draft && draft.status !== 'idle' && draft.status !== 'saving') {
      draft.status = 'idle';
      draft.message = undefined;
    }
  }

  // ── Connections: the real, read-only endpoint status (honest — no fake controls, P-D6). ──.
  const gatewayState = $derived<'up' | 'down' | 'unknown'>(
    gatewayHealthy === null ? 'unknown' : gatewayHealthy ? 'up' : 'down',
  );
</script>

<SettingsSheet
  sections={SECTIONS}
  bind:active={section}
  bind:open
  {theme}
  title="Settings"
  data-testid="settings-surface"
>
  {#snippet content(active)}
    {#if active === 'profile'}
      <!-- PROFILE — the platform identity, read-only (P-D6: honest, no fake controls). -->
      <section class="pane" data-testid="settings-panel-profile">
        <header class="pane__intro">
          <h3 class="pane__title">Profile</h3>
          <p class="pane__subtitle">Your Eden identity, as the platform knows it.</p>
        </header>
        {#if profile}
          <dl class="rows" data-testid="settings-profile">
            <dt>Name</dt>
            <dd><span class="val">{profile.name}</span></dd>
            <dt>Email</dt>
            <dd><code class="mono">{profile.email}</code></dd>
            {#if profile.organization}
              <dt>Organization</dt>
              <dd><span class="val">{profile.organization.name}</span></dd>
            {/if}
            {#if profile.role}
              <dt>Role</dt>
              <dd><code class="mono">{profile.role}</code></dd>
            {/if}
          </dl>
        {:else}
          <p class="quiet" data-testid="settings-profile-signed-out">
            You are not signed in. Sign in to see your platform identity here.
          </p>
        {/if}
      </section>
    {:else if active === 'appearance'}
      <!-- APPEARANCE — the colour mode, driving the REAL themePreference store (live retheme). -->
      <section class="pane" data-testid="settings-panel-appearance">
        <header class="pane__intro">
          <h3 class="pane__title">Appearance</h3>
          <p class="pane__subtitle">Choose the colour mode. System follows your device.</p>
        </header>
        <div class="field" data-testid="settings-colormode" aria-label="Colour mode">
          <span class="field__label">Colour mode</span>
          <div class="seg" role="radiogroup" aria-label="Colour mode">
            {#each COLOR_MODES as mode (mode)}
              <button
                type="button"
                class="seg__opt"
                class:seg__opt--on={colorMode === mode}
                data-testid="settings-colormode-{mode.toLowerCase()}"
                role="radio"
                aria-checked={colorMode === mode}
                onclick={() => chooseColorMode(mode)}
              >
                {mode}
              </button>
            {/each}
          </div>
          <p class="field__hint">
            System follows your device's appearance{colorMode === 'System' ? ' (active).' : '.'}
          </p>
        </div>
      </section>
    {:else if active === 'agents'}
      <!-- AGENTS — the per-agent-type default configuration editor (GET/PUT /agent-configs). The
           testids + the PUT wire shape are unchanged from the legacy modal (the e2e pins them). -->
      <section class="pane" data-testid="settings-panel-agents">
        <header class="pane__intro">
          <h3 class="pane__title">Agent defaults</h3>
          <p class="pane__subtitle">
            The out-of-the-box configuration each agent type starts from.
          </p>
        </header>

        {#if loadError}
          <p class="load-error" data-testid="settings-load-error" role="alert">{loadError}</p>
        {/if}

        <ul class="agents" role="list">
          {#each agentTypes as agentType (agentType.id)}
            {@const draft = drafts[agentType.id]}
            <li class="agent" data-testid="agent-type-config" data-agent-type={agentType.id}>
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
                      class="cfg-field cfg-field--editable"
                      type="text"
                      bind:value={draft.model}
                      oninput={() => markDirty(agentType.id)}
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
                      class="cfg-field cfg-field--editable"
                      type="text"
                      bind:value={draft.grants}
                      oninput={() => markDirty(agentType.id)}
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
                      class="cfg-field cfg-field--select"
                      bind:value={draft.posture}
                      onchange={() => markDirty(agentType.id)}
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
                      <span
                        class="save-status save-status--ok"
                        role="status"
                        data-testid="agent-type-config-saved"
                      >
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
      </section>
    {:else if active === 'connectors'}
      <!-- CONNECTORS — the user-secrets manager (design §3): the write-only connector list + add flow.
           Sits ABOVE the Connections catch-all. The section content lives app-local under
           settings/connectors/ (P-D7 promotion candidates), composing @eden/primitives only. -->
      <section class="pane" data-testid="settings-panel-connectors">
        <header class="pane__intro">
          <h3 class="pane__title">Connectors</h3>
          <p class="pane__subtitle">Connect Eden to the tools your agents use.</p>
        </header>
        <ConnectorsSection
          {open}
          {theme}
          {loadConnectors}
          {connectProvider}
          {disconnectConnector}
        />
      </section>
    {:else}
      <!-- CONNECTIONS — the real endpoint status, read-only + honest (P-D6: no fake controls). -->
      <section class="pane" data-testid="settings-panel-connections">
        <header class="pane__intro">
          <h3 class="pane__title">Connections</h3>
          <p class="pane__subtitle">Where Eden is talking, right now. Read-only.</p>
        </header>
        <dl class="rows" data-testid="settings-connections">
          <dt>Agent gateway</dt>
          <dd>
            <span class="conn conn--{gatewayState}" data-testid="settings-connection-gateway">
              {gatewayState === 'unknown'
                ? 'checking…'
                : gatewayState === 'up'
                  ? 'connected'
                  : 'unreachable'}
            </span>
            <code class="mono endpoint">{gatewayLabel}</code>
          </dd>
          <dt>Platform</dt>
          <dd>
            <span
              class="conn conn--{platformSignedIn ? 'up' : 'unknown'}"
              data-testid="settings-connection-platform"
            >
              {platformSignedIn ? 'signed in' : 'signed out'}
            </span>
            <code class="mono endpoint">{platformLabel}</code>
          </dd>
        </dl>
      </section>
    {/if}
  {/snippet}
</SettingsSheet>

<style>
  /* ── token bridge ─────────────────────────────────────────────────────────.
     The SettingsSurface organism owns the sheet / rail / heading appearance (all @eden/theme-derived,
     no literals). This subtree styles only the per-section CONTENT, bridging the generated @eden/theme
     role tokens to the app's --eden-app-* / --color-* vocabulary — the same math-sourced bridge the
     app's overlays + create flow use. One hue source, no hand-set hex or px on a painted role. */
  .pane {
    display: flex;
    flex-direction: column;
    gap: var(--space-4, 16px);
    min-inline-size: 0;
    color: var(--foreground, var(--color-on-surface));
    font-size: var(--font-size-body-large, 15px);
  }
  .pane__intro {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .pane__title {
    margin: 0;
    font-size: var(--font-size-title, 20px);
    font-weight: 600;
    color: var(--foreground, var(--color-on-surface));
  }
  .pane__subtitle {
    margin: 0;
    font-size: var(--font-size-caption, 12px);
    color: var(--muted-foreground, var(--color-outline));
  }
  .quiet {
    margin: 0;
    color: var(--muted-foreground, var(--color-outline));
    font-size: var(--font-size-label, 13px);
  }

  /* ── definition rows (Profile / Connections) ── */
  .rows {
    margin: 0;
    display: grid;
    grid-template-columns: minmax(7rem, max-content) 1fr;
    gap: var(--space-2, 8px) var(--space-4, 16px);
    align-items: baseline;
  }
  .rows dt {
    color: var(--muted-foreground, var(--color-outline));
    font-size: var(--font-size-caption, 12px);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }
  .rows dd {
    margin: 0;
    display: flex;
    align-items: center;
    gap: var(--space-3, 12px);
    flex-wrap: wrap;
    color: var(--foreground, var(--color-on-surface));
  }
  .val {
    font-size: var(--font-size-body-large, 15px);
  }
  .mono {
    font-family: var(--font-code, monospace);
    font-size: var(--font-size-label, 13px);
    color: var(--foreground, var(--color-on-surface));
  }

  /* ── Appearance: the colour-mode segmented control ── */
  .field {
    display: flex;
    flex-direction: column;
    gap: var(--space-2, 8px);
  }
  .field__label {
    font-size: var(--font-size-caption, 12px);
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--muted-foreground, var(--color-outline));
  }
  .field__hint {
    margin: 0;
    font-size: var(--font-size-caption, 12px);
    color: var(--muted-foreground, var(--color-outline));
  }
  /* The shadcn segmented control — a --surface-muted trough, --radius-md geometry, a raised --card
     selected pill with a subtle shadow. */
  .seg {
    display: inline-flex;
    gap: var(--space-1, 4px);
    padding: var(--space-1, 4px);
    background: var(
      --surface-muted,
      color-mix(in oklab, var(--color-on-surface) 4%, var(--color-surface))
    );
    border: 1px solid var(--border, var(--color-outline));
    border-radius: var(--radius-md, 8px);
    inline-size: fit-content;
  }
  .seg__opt {
    padding: var(--space-2, 8px) var(--space-4, 16px);
    min-block-size: 44px;
    background: none;
    border: 1px solid transparent;
    border-radius: var(--radius-sm, 6px);
    color: var(--muted-foreground, var(--color-outline));
    font-family: var(--font-code, monospace);
    font-size: var(--font-size-label, 14px);
    font-weight: 500;
    cursor: pointer;
    /* W5: the colour-mode segmented control rides the theme motion tokens. */
    transition:
      color var(--duration-short-2, 120ms) var(--ease-standard, ease),
      background var(--duration-short-2, 120ms) var(--ease-standard, ease),
      border-color var(--duration-short-2, 120ms) var(--ease-standard, ease);
  }
  .seg__opt:hover {
    color: var(--foreground, var(--color-on-surface));
  }
  .seg__opt:focus-visible {
    outline: 2px solid var(--ring, var(--color-primary));
    outline-offset: 1px;
  }
  .seg__opt--on {
    background: var(--card, var(--color-surface));
    border-color: var(--border, var(--color-primary));
    color: var(--foreground, var(--color-on-surface));
    box-shadow: var(--shadow-xs);
  }

  /* ── Agents: the per-agent-type cards ── */
  .agents {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-4, 16px);
  }
  /* Each agent config is a shadcn Card — a --card surface, 1px --border hairline, --radius-lg
     corners, and the resting --shadow-xs. */
  .agent {
    display: flex;
    flex-direction: column;
    gap: var(--space-3, 12px);
    padding: var(--space-4, 16px);
    background: var(--card, var(--color-surface));
    border: 1px solid var(--border, var(--color-outline));
    border-radius: var(--radius-lg, 6px);
    box-shadow: var(--shadow-xs);
  }
  .agent__head {
    display: flex;
    align-items: center;
    gap: var(--space-3, 12px);
    padding-block-end: var(--space-2, 8px);
    border-block-end: 1px solid var(--border, var(--color-outline));
  }
  .agent__glyph {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    inline-size: var(--space-7, 28px);
    block-size: var(--space-7, 28px);
    flex: none;
    border: 1px solid var(--border, var(--color-outline));
    border-radius: var(--radius-sm, 4px);
    background: var(
      --surface-muted,
      color-mix(in oklab, var(--color-on-surface) 4%, var(--color-surface))
    );
    color: var(--color-primary);
    font-size: var(--font-size-body-large, 15px);
  }
  .agent__label {
    font-size: var(--font-size-body-large, 15px);
    font-weight: 600;
    color: var(--foreground, var(--color-on-surface));
  }
  /* W5: the config grid previously used a `gap: 1px` over a line-coloured background to draw the cell
     separators — but a `max-content` key column leaves a wide strip of that background exposed between
     the label and value columns (the "odd darker column band"). Draw the separators as real cell
     borders instead (gap: 0), so every cell fills its track flush and no band shows in either theme.
     The key column is a fixed fraction, not `max-content`, so the seam sits at a stable position. */
  .agent__grid {
    margin: 0;
    display: grid;
    grid-template-columns: minmax(8rem, 0.4fr) 1fr;
    gap: 0;
    border: 1px solid var(--border, var(--color-outline));
    border-radius: var(--radius-md, 4px);
    overflow: hidden;
  }
  .row {
    display: contents;
  }
  .row__key,
  .row__val {
    background: var(--card, var(--color-surface));
    padding: var(--space-2, 8px) var(--space-3, 12px);
    min-inline-size: 0;
    border-block-start: 1px solid var(--border, var(--color-outline));
  }
  /* the first row (Panel widgets · key + val) sits flush under the card border — no top rule. */
  .row:first-child .row__key,
  .row:first-child .row__val {
    border-block-start: none;
  }
  .row__key {
    font-size: var(--font-size-label, 13px);
    color: var(--muted-foreground, var(--color-outline));
    white-space: nowrap;
    background: var(--surface-muted, var(--color-surface));
    border-inline-end: 1px solid var(--border, var(--color-outline));
  }
  .row__val {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--space-2, 8px);
    color: var(--foreground, var(--color-on-surface));
    overflow-wrap: anywhere;
  }
  .row--wide .row__val {
    align-items: flex-start;
  }
  .unset {
    font-size: var(--font-size-label, 13px);
    color: var(--muted-foreground, var(--color-outline));
    font-style: italic;
  }
  .chips {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2, 8px);
  }
  /* Shadcn outline badges — a --surface-muted fill, a 1px --border, --radius-sm corners. */
  .chip {
    display: inline-flex;
    align-items: center;
    padding: 2px var(--space-2, 8px);
    border: 1px solid var(--border, var(--color-outline));
    border-radius: var(--radius-sm, 4px);
    background: var(
      --surface-muted,
      color-mix(in oklab, var(--color-on-surface) 4%, var(--color-surface))
    );
    color: var(--muted-foreground, var(--color-on-surface));
    font-family: var(--font-code, monospace);
    font-size: var(--font-size-caption, 12px);
    letter-spacing: 0.02em;
  }
  /* Shadcn input geometry — a 1px --input edge, --radius-sm corners, a --ring focus halo. */
  .cfg-field {
    flex: 1 1 14rem;
    min-inline-size: 0;
    padding: var(--space-2, 8px) var(--space-3, 12px);
    background: var(--background, var(--color-surface));
    color: var(--foreground, var(--color-on-surface));
    border: 1px solid var(--input, var(--color-outline));
    border-radius: var(--radius-sm, 4px);
    font-family: var(--font-code, monospace);
    font-size: var(--font-size-label, 13px);
    transition:
      border-color var(--duration-short-2, 120ms) var(--ease-standard, ease),
      box-shadow var(--duration-short-2, 120ms) var(--ease-standard, ease);
  }
  .cfg-field:focus-visible {
    outline: none;
    border-color: var(--ring, var(--color-primary));
    box-shadow: 0 0 0 3px color-mix(in oklab, var(--ring, var(--color-primary)) 30%, transparent);
  }
  .cfg-field:disabled {
    color: var(--muted-foreground, var(--color-outline));
    cursor: not-allowed;
    opacity: 0.7;
  }
  .cfg-field--select {
    flex: 0 0 auto;
    cursor: pointer;
  }
  .cfg-field--select:disabled {
    cursor: not-allowed;
  }
  .agent__save {
    align-items: center;
  }
  /* The Save action gets the shadcn solid-button geometry — a solid --primary fill, --radius-md,
     the --shadow-sm lift. */
  .save-btn {
    padding: var(--space-2, 8px) var(--space-4, 16px);
    border: 1px solid var(--primary, var(--color-primary));
    border-radius: var(--radius-md, 6px);
    background: var(--primary, var(--color-primary));
    color: var(--primary-foreground, var(--color-on-primary));
    font-family: var(--font-code, monospace);
    font-size: var(--font-size-label, 13px);
    font-weight: 600;
    cursor: pointer;
    box-shadow: var(--shadow-sm);
    transition:
      filter var(--duration-short-2, 120ms) var(--ease-standard, ease),
      box-shadow var(--duration-short-2, 120ms) var(--ease-standard, ease);
  }
  .save-btn:hover:not(:disabled) {
    filter: brightness(1.08);
    box-shadow: var(--shadow-md);
  }
  .save-btn:focus-visible {
    outline: 2px solid var(--ring, var(--color-primary));
    outline-offset: 2px;
  }
  .save-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .save-status {
    font-size: var(--font-size-caption, 12px);
    font-family: var(--font-code, monospace);
  }
  .save-status--ok {
    color: var(--color-success, var(--color-primary));
  }
  .save-status--error {
    color: var(--destructive, var(--color-error));
  }
  .load-error {
    margin: 0;
    padding: var(--space-2, 8px) var(--space-3, 12px);
    border: 1px solid color-mix(in oklab, var(--color-error) 30%, transparent);
    border-radius: var(--radius-md, 6px);
    background: var(--destructive-surface);
    color: var(--destructive, var(--color-error));
    font-size: var(--font-size-label, 13px);
  }

  /* ── Connections: the read-only status pills ── */
  /* Shadcn outline status pills — a --surface-muted fill, a 1px --border, --radius-sm corners. */
  .conn {
    display: inline-flex;
    align-items: center;
    gap: 0.35em;
    padding: 0.15rem 0.6rem;
    border-radius: var(--radius-sm);
    font-family: var(--font-code, monospace);
    font-size: var(--font-size-caption, 12px);
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    background: var(--surface-muted);
    border: 1px solid var(--border);
    color: var(--muted-foreground, var(--color-outline));
  }
  .conn--up {
    background: var(--success-surface);
    border-color: color-mix(in oklab, var(--color-success) 30%, transparent);
    color: var(--color-success, var(--color-primary));
  }
  .conn--down {
    background: var(--destructive-surface);
    border-color: color-mix(in oklab, var(--color-error) 30%, transparent);
    color: var(--destructive, var(--color-error));
  }
  .endpoint {
    color: var(--muted-foreground, var(--color-outline));
  }

  @media (prefers-reduced-motion: reduce) {
    .seg__opt {
      transition: none;
    }
    .save-btn {
      transition: none;
    }
  }
</style>
