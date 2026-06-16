<script lang="ts">
  // The PROJECTS DASHBOARD — Eden's home. A project is what a user builds (today each gateway
  // session stands in for a project until the persisted Project object lands). The grid shows the
  // user's projects; "＋ New project" starts the creation flow; a user-profile card is pinned at the
  // bottom and opens the tabbed Settings (its first tab is the per-agent-type default configuration).
  // Token-driven from @eden/theme; the cards/profile/settings are reusable components.
  import { GatewayClient, GatewayError } from '$lib/gateway/client';
  import { resolveGatewayUrl } from '$lib/gateway/configuration';
  import { edenTheme } from '$lib/theme/edenTheme';
  import { goto } from '$app/navigation';
  import { Button } from '@eden/primitives';
  import ProjectCard, { type ProjectSummary } from '$lib/dashboard/ProjectCard.svelte';
  import UserProfileCard from '$lib/dashboard/UserProfileCard.svelte';
  import SettingsModal from '$lib/dashboard/SettingsModal.svelte';

  const client = new GatewayClient(resolveGatewayUrl());
  const theme = edenTheme;

  let projects = $state<ProjectSummary[]>([]);
  let settingsOpen = $state(false);
  let listError = $state<string | null>(null);
  let loaded = $state(false);

  async function refresh(): Promise<void> {
    try {
      const page = await client.listSessions();
      // Map the gateway session records onto the dashboard's ProjectSummary (a session ≈ a project
      // until the persisted Project object lands).
      projects = page.sessions.map((session) => ({
        id: session.id,
        name: session.id,
        kind: session.template,
        status: session.status,
        harness: (session as { labels?: Record<string, string> }).labels?.harness,
        updatedAt: session.updatedAt,
      }));
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

  function openProject(id: string): void {
    void goto(`/chat?session=${encodeURIComponent(id)}`);
  }
  function newProject(): void {
    void goto('/chat?new=1');
  }
</script>

<svelte:head><title>Eden — Projects</title></svelte:head>

<div class="dash" data-testid="projects-dashboard">
  <header class="dash__head">
    <div class="dash__brand">
      <span class="dash__mark" aria-hidden="true">◆</span>
      <span class="dash__name">Eden</span>
    </div>
    <h1 class="dash__title">Projects</h1>
    <span class="dash__new">
      <Button variant="primary" {theme} onclick={newProject}>＋ New project</Button>
    </span>
  </header>

  <main class="dash__body">
    {#if listError}
      <p class="dash__error" data-testid="dash-error">{listError}</p>
    {/if}

    {#if loaded && projects.length === 0}
      <div class="dash__empty" data-testid="dash-empty">
        <h2>Build something with Eden</h2>
        <p>An agent will scope it with you in a few quick steps, then build it.</p>
        <Button variant="primary" {theme} onclick={newProject}>＋ New project</Button>
      </div>
    {:else}
      <ul class="dash__grid" role="list" data-testid="project-grid">
        <li>
          <button class="dash__newcard" data-testid="new-project-card" onclick={newProject}>
            <span class="dash__newcard-plus" aria-hidden="true">＋</span>
            <span class="dash__newcard-label">New project</span>
          </button>
        </li>
        {#each projects as project (project.id)}
          <li><ProjectCard {project} onOpen={() => openProject(project.id)} {theme} /></li>
        {/each}
      </ul>
    {/if}
  </main>

  <footer class="dash__footer">
    <UserProfileCard name="You" onSettings={() => (settingsOpen = true)} {theme} />
  </footer>
</div>

<SettingsModal bind:open={settingsOpen} {theme} />

<style>
  .dash {
    display: flex;
    flex-direction: column;
    height: 100vh;
    overflow: hidden;
    background: var(--eden-app-bg);
    color: var(--eden-app-fg);
  }
  .dash__head {
    display: flex;
    align-items: center;
    gap: var(--space-4, 16px);
    padding: var(--space-4, 16px) var(--space-6, 24px);
    border-block-end: 1px solid var(--eden-app-line);
  }
  .dash__brand {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2, 8px);
  }
  .dash__mark {
    color: var(--eden-app-accent);
    font-size: var(--font-size-body-large, 16px);
  }
  .dash__name {
    font-weight: 700;
  }
  .dash__title {
    margin: 0;
    font-size: var(--font-size-title, 23px);
  }
  .dash__new {
    margin-inline-start: auto;
  }
  .dash__body {
    flex: 1;
    min-block-size: 0;
    overflow-y: auto;
    padding: var(--space-6, 24px);
  }
  .dash__error {
    color: var(--color-error);
    font-size: var(--font-size-label, 13px);
  }
  .dash__empty {
    max-inline-size: 46ch;
    margin: 12vh auto 0;
    text-align: center;
    display: flex;
    flex-direction: column;
    gap: var(--space-4, 16px);
    align-items: center;
  }
  .dash__empty p {
    color: var(--eden-app-muted);
    margin: 0;
  }
  .dash__grid {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: var(--space-4, 16px);
    max-inline-size: 80rem;
  }
  .dash__newcard {
    inline-size: 100%;
    block-size: 100%;
    min-block-size: 7rem;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--space-2, 8px);
    background: none;
    border: 1.5px dashed var(--eden-app-line);
    border-radius: var(--eden-app-radius, 8px);
    color: var(--eden-app-muted);
    cursor: pointer;
    transition: border-color 140ms ease, color 140ms ease;
  }
  .dash__newcard:hover {
    border-color: var(--eden-app-accent);
    color: var(--eden-app-fg);
  }
  .dash__newcard-plus {
    font-size: var(--font-size-title, 23px);
    color: var(--eden-app-accent);
  }
  .dash__footer {
    border-block-start: 1px solid var(--eden-app-line);
    padding: var(--space-3, 12px) var(--space-6, 24px);
    background: var(--eden-app-rail-bg);
  }
  @media (prefers-reduced-motion: reduce) {
    .dash__newcard {
      transition: none;
    }
  }
</style>
