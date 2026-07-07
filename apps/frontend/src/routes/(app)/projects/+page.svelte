<script lang="ts">
  // The PROJECTS page — Eden's home, rendered inside the app shell (the sidebar provides the brand,
  // user, and Settings; this page owns its header + grid). A project is what a user builds; the grid
  // lists them, "＋ New project" starts the creation flow. Token-driven; cards are reusable components.
  import { GatewayClient, GatewayError } from '$lib/gateway/client';
  import { resolveGatewayUrl } from '$lib/gateway/configuration';
  import { edenTheme } from '$lib/theme/edenTheme';
  import { goto } from '$app/navigation';
  import { Button } from '@eden/primitives';
  import ProjectCard, { type ProjectSummary } from '$lib/dashboard/ProjectCard.svelte';

  const client = new GatewayClient(resolveGatewayUrl());
  const theme = edenTheme;

  let projects = $state<ProjectSummary[]>([]);
  let listError = $state<string | null>(null);
  let loaded = $state(false);

  async function refresh(): Promise<void> {
    try {
      const page = await client.listProjects();
      // Map the persisted ProjectViews onto the dashboard's ProjectSummary read model.
      projects = page.projects.map((project) => ({
        id: project.id,
        name: project.name,
        kind: project.kind,
        status: project.status,
        harness: project.harness,
        updatedAt: project.updatedAt,
        stacks: project.stacks,
        sessionId: project.sessionId,
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

  function openProject(project: ProjectSummary): void {
    // Open the project's Build view IN-SHELL (doc 17 §5): a persisted project maps to its own
    // /projects/<id>/build surface (which resolves its build session). A project without an id would
    // have nowhere to map — fall back to the unscoped Build view — but every ProjectSummary carries
    // an id, so this is the mapped path in practice.
    if (project.id) {
      void goto(`/projects/${encodeURIComponent(project.id)}/build`);
    } else {
      void goto('/chat');
    }
  }
  function newProject(): void {
    // "New project" opens the create flow — it lives in the Build view (now in-shell) via ?new=1.
    // The create-flow → saga handoff (route into /projects/<id>) is wired in BuildWorkspace itself.
    void goto('/chat?new=1');
  }
</script>

<svelte:head><title>Eden — Projects</title></svelte:head>

<div class="page" data-testid="projects-dashboard">
  <header class="page__head">
    <h1 class="page__title">Projects</h1>
    <span class="page__action">
      <Button variant="primary" {theme} onclick={newProject}>＋ New project</Button>
    </span>
  </header>

  <div class="page__body">
    {#if listError}
      <p class="page__error" data-testid="dash-error">{listError}</p>
    {/if}

    {#if loaded && projects.length === 0}
      <div class="page__empty" data-testid="dash-empty">
        <h2>Build something with Eden</h2>
        <p>An agent will scope it with you in a few quick steps, then build it.</p>
        <Button variant="primary" {theme} onclick={newProject}>＋ New project</Button>
      </div>
    {:else}
      <ul class="grid" role="list" data-testid="project-grid">
        <li>
          <button class="newcard" data-testid="new-project-card" onclick={newProject}>
            <span class="newcard__plus" aria-hidden="true">＋</span>
            <span class="newcard__label">New project</span>
          </button>
        </li>
        {#each projects as project (project.id)}
          <li><ProjectCard {project} onOpen={() => openProject(project)} {theme} /></li>
        {/each}
      </ul>
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
  .grid {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: var(--space-4, 16px);
    max-inline-size: 80rem;
  }
  .newcard {
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
    transition:
      border-color 140ms ease,
      color 140ms ease;
  }
  .newcard:hover {
    border-color: var(--eden-app-accent);
    color: var(--eden-app-fg);
  }
  .newcard__plus {
    font-size: var(--font-size-title, 23px);
    color: var(--eden-app-accent);
  }
  @media (prefers-reduced-motion: reduce) {
    .newcard {
      transition: none;
    }
  }
</style>
