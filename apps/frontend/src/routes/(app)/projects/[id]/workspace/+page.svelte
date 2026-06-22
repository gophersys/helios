<script lang="ts">
  // The project WORKSPACE route — the XCode-like 3-pane workspace UI (W4): a full-screen, clean,
  // reusable workspace over a built project.
  //
  //   • TOP BAR  — ProjectTopBar: git info (branch · last commit · the repo link from
  //                project.repoUrl) + project settings (status · stacks · the supervisor agent).
  //   • LEFT     — SupervisorConversation: the live conversation with the project's supervisor,
  //                REUSING the chat SSE rails (ChatSession folds the agentsession Event taxonomy; the
  //                $lib/chat components render it). The host owns the session lifecycle (open on
  //                mount, close on teardown — leak-free).
  //   • CENTER   — WorktreePane: the generated assets — the committed worktree files (init/product/*
  //                + the rest) rendered LIVE from the project worktree as a file tree + a viewer
  //                (markdown / JSON pretty-rendered), refreshing as commits land.
  //
  // The page is the THIN composition seam: it reads the project (router.go GET /projects/{id}), binds
  // the supervisor session, wires the worktree store to the gateway, and drives the live worktree
  // refresh off the supervisor's activity (each streamed event grows the entry timeline — the "a
  // commit may have landed" signal, debounced — so freshly committed files appear without a backend
  // push channel, exactly as FileTreeWidget already does). All visual/behaviour logic lives in the
  // reusable components; this only orchestrates. Client-rendered (ssr=false), token-driven via
  // @eden/theme.
  import { page } from '$app/state';
  import { goto } from '$app/navigation';
  import { onDestroy } from 'svelte';
  import { GatewayClient, GatewayError } from '$lib/gateway/client';
  import { resolveGatewayUrl } from '$lib/gateway/configuration';
  import { ChatSession } from '$lib/gateway/session.svelte';
  import type { Harness, ProductHarness, ProjectView } from '$lib/gateway/types';
  import { edenTheme } from '$lib/theme/edenTheme';
  import WorkspaceShell from '$lib/workspace/WorkspaceShell.svelte';
  import ProjectTopBar, { type CommitSummary } from '$lib/workspace/ProjectTopBar.svelte';
  import SupervisorConversation from '$lib/workspace/SupervisorConversation.svelte';
  import WorktreePane from '$lib/workspace/WorktreePane.svelte';
  import { GatewayWorktreeSource, WorktreeStore } from '$lib/workspace/worktreeFiles.svelte';

  const client = new GatewayClient(resolveGatewayUrl());
  const theme = edenTheme;

  // The route id is reactive (a client-side nav between two project ids must re-bind without a
  // remount), so the whole binding re-runs when it changes.
  const projectId = $derived(page.params.id ?? '');

  let project = $state<ProjectView | null>(null);
  let loadError = $state<string | null>(null);
  let loaded = $state(false);

  // The bound supervisor session + the worktree store for the CURRENT project. Rebound by the effect
  // below; torn down on teardown / re-bind so the SSE stream never leaks.
  let session = $state<ChatSession | null>(null);
  let worktree = $state<WorktreeStore | null>(null);

  /** Map a product harness onto the chat-label set the SSE/control seam uses (codex folds to the
   *  claude-tone label for the chrome; the full product still rode at create). */
  function chatHarness(harness: ProductHarness): Harness {
    return harness === 'omp' ? 'omp' : 'claude';
  }

  /** The supervisor/build session id the conversation attaches to: the supervisor agent the saga
   *  launched, falling back to the legacy build sessionId. Empty when neither is recorded yet (a
   *  project that has not reached supervisor_ready — the conversation pane then shows its honest
   *  waiting state rather than a dead stream). */
  function supervisorSessionId(record: ProjectView): string {
    return record.supervisorAgentId || record.sessionId || '';
  }

  /** Read the project once. A fault is surfaced (not swallowed); a not-found is terminal. On a good
   *  read it (re)binds the supervisor session + the worktree store to this project. */
  async function load(id: string): Promise<void> {
    if (!id) {
      loadError = 'No project id in the route.';
      loaded = true;
      return;
    }
    try {
      const next = await client.getProject(id);
      if (id !== projectId) return; // a nav changed the id under us
      project = next;
      loadError = null;
      loaded = true;
      bindSession(next);
    } catch (cause) {
      if (id !== projectId) return;
      loaded = true;
      loadError = cause instanceof GatewayError ? `${cause.kind}: ${cause.message}` : String(cause);
    }
  }

  /** bindSession opens the supervisor ChatSession + wires the worktree store for a project. It tears
   *  down any prior session first (leak-free), then opens the new SSE stream. When no supervisor
   *  session is known yet, the conversation is left null (the pane renders its waiting state) but the
   *  worktree still binds to the project's session id if any. */
  function bindSession(record: ProjectView): void {
    session?.close();
    const id = supervisorSessionId(record);
    if (id) {
      const harness = chatHarness(record.harness);
      const opened = new ChatSession(client, id, harness);
      session = opened;
      opened.open();
      worktree = new WorktreeStore(new GatewayWorktreeSource(id));
      void worktree.refresh();
    } else {
      session = null;
      worktree = null;
    }
  }

  // ── live worktree refresh ─────────────────────────────────────────────────────.
  // The supervisor's entry-count is the "the agent did something — a commit may have landed" signal
  // (a new tool call / message grows it). Re-listing the worktree on each change surfaces freshly
  // committed files without a backend push channel; a debounce coalesces a burst of streamed events
  // into one request (mirrors FileTreeWidget). The effect tracks the entry count + the store identity
  // so it re-arms on a re-bind.
  const REFRESH_DEBOUNCE_MS = 350;
  let firstActivity = true;
  $effect(() => {
    const store = worktree;
    const activeSession = session;
    if (!store || !activeSession) return;
    // Touch the reactive activity signal so the effect re-runs as the supervisor works.
    const activity = activeSession.entries.length;
    // Skip the initial run (the bind already did the first refresh) — only re-list on real activity.
    if (firstActivity) {
      firstActivity = false;
      void activity;
      return;
    }
    void activity;
    const handle = setTimeout(() => void store.refresh(), REFRESH_DEBOUNCE_MS);
    return () => clearTimeout(handle);
  });

  // The last-commit summary the top bar shows. The gateway exposes no commit feed yet (router.go has
  // no commit route), so this stays null and the top bar shows branch + repo without a fabricated
  // hash — honest. When a commit-feed contract lands, the host sets this from it.
  const lastCommit = $state<CommitSummary | null>(null);

  function backToProjects(): void {
    void goto('/projects');
  }

  // (Re)bind whenever the route id changes. $effect re-runs on projectId; a hard reload runs it fresh
  // on mount, a client-side nav re-targets it. The session is torn down on cleanup so the SSE stream
  // never leaks across a nav or teardown.
  $effect(() => {
    void projectId;
    loaded = false;
    project = null;
    firstActivity = true;
    void load(projectId);
    return () => session?.close();
  });

  onDestroy(() => session?.close());
</script>

<svelte:head><title>Eden — {project?.name ?? 'Workspace'}</title></svelte:head>

{#if loadError && !project}
  <!-- A hard read fault before we ever saw the project (e.g. not-found): a plain, honest message. -->
  <div class="fault" data-testid="workspace-fault">
    <h1>Couldn't open this workspace</h1>
    <p class="fault__detail">{loadError}</p>
    <button type="button" class="fault__action" onclick={backToProjects}>Back to projects</button>
  </div>
{:else if !loaded || !project}
  <div class="loading" data-testid="workspace-skeleton">
    <p>Opening workspace…</p>
  </div>
{:else}
  {@const activeProject = project}
  <WorkspaceShell leftLabel="Conversation with the supervisor" {theme}>
    {#snippet topbar()}
      <ProjectTopBar project={activeProject} commit={lastCommit} onBack={backToProjects} {theme} />
    {/snippet}
    {#snippet left()}
      {#if session}
        <SupervisorConversation {session} {theme} />
      {:else}
        <div class="no-session" data-testid="workspace-no-session">
          <p>
            The supervisor is not online yet. The conversation opens here once the project's
            supervisor agent is ready.
          </p>
        </div>
      {/if}
    {/snippet}
    {#snippet center()}
      {#if worktree}
        <WorktreePane store={worktree} onRefresh={() => worktree?.refresh()} {theme} />
      {:else}
        <div class="no-session" data-testid="workspace-no-worktree">
          <p>The generated files appear here as the build commits them.</p>
        </div>
      {/if}
    {/snippet}
  </WorkspaceShell>
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
  .loading {
    display: grid;
    place-items: center;
    block-size: 100%;
    min-block-size: 60vh;
    color: var(--eden-app-muted);
  }
  .no-session {
    display: grid;
    place-items: center;
    block-size: 100%;
    padding: var(--space-6, 24px);
    color: var(--eden-app-muted);
    text-align: center;
  }
  .no-session p {
    max-inline-size: 40ch;
  }
</style>
