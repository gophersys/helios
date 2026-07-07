<script lang="ts">
  // The PROJECT-DETAIL route — what a freshly created project shows while Eden's create-saga
  // provisions it, and the gate into the project's workspace once it is ready. It is RELOAD-SAFE: it
  // re-reads the project status on mount and POLLS it (the gateway exposes no project-level SSE yet —
  // router.go lists only POST/GET /projects + GET /projects/{id}), so a refresh resumes at exactly the
  // current step rather than restarting the flow. The status drives three outcomes:
  //
  //   • {creating, provisioning_repo, seeding_template, launching_supervisor} → the LOADING screen
  //     (the reusable ProjectLoading stepper: repo → template → supervisor).
  //   • {supervisor_ready, wizard, building} → route INTO the workspace (the chat surface streaming the
  //     supervisor's build session; the workspace shell lands here as it is built).
  //   • failed → ProjectLoading's failure state (lastError + a Retry that re-POSTs the create — the
  //     saga is idempotency-keyed, so a re-create resumes from where it stalled).
  //
  // Client-rendered (ssr=false, +page.ts) like the rest of the app shell. Token-driven via @eden/theme.
  import { page } from '$app/state';
  import { goto } from '$app/navigation';
  import { onDestroy } from 'svelte';
  import { GatewayClient, GatewayError } from '$lib/gateway/client';
  import { resolveGatewayUrl } from '$lib/gateway/configuration';
  import { edenTheme } from '$lib/theme/edenTheme';
  import {
    PROJECT_LOADING_STATUSES,
    PROJECT_READY_STATUSES,
    type ProjectStatus,
    type ProjectView,
  } from '$lib/gateway/types';
  import ProjectLoading from '$lib/dashboard/ProjectLoading.svelte';
  import SetupWizard from '$lib/chat/wizard/SetupWizard.svelte';
  import { createGatewayWizardSource } from '$lib/chat/wizard/wizardSource';

  const client = new GatewayClient(resolveGatewayUrl());
  const theme = edenTheme;

  // The route id is reactive (the param can change without a remount on a client-side nav between
  // two project ids), so the poll re-targets when it does.
  const projectId = $derived(page.params.id ?? '');

  let project = $state<ProjectView | null>(null);
  let loadError = $state<string | null>(null);
  let retrying = $state(false);
  // The first successful fetch flips this so we render a skeleton state before the first read, never
  // a flash of the failure UI for a still-unknown status.
  let loaded = $state(false);

  // The poll cadence while the saga walks. A modest 1.2s keeps the stepper feeling live without
  // hammering the gateway; the loop stops the instant the status leaves the loading set.
  const POLL_INTERVAL_MS = 1200;
  let pollTimer: ReturnType<typeof setTimeout> | null = null;

  function clearPoll(): void {
    if (pollTimer !== null) {
      clearTimeout(pollTimer);
      pollTimer = null;
    }
  }

  /** True while the current status is a provisioning step (the poll keeps running). */
  function isLoadingStatus(status: ProjectStatus): boolean {
    return PROJECT_LOADING_STATUSES.has(status);
  }

  /** Read the project once. On a terminal/ready status, route into the workspace; while loading,
   *  schedule the next poll. A fetch fault is surfaced (not swallowed) but does NOT stop the poll —
   *  a transient gateway blip should not strand the loading screen. */
  async function fetchOnce(): Promise<void> {
    const id = projectId;
    if (!id) {
      loadError = 'No project id in the route.';
      loaded = true;
      return;
    }
    try {
      const next = await client.getProject(id);
      // Guard against an out-of-order resolution after the id changed under a client-side nav.
      if (id !== projectId) return;
      project = next;
      loadError = null;
      loaded = true;

      // The SETUP WIZARD step is in-route: when the saga reaches `wizard` the supervisor is up and
      // driving the product-scoping interview, so we render SetupWizard HERE (the template branches
      // on the status) rather than routing on — the wizard runs its own worktree poll, so the
      // status poll stops. Only the OTHER ready statuses (supervisor_ready/building) route straight
      // into the build workspace.
      if (next.status === 'wizard') {
        clearPoll();
        return;
      }
      if (PROJECT_READY_STATUSES.has(next.status)) {
        clearPoll();
        enterWorkspace(next);
        return;
      }
      if (isLoadingStatus(next.status)) {
        schedulePoll();
        return;
      }
      // A non-loading, non-ready status (draft / failed): stop polling and let the template render the
      // appropriate surface (failed → the retry UI; draft → the same loading chrome until the saga
      // begins, which a manual reload or the create handoff advances).
      clearPoll();
    } catch (cause) {
      if (id !== projectId) return;
      loaded = true;
      loadError = cause instanceof GatewayError ? `${cause.kind}: ${cause.message}` : String(cause);
      // A not-found is terminal (the project does not exist) — stop polling; any other fault is
      // treated as transient and the poll continues so a recovered gateway resumes the screen.
      if (cause instanceof GatewayError && cause.kind === 'not-found') {
        clearPoll();
      } else {
        schedulePoll();
      }
    }
  }

  function schedulePoll(): void {
    clearPoll();
    pollTimer = setTimeout(() => void fetchOnce(), POLL_INTERVAL_MS);
  }

  /** Route into the project's Build view IN-SHELL once the supervisor is up (doc 17 §5). The project
   *  maps to its own /projects/<id>/build surface, which resolves the build session (supervisor agent
   *  or legacy link) and streams it inside the one shell. */
  function enterWorkspace(ready: ProjectView): void {
    void goto(`/projects/${encodeURIComponent(ready.id)}/build`);
  }

  /** Retry a failed build: re-POST the create (the saga is idempotency-keyed, so it resumes), then
   *  resume polling from the refreshed status. A retry fault surfaces on the same screen. */
  async function retry(): Promise<void> {
    if (!project || retrying) return;
    retrying = true;
    loadError = null;
    try {
      const refreshed = await client.resumeProject(project);
      project = refreshed;
      if (isLoadingStatus(refreshed.status)) {
        schedulePoll();
      } else if (refreshed.status === 'wizard') {
        // The setup wizard renders in-route (the template branches on status); stop polling.
        clearPoll();
      } else if (PROJECT_READY_STATUSES.has(refreshed.status)) {
        enterWorkspace(refreshed);
      }
    } catch (cause) {
      loadError = cause instanceof GatewayError ? `${cause.kind}: ${cause.message}` : String(cause);
    } finally {
      retrying = false;
    }
  }

  function backToProjects(): void {
    clearPoll();
    void goto('/projects');
  }

  // Reload-safe entry: (re-)start the read whenever the route id changes. $effect re-runs on
  // projectId, so a client-side nav between two project ids re-targets the poll; a hard reload runs it
  // fresh on mount.
  $effect(() => {
    // Touch projectId so the effect tracks it.
    void projectId;
    clearPoll();
    loaded = false;
    project = null;
    void fetchOnce();
    return clearPoll;
  });

  onDestroy(clearPoll);

  // The status the loading surface renders. Before the first read we show the provisioning chrome at
  // the earliest step (`creating`) so there is no blank flash; after, the real status drives it.
  const displayStatus = $derived<ProjectStatus>(project?.status ?? 'creating');

  // ── the SETUP WIZARD (status === 'wizard') ─────────────────────────────────────.
  // True once the saga reached the wizard step AND the supervisor session id is known (the wizard
  // drives that live session + reads the project's worktree). The template branches on this.
  const inWizard = $derived(project?.status === 'wizard' && Boolean(project.supervisorAgentId));

  // The wizard's I/O seam, bound to the LIVE gateway: the supervisor session's workspace file
  // surface (the committed init/product/* interview artifacts) + its control channel. Derived from
  // the project so it re-targets if the route id changes; null until the supervisor id is known.
  const wizardSource = $derived(
    project && project.supervisorAgentId
      ? createGatewayWizardSource(client, project.supervisorAgentId)
      : null,
  );

  /** The interview is complete (the wizard's onfinish): route into the build workspace. The build
   *  session is the supervisor agent (or the legacy `sessionId` link). This finish path lands on the
   *  unscoped Build view at /chat?session= (the wizard's committed contract — the setup interview
   *  ends in the running build conversation, which the Build view streams); the project's own
   *  /projects/<id>/build surface is reached from the dashboard once the project is mapped. */
  function enterFromWizard(): void {
    if (!project) return;
    const sessionId = project.supervisorAgentId || project.sessionId;
    if (sessionId) {
      const harness = project.harness ? `&harness=${encodeURIComponent(project.harness)}` : '';
      void goto(`/chat?session=${encodeURIComponent(sessionId)}${harness}`);
    } else {
      void goto('/chat');
    }
  }
</script>

<svelte:head><title>Eden — {project?.name ?? 'Project'}</title></svelte:head>

{#if loadError && !project}
  <!-- A hard read fault before we ever saw the project (e.g. not-found): a plain, honest message. -->
  <div class="fault" data-testid="project-detail-fault">
    <h1>Couldn't load this project</h1>
    <p class="fault__detail">{loadError}</p>
    <button type="button" class="fault__action" onclick={backToProjects}>Back to projects</button>
  </div>
{:else if inWizard && wizardSource && project}
  <!-- The setup wizard: the supervisor's FSM made visible. It renders the supervisor's committed
       interview (live from the project's worktree) + drives the supervisor session. -->
  <SetupWizard
    source={wizardSource}
    projectName={project.name}
    onfinish={enterFromWizard}
    {theme}
  />
{:else}
  <ProjectLoading
    status={displayStatus}
    name={project?.name}
    lastError={project?.lastError ?? loadError}
    {retrying}
    {theme}
    onRetry={retry}
    onCancel={backToProjects}
  />
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
