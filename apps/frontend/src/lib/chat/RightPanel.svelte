<script lang="ts">
  // The agent-workspace RIGHT PANEL — the third region of the Eden workspace (nav · conversation ·
  // PANEL). Its widget stack is chosen by the session's AGENT TYPE (the registry in
  // agentWorkspace.ts): an implementer shows its generated files; an architect would show docs +
  // decisions; a supervisor its sub-agent tree — "the right side changes with the agent type".
  // Every widget consumes the live session, so the panel updates the instant new events arrive.
  import type { Theme } from '@eden/theme';
  import type { ChatSession } from '$lib/gateway/session.svelte';
  import type { AgentTypeDescriptor } from '$lib/workspace/agentWorkspace';
  import WorkspaceWidget from './WorkspaceWidget.svelte';
  import FileTreeWidget from './FileTreeWidget.svelte';
  import DocumentsWidget from './DocumentsWidget.svelte';
  import DecisionsWidget from './DecisionsWidget.svelte';
  import AgentsWidget from './AgentsWidget.svelte';
  import ProgressWidget from './ProgressWidget.svelte';

  let {
    session,
    agentType,
    theme,
  }: { session: ChatSession; agentType: AgentTypeDescriptor; theme: Theme } = $props();
</script>

<aside class="panel" data-testid="agent-panel" data-agent-type={agentType.id} aria-label="agent workspace panel">
  <header class="panel__head">
    <span class="panel__type" data-testid="panel-agent-type">
      <span class="panel__glyph" aria-hidden="true">{agentType.glyph}</span>
      {agentType.label}
    </span>
    <code class="panel__harness">{session.harness}</code>
  </header>

  <div class="panel__widgets">
    {#each agentType.widgets as widget (widget)}
      {#if widget === 'workspace'}
        <WorkspaceWidget entries={session.entries} {theme} />
      {:else if widget === 'files'}
        <FileTreeWidget {session} {theme} />
      {:else if widget === 'documents'}
        <DocumentsWidget {session} {theme} />
      {:else if widget === 'decisions'}
        <DecisionsWidget {session} {theme} />
      {:else if widget === 'agents'}
        <AgentsWidget {session} {theme} />
      {:else if widget === 'progress'}
        <ProgressWidget {session} {theme} />
      {:else}
        <!-- any future widget id falls back to a labeled placeholder until its component lands -->
        <section class="panel__placeholder" data-testid="panel-widget-placeholder" data-widget={widget}>
          <span class="panel__placeholder-title">{widget}</span>
          <span class="panel__placeholder-note">coming online</span>
        </section>
      {/if}
    {/each}
  </div>
</aside>

<style>
  .panel {
    display: flex;
    flex-direction: column;
    gap: var(--space-4, 16px);
    padding: var(--space-4, 16px);
    background: var(--eden-app-panel-bg);
    border-inline-start: 1px solid var(--eden-app-line);
    overflow-y: auto;
    min-inline-size: 0;
  }
  .panel__head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-2, 8px);
    padding-block-end: var(--space-2, 8px);
    border-block-end: 1px solid var(--eden-app-line);
  }
  .panel__type {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2, 8px);
    font-weight: 600;
    font-size: var(--font-size-label, 13px);
    color: var(--eden-app-fg);
  }
  .panel__glyph {
    color: var(--eden-app-accent);
    font-size: var(--font-size-body-large, 16px);
  }
  .panel__harness {
    font-family: var(--font-code);
    font-size: var(--font-size-caption, 12px);
    color: var(--eden-app-muted);
  }
  .panel__widgets {
    display: flex;
    flex-direction: column;
    gap: var(--space-5, 20px);
    min-block-size: 0;
  }
  .panel__placeholder {
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: var(--space-3, 12px);
    border: 1px dashed var(--eden-app-line);
    border-radius: var(--eden-app-radius, 4px);
  }
  .panel__placeholder-title {
    font-family: var(--font-code);
    font-size: var(--font-size-caption, 12px);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--eden-app-muted);
  }
  .panel__placeholder-note {
    font-size: var(--font-size-caption, 12px);
    color: var(--eden-app-muted);
    opacity: 0.7;
  }
</style>
