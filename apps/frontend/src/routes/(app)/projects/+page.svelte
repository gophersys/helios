<script lang="ts">
  // The PROJECTS page — Eden's home, rendered inside the app shell (the sidebar provides the brand,
  // user, and Settings; this page owns its header + grid). A project is what a user builds; the grid
  // lists them, "＋ New project" starts the creation flow. Token-driven; cards are reusable components.
  import { GatewayClient, GatewayError } from '$lib/gateway/client';
  import { resolveGatewayUrl } from '$lib/gateway/configuration';
  import { edenLightTheme, edenDarkTheme } from '$lib/theme/edenTheme';
  import { themePreference } from '$lib/theme/themePreference.svelte';
  import { goto } from '$app/navigation';
  import { Button, EmptyState } from '@eden/primitives';
  import ProjectCard, { type ProjectSummary } from '$lib/dashboard/ProjectCard.svelte';

  const client = new GatewayClient(resolveGatewayUrl());
  const theme = $derived(themePreference.resolvedMode === 'dark' ? edenDarkTheme : edenLightTheme);

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

  // W4: the empty state is a PRODUCT SURFACE, not a void (doc 17 §1.2/§4). Its content slot seeds a
  // few example "spark" ideas — what Eden can build — as clickable chips that open the create flow, so
  // the empty case OFFERS a starting point instead of an apology. (The flow opens on SPARK where the
  // user refines the idea; a pre-filled spark param is not yet a wired end-to-end contract, so a chip
  // honestly starts the flow rather than faking a filled input.)
  const SPARK_IDEAS: readonly string[] = [
    'A payments service in Go',
    'A REST API with Postgres',
    'A CLI that scaffolds projects',
  ];
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
      <!-- W4: the empty state is a product surface (@eden/primitives EmptyState) — serif headline ·
           body · primary action · a CONTENT SLOT of spark-idea chips that open the create flow. The
           `dash-empty` testid stays on the rendered EmptyState root (the DO-NOT-BREAK contract). -->
      <div class="page__empty" data-testid="dash-empty">
        <EmptyState
          {theme}
          headline="Build something with Eden"
          body="An agent will scope it with you in a few quick steps, then build it."
        >
          {#snippet action()}
            <Button variant="primary" {theme} onclick={newProject}>＋ New project</Button>
          {/snippet}
          {#snippet content()}
            <div class="sparks">
              <p class="sparks__caption">Try starting from an idea</p>
              <ul class="sparks__list" role="list">
                {#each SPARK_IDEAS as idea (idea)}
                  <li>
                    <button
                      type="button"
                      class="spark"
                      data-testid="dash-spark"
                      onclick={newProject}
                    >
                      {idea}
                    </button>
                  </li>
                {/each}
              </ul>
            </div>
          {/snippet}
        </EmptyState>
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
  /* W4: the wrapper only vertically positions the EmptyState (which owns its own reading measure,
     centering, headline/body voices, and content slot). No hand-set painted roles here. */
  .page__empty {
    margin-block-start: 10vh;
  }
  /* the spark-idea chips in the EmptyState content slot — clickable ideas that open the create flow. */
  .sparks {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-3, 12px);
  }
  .sparks__caption {
    margin: 0;
    font-size: var(--font-size-caption, 12px);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--eden-app-muted, var(--color-outline));
  }
  .sparks__list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: var(--space-2, 8px);
  }
  .spark {
    padding: var(--space-2, 8px) var(--space-4, 16px);
    min-block-size: 44px;
    background: var(--eden-app-panel-bg, var(--color-surface));
    border: 1px solid var(--eden-app-line, var(--color-outline));
    border-radius: 999px;
    color: var(--eden-app-fg, var(--color-on-surface));
    font: inherit;
    font-size: var(--font-size-label, 13px);
    cursor: pointer;
    /* W5: hover rides the theme motion tokens (nearest ladder step + standard easing). */
    transition:
      border-color var(--duration-short-3, 140ms) var(--ease-standard, ease),
      color var(--duration-short-3, 140ms) var(--ease-standard, ease);
  }
  .spark:hover {
    border-color: var(--color-primary);
    color: var(--color-primary);
  }
  .spark:focus-visible {
    outline: 2px solid var(--color-primary);
    outline-offset: 2px;
  }
  /* W5 density pass (P-D5, vs the Clusters north star): the populated grid is a WORKING surface, not
     a marketing page — tighten the gutter to the space-3 step (the north star's card gutter grade) so
     the cards read as a dense, scannable board rather than floating tiles. */
  .grid {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: var(--space-3, 12px);
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
      border-color var(--duration-short-3, 140ms) var(--ease-standard, ease),
      color var(--duration-short-3, 140ms) var(--ease-standard, ease);
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
    .newcard,
    .spark {
      transition: none;
    }
  }
</style>
