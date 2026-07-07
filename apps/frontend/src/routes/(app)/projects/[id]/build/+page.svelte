<script lang="ts">
  // /projects/[id]/build — THE project's Build view (doc 17 §5): the chat workspace scoped to one
  // project, rendered inside the one (app) shell. This is where a mapped project's conversation lives
  // (the in-shell equivalent of the old /chat?session= handoff). It resolves the project's build
  // session (the supervisor agent, or the legacy sessionId link) and hands it to <BuildWorkspace> as
  // the deep-link intent, so the same reusable Build view streams the project's session with the
  // shell chrome around it. A project still provisioning has no build session yet → we fall through
  // to the project loading/wizard route (/projects/[id]).
  import { page } from '$app/state';
  import { goto } from '$app/navigation';
  import { GatewayClient, GatewayError } from '$lib/gateway/client';
  import { resolveGatewayUrl } from '$lib/gateway/configuration';
  import type { ProductHarness, ProjectView } from '$lib/gateway/types';
  import { PROJECT_READY_STATUSES } from '$lib/gateway/types';
  import BuildWorkspace from '$lib/buildview/BuildWorkspace.svelte';

  const client = new GatewayClient(resolveGatewayUrl());
  const projectId = $derived(page.params.id ?? '');

  let project = $state<ProjectView | null>(null);
  let loadError = $state<string | null>(null);
  let loaded = $state(false);

  // The build session the workspace attaches to (the supervisor agent, or the legacy link).
  const sessionId = $derived(project?.supervisorAgentId || project?.sessionId || null);
  const harness = $derived((project?.harness as ProductHarness | null) ?? null);

  $effect(() => {
    const id = projectId;
    if (!id) {
      loadError = 'No project id in the route.';
      loaded = true;
      return;
    }
    loaded = false;
    project = null;
    loadError = null;
    void (async () => {
      try {
        const next = await client.getProject(id);
        if (id !== projectId) return;
        project = next;
        loaded = true;
        // A project that has not reached its supervisor yet has no build session — send the user to
        // the loading/wizard route, which drives the saga and lands back here when ready.
        if (!next.supervisorAgentId && !next.sessionId && !PROJECT_READY_STATUSES.has(next.status)) {
          void goto(`/projects/${encodeURIComponent(id)}`);
        }
      } catch (cause) {
        if (id !== projectId) return;
        loaded = true;
        loadError =
          cause instanceof GatewayError ? `${cause.kind}: ${cause.message}` : String(cause);
      }
    })();
  });
</script>

<svelte:head><title>Eden — {project?.name ?? 'Build'}</title></svelte:head>

{#if loadError}
  <div class="fault" data-testid="build-fault">
    <h1>Couldn't load this project</h1>
    <p class="fault__detail">{loadError}</p>
    <button type="button" class="fault__action" onclick={() => goto('/projects')}
      >Back to projects</button
    >
  </div>
{:else if loaded}
  <BuildWorkspace deepLink={{ sessionId, harness }} />
{/if}

<style>
  .fault {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: var(--space-4, 16px);
    max-inline-size: 34rem;
    margin: 12vh auto 0;
    padding: var(--space-6, 24px);
    color: var(--eden-app-fg);
  }
  .fault h1 {
    margin: 0;
    font-size: var(--font-size-title, 23px);
  }
  .fault__detail {
    margin: 0;
    color: var(--color-error);
    font-size: var(--font-size-label, 13px);
    overflow-wrap: anywhere;
  }
  .fault__action {
    appearance: none;
    font-family: inherit;
    font-size: var(--font-size-body, 15px);
    font-weight: 600;
    padding: var(--space-2, 8px) var(--space-5, 20px);
    min-block-size: 44px;
    border-radius: var(--eden-app-radius, 8px);
    border: 1px solid var(--eden-app-line);
    background: none;
    color: var(--eden-app-fg);
    cursor: pointer;
  }
  .fault__action:hover {
    border-color: var(--eden-app-accent);
  }
  .fault__action:focus-visible {
    outline: 2px solid var(--eden-app-accent);
    outline-offset: 2px;
  }
</style>
