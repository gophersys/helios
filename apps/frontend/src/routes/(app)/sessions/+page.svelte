<script lang="ts">
  // The SESSIONS page — the agent sessions Eden is running, rendered inside the app shell. It reads
  // the gateway's session list (GET /sessions → orchestrator.Agent records) and lists each with its
  // status, agent template, and age; opening one drops into the full-screen chat workspace. A real
  // backend connection, the management counterpart to the chat workspace.
  import { GatewayClient, GatewayError } from '$lib/gateway/client';
  import { resolveGatewayUrl } from '$lib/gateway/configuration';
  import { edenTheme } from '$lib/theme/edenTheme';
  import { goto } from '$app/navigation';
  import { Button } from '@eden/primitives';
  import type { AgentView } from '$lib/gateway/types';

  const client = new GatewayClient(resolveGatewayUrl());
  const theme = edenTheme;

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
    void goto(`/chat?session=${encodeURIComponent(session.id)}`);
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
      <div class="page__empty" data-testid="sessions-empty">
        <h2>No sessions yet</h2>
        <p>Start a project and the agent session that builds it appears here.</p>
        <Button variant="primary" {theme} onclick={() => goto('/chat?new=1')}>＋ New session</Button
        >
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
  .page__empty {
    max-inline-size: 46ch;
    margin: 12vh auto 0;
    text-align: center;
    display: flex;
    flex-direction: column;
    gap: var(--space-4, 16px);
    align-items: center;
  }
  .page__empty p {
    color: var(--eden-app-muted);
    margin: 0;
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
