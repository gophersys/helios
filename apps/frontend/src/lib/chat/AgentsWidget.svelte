<script lang="ts">
  // The SUB-AGENTS widget — the delegated agents the supervisor spawned, derived LIVE from its
  // tool-call stream: each `Task` tool call is one sub-agent (its args summary is the brief). The
  // list fills in the instant the supervisor delegates, and each row's status dot tracks the
  // delegated run (running → ok / error / denied). Fully token-driven from @eden/theme.
  import type { Theme } from '@eden/theme';
  import type { ChatSession, Entry } from '$lib/gateway/session.svelte';
  import PanelWidget from './PanelWidget.svelte';

  let { session, theme }: { session: ChatSession; theme?: Theme } = $props();

  interface SubAgent {
    callId: string;
    brief: string;
    status: 'running' | 'ok' | 'error' | 'denied';
  }

  // One delegated sub-agent per `Task` tool entry, keyed by callId, in spawn order. The args summary
  // is the sub-agent's brief; an empty/redacted summary falls back to a neutral label.
  const isTask = (entry: Entry): entry is Extract<Entry, { role: 'tool' }> =>
    entry.role === 'tool' && entry.tool.name === 'Task';

  const subAgents = $derived.by<SubAgent[]>(() =>
    session.entries.filter(isTask).map((entry) => ({
      callId: entry.tool.callId,
      brief: (entry.tool.argsSummary ?? '').trim() || 'delegated task',
      status: entry.tool.status,
    })),
  );
</script>

<div class="agents" data-testid="agents-widget" data-count={subAgents.length}>
  <PanelWidget title="Sub-agents" count={subAgents.length} {theme}>
    {#snippet children()}
      {#if subAgents.length === 0}
        <p class="agents__empty" data-testid="agents-empty">
          No sub-agents yet — they appear as the supervisor delegates.
        </p>
      {:else}
        <ul class="agents__list" role="list">
          {#each subAgents as agent (agent.callId)}
            <li class="agent" data-testid="agents-row" data-status={agent.status}>
              <span class="agent__dot" data-status={agent.status} aria-hidden="true"></span>
              <span class="agent__brief" title={agent.brief}>{agent.brief}</span>
              <span class="agent__status" data-testid="agents-row-status">{agent.status}</span>
            </li>
          {/each}
        </ul>
      {/if}
    {/snippet}
  </PanelWidget>
</div>

<style>
  .agents {
    display: flex;
    flex-direction: column;
    gap: var(--space-2, 8px);
    min-block-size: 0;
  }
  .agents__empty {
    font-size: var(--font-size-caption, 12px);
    color: var(--eden-app-muted);
    margin: 0;
  }
  .agents__list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
    overflow-y: auto;
  }
  .agent {
    display: flex;
    align-items: center;
    gap: var(--space-2, 8px);
    padding: var(--space-1, 4px) var(--space-2, 8px);
    border-radius: var(--eden-app-radius, 4px);
    font-family: var(--font-code);
    font-size: var(--font-size-caption, 12px);
    animation: agent-in 240ms ease-out;
  }
  .agent:hover {
    background: var(--eden-app-panel-bg);
  }
  .agent__dot {
    inline-size: 7px;
    block-size: 7px;
    border-radius: 50%;
    flex: none;
    background: var(--eden-app-muted);
  }
  .agent__dot[data-status='running'] {
    background: var(--eden-app-accent);
    animation: agent-pulse 1.2s ease-in-out infinite;
  }
  .agent__dot[data-status='ok'] {
    background: var(--color-info);
  }
  .agent__dot[data-status='error'],
  .agent__dot[data-status='denied'] {
    background: var(--color-error);
  }
  .agent__brief {
    color: var(--eden-app-fg);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    flex: 1;
    min-inline-size: 0;
  }
  .agent__status {
    flex: none;
    font-size: 10px;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--eden-app-muted);
  }
  .agent[data-status='running'] .agent__status {
    color: var(--eden-app-accent);
  }
  .agent[data-status='error'] .agent__status,
  .agent[data-status='denied'] .agent__status {
    color: var(--color-error);
  }
  @keyframes agent-in {
    from {
      opacity: 0;
      transform: translateY(-3px);
    }
  }
  @keyframes agent-pulse {
    50% {
      opacity: 0.4;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .agent {
      animation: none;
    }
    .agent__dot[data-status='running'] {
      animation: none;
    }
  }
</style>
