<script lang="ts">
  // The SESSIONS page — the agent sessions Eden is running, rendered inside the app shell. It reads
  // the gateway's session list (GET /sessions → orchestrator.Agent records) and lists each with its
  // status, agent template, and age; opening one drops into the full-screen chat workspace. A real
  // backend connection, the management counterpart to the chat workspace.
  import { GatewayClient, GatewayError } from '$lib/gateway/client';
  import { resolveGatewayUrl } from '$lib/gateway/configuration';
  import { edenLightTheme, edenDarkTheme } from '$lib/theme/edenTheme';
  import { themePreference } from '$lib/theme/themePreference.svelte';
  import { goto } from '$app/navigation';
  import { Button, EmptyState } from '@eden/primitives';
  import type { AgentView } from '$lib/gateway/types';

  const client = new GatewayClient(resolveGatewayUrl());
  const theme = $derived(
    themePreference.resolvedMode === 'dark' ? edenDarkTheme : edenLightTheme,
  );

  let sessions = $state<AgentView[]>([]);
  let listError = $state<string | null>(null);
  let loaded = $state(false);

  async function refresh(): Promise<void> {
    try {
      const page = await client.listSessions();
      sessions = page.sessions;
      listError = null;
    } catch (cause) {
      listError = cause instanceof GatewayError ? `${cause.kind}: ${cause.message}` : String(cause);
    } finally {
      loaded = true;
    }
  }

  $effect(() => {
    void refresh();
  });

  function openSession(session: AgentView): void {
    // Open the session's Build view IN-SHELL (doc 17 §5): the global, unscoped Build surface
    // addressed by the session id.
    void goto(`/sessions/${encodeURIComponent(session.id)}`);
  }
  function shortId(id: string): string {
    return id.length > 12 ? `${id.slice(0, 10)}…` : id;
  }
  function relativeTime(iso: string): string {
    const then = Date.parse(iso);
    if (Number.isNaN(then)) return '—';
    const seconds = Math.max(0, Math.round((Date.now() - then) / 1000));
    if (seconds < 60) return `${seconds}s ago`;
    const minutes = Math.round(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.round(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    return `${Math.round(hours / 24)}d ago`;
  }
</script>

<svelte:head><title>Eden — Sessions</title></svelte:head>

<div class="page" data-testid="sessions-page">
  <header class="page__head">
    <h1 class="page__title">Sessions</h1>
    <span class="page__action">
      <Button variant="primary" {theme} onclick={() => goto('/chat?new=1')}>＋ New session</Button>
    </span>
  </header>

  <div class="page__body">
    {#if listError}
      <p class="page__error" data-testid="sessions-error">{listError}</p>
    {/if}

    {#if loaded && sessions.length === 0}
      <!-- W4: the empty state is a product surface (@eden/primitives EmptyState) — serif headline ·
           body · primary action · a CONTENT SLOT pointing at where sessions come from (a project's
           build). The `sessions-empty` testid stays on the rendered EmptyState root (DO-NOT-BREAK). -->
      <div class="page__empty" data-testid="sessions-empty">
        <EmptyState
          {theme}
          headline="No sessions yet"
          body="Start a project and the agent session that builds it appears here."
        >
          {#snippet action()}
            <Button variant="primary" {theme} onclick={() => goto('/chat?new=1')}>＋ New session</Button>
          {/snippet}
          {#snippet content()}
            <p class="pointer">
              Sessions are born from a build. Head to
              <button type="button" class="pointer__link" data-testid="sessions-to-projects" onclick={() => goto('/projects')}>Projects</button>
              and start one.
            </p>
          {/snippet}
        </EmptyState>
      </div>
    {:else if loaded}
      <table class="sessions" data-testid="sessions-table">
        <thead>
          <tr>
            <th>Session</th>
            <th>Agent</th>
            <th>Status</th>
            <th>Created</th>
            <th class="sessions__actions-col"></th>
          </tr>
        </thead>
        <tbody>
          {#each sessions as session (session.id)}
            <tr data-testid="session-row" data-session-id={session.id}>
              <td><code class="sessions__id">{shortId(session.id)}</code></td>
              <td>{session.template}</td>
              <td><span class="status status--{session.status}">{session.status}</span></td>
              <td class="sessions__age">{relativeTime(session.createdAt)}</td>
              <td class="sessions__actions-col">
                <button class="open" onclick={() => openSession(session)}>Open →</button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  </div>
</div>

<style>
  .page {
    display: flex;
    flex-direction: column;
    min-block-size: 100%;
  }
  .page__head {
    display: flex;
    align-items: center;
    gap: var(--space-4, 16px);
    padding: var(--space-5, 20px) var(--space-6, 24px);
    border-block-end: 1px solid var(--eden-app-line);
  }
  .page__title {
    margin: 0;
    font-size: var(--font-size-title, 23px);
  }
  .page__action {
    margin-inline-start: auto;
  }
  .page__body {
    flex: 1;
    padding: var(--space-6, 24px);
  }
  .page__error {
    color: var(--color-error);
    font-size: var(--font-size-label, 13px);
  }
  /* W4: the wrapper only vertically positions the EmptyState (which owns its own reading measure,
     centering, headline/body voices, and content slot). No hand-set painted roles here. */
  .page__empty {
    margin-block-start: 10vh;
  }
  .pointer {
    margin: 0;
    color: var(--eden-app-muted, var(--color-outline));
    font-size: var(--font-size-label, 13px);
  }
  .pointer__link {
    padding: 0;
    background: none;
    border: none;
    color: var(--color-primary);
    font: inherit;
    text-decoration: underline;
    cursor: pointer;
  }
  .pointer__link:focus-visible {
    outline: 2px solid var(--color-primary);
    outline-offset: 2px;
  }
  .sessions {
    inline-size: 100%;
    max-inline-size: 64rem;
    border-collapse: collapse;
    font-size: var(--font-size-body, 15px);
  }
  .sessions th {
    text-align: start;
    padding: var(--space-2, 8px) var(--space-3, 12px);
    color: var(--eden-app-muted);
    font-weight: 600;
    font-size: var(--font-size-label, 13px);
    border-block-end: 1px solid var(--eden-app-line);
  }
  .sessions td {
    padding: var(--space-3, 12px);
    border-block-end: 1px solid var(--eden-app-line);
    vertical-align: middle;
  }
  .sessions__id {
    color: var(--eden-app-muted);
    font-family: var(--font-code);
  }
  .sessions__age {
    color: var(--eden-app-muted);
  }
  .sessions__actions-col {
    text-align: end;
  }
  .status {
    display: inline-block;
    padding: 1px var(--space-2, 8px);
    border-radius: 999px;
    font-size: var(--font-size-caption, 12px);
    font-weight: 600;
    background: color-mix(in oklab, var(--eden-app-fg) 10%, transparent);
    color: var(--eden-app-fg);
  }
  .status--running {
    background: color-mix(in oklab, var(--color-info) 22%, transparent);
  }
  .status--completed {
    background: color-mix(in oklab, var(--color-success, var(--eden-app-accent)) 22%, transparent);
  }
  .status--failed {
    background: color-mix(in oklab, var(--color-error) 22%, transparent);
  }
  .open {
    border: 1px solid var(--eden-app-line);
    background: none;
    color: var(--eden-app-fg);
    padding: var(--space-1, 4px) var(--space-3, 12px);
    border-radius: var(--eden-app-radius, 8px);
    cursor: pointer;
    font: inherit;
    transition: border-color 120ms ease;
  }
  .open:hover {
    border-color: var(--eden-app-accent);
  }
</style>
