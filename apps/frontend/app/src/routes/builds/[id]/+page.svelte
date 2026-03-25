<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { beforeNavigate, goto } from '$app/navigation';
  import { page } from '$app/stores';
  import {
    ArrowLeft,
    Clock,
    Download,
    ExternalLink,
    FileText,
    GitBranch,
    GitCommit,
    Hammer,
    RefreshCw,
    Server,
  } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import type { BuildJob, BuildJobArtifact } from '$lib/types/ci';
  import { fetchBuild, fetchBuildLog, fetchBuildArtifacts, triggerBuild } from '$lib/services/ci';
  import {
    subscribeCiBuild,
    type CiBuildLogEvent,
    type CiBuildCompleteEvent,
  } from '$lib/services/websocket';
  import { formatTimeAgo, formatDateTime, formatDuration, formatSize } from '$lib/utils/formatting';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import LoadingState from '$lib/components/ui/loading-state.svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import BuildLogViewer from '$lib/components/ci/build-log.svelte';

  const auth = getAuth();
  const buildId = $derived($page.params.id);

  let build = $state<BuildJob | null>(null);
  let artifacts = $state<BuildJobArtifact[]>([]);
  let logLines = $state<string[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let retriggering = $state(false);
  let unsubscribeWs: (() => void) | null = null;

  const isActive = $derived(
    build?.status === 'BUILDING' || build?.status === 'QUEUED' || build?.status === 'CLONING'
  );

  // Bitbucket URL for the commit
  const commitUrl = $derived(
    build?.commitSha && build?.product
      ? `https://bitbucket.org/corekinect/${build.product}/commits/${build.commitSha}`
      : null
  );
  const branchUrl = $derived(
    build?.branch && build?.product
      ? `https://bitbucket.org/corekinect/${build.product}/branch/${build.branch}`
      : null
  );

  async function loadBuild(): Promise<void> {
    if (!buildId) return;
    try {
      build = await fetchBuild(buildId);
      error = null;
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to load build';
    } finally {
      loading = false;
    }
  }

  async function loadLog(): Promise<void> {
    if (!buildId) return;
    try {
      const log = await fetchBuildLog(buildId);
      logLines = log.split('\n');
    } catch {
      // Log may not be available yet
    }
  }

  async function loadArtifacts(): Promise<void> {
    if (!buildId) return;
    try {
      artifacts = await fetchBuildArtifacts(buildId);
    } catch {
      artifacts = [];
    }
  }

  async function retrigger(): Promise<void> {
    if (!build) return;
    if (!confirm('Re-trigger this build with the same configuration?')) return;
    retriggering = true;
    try {
      const newBuild = await triggerBuild({
        product: build.product,
        board: build.board,
        target: build.target,
        variant: build.variant,
        branch: build.branch,
        commitSha: build.commitSha || undefined,
      });
      goto(`/builds/${newBuild.id}`);
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to re-trigger build';
    } finally {
      retriggering = false;
    }
  }

  function setupWebSocket(): void {
    if (!buildId) return;
    unsubscribeWs = subscribeCiBuild(
      buildId,
      {
        onLog: (data: CiBuildLogEvent) => {
          const newLines = data.chunk.split('\n').filter(l => l.length > 0);
          logLines = [...logLines, ...newLines];
        },
        onComplete: (_data: CiBuildCompleteEvent) => {
          loadBuild();
          loadArtifacts();
        },
      },
      (msg) => console.warn('Build WS error:', msg)
    );
  }

  function cleanup(): void {
    if (unsubscribeWs) { unsubscribeWs(); unsubscribeWs = null; }
  }

  onMount(() => {
    if (!auth.hasPermission('builds:view')) {
      goto('/');
      return;
    }
    loadBuild();
    loadLog();
    loadArtifacts();
    setupWebSocket();

    const interval = setInterval(() => {
      if (build && isActive) {
        loadBuild();
        loadLog();
      } else if (build && (build.status === 'SUCCESS' || build.status === 'FAILED')) {
        loadLog();
        loadArtifacts();
        clearInterval(interval);
      }
    }, 5000);

    return () => clearInterval(interval);
  });

  onDestroy(cleanup);
  beforeNavigate(cleanup);
</script>

<svelte:head>
  <title>Build {buildId?.slice(0, 8) ?? ''} - Concord</title>
</svelte:head>

<div class="animate-fade-in">
  <button
    onclick={() => goto('/builds')}
    class="flex items-center gap-1 text-xs text-text-tertiary hover:text-text-primary transition-colors mb-3"
  >
    <ArrowLeft size={14} />
    All Builds
  </button>

  {#if loading}
    <LoadingState message="Loading build..." />
  {:else if error && !build}
    <ErrorAlert message={error} />
  {:else if build}
    <ErrorAlert message={error} />

    <!-- Header -->
    <div class="flex items-start justify-between gap-4 mb-4">
      <div>
        <div class="flex items-center gap-3">
          <h1 class="text-lg font-semibold text-text-primary">{build.product}</h1>
          <span class="inline-flex items-center rounded bg-surface-2 px-2 py-0.5 text-xs text-text-secondary font-mono">{build.variant}</span>
          <span class="inline-flex items-center rounded bg-surface-2 px-2 py-0.5 text-xs text-text-tertiary">{build.board} / {build.target}</span>
          <StatusBadge status={build.status} />
          {#if isActive}
            <span class="inline-flex items-center gap-1.5 rounded-full bg-accent-muted px-2 py-0.5 text-2xs font-medium text-accent">
              <span class="relative flex h-2 w-2">
                <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent opacity-75"></span>
                <span class="relative inline-flex rounded-full h-2 w-2 bg-accent"></span>
              </span>
              {build.status}
            </span>
          {/if}
        </div>

        <!-- Branch + Commit with Bitbucket links -->
        <div class="mt-2 flex items-center gap-3 text-xs">
          <span class="inline-flex items-center gap-1.5 text-text-secondary">
            <GitBranch size={14} />
            {#if branchUrl}
              <a href={branchUrl} target="_blank" rel="noopener" class="font-mono hover:text-accent transition-colors">
                {build.branch}
                <ExternalLink size={10} class="inline ml-0.5 opacity-50" />
              </a>
            {:else}
              <span class="font-mono">{build.branch}</span>
            {/if}
          </span>
          {#if build.commitSha}
            <span class="inline-flex items-center gap-1.5 text-info">
              <GitCommit size={14} />
              {#if commitUrl}
                <a href={commitUrl} target="_blank" rel="noopener" class="font-mono font-medium hover:underline">
                  {build.commitSha.slice(0, 7)}
                  <ExternalLink size={10} class="inline ml-0.5 opacity-50" />
                </a>
              {:else}
                <span class="font-mono font-medium">{build.commitSha.slice(0, 7)}</span>
              {/if}
            </span>
          {/if}
        </div>
      </div>

      <div class="flex items-center gap-2">
        {#if auth.hasPermission('builds:manage')}
          <button
            onclick={retrigger}
            disabled={retriggering}
            class="btn btn-sm flex items-center gap-1.5"
          >
            <RefreshCw size={14} class={retriggering ? 'animate-spin' : ''} />
            {retriggering ? 'Triggering...' : 'Re-trigger'}
          </button>
        {/if}
      </div>
    </div>

    <!-- Metadata cards -->
    <div class="grid grid-cols-2 gap-3 sm:grid-cols-5 mb-6">
      <div class="card card-sm">
        <div class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">Version</div>
        <div class="mt-1 text-sm font-mono font-semibold text-text-primary">
          {build.versionString ?? '--'}
        </div>
      </div>
      <div class="card card-sm">
        <div class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">Duration</div>
        <div class="mt-1 flex items-center gap-1.5">
          <Clock size={14} class="text-text-tertiary" />
          <span class="text-sm font-semibold tabular-nums text-text-primary">
            {build.durationSeconds ? formatDuration(build.durationSeconds * 1000) : '--'}
          </span>
        </div>
      </div>
      <div class="card card-sm">
        <div class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">Builder</div>
        <div class="mt-1 flex items-center gap-1.5">
          <Server size={14} class="text-text-tertiary" />
          <span class="text-sm font-semibold text-text-primary">{build.workerId ?? '--'}</span>
        </div>
      </div>
      <div class="card card-sm">
        <div class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">Artifacts</div>
        <div class="mt-1 flex items-center gap-1.5">
          <FileText size={14} class="text-text-tertiary" />
          <span class="text-sm font-semibold tabular-nums text-text-primary">{artifacts.length}</span>
        </div>
      </div>
      {#if build.configFlags?.versionOverride}
        <div class="card card-sm">
          <div class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">Override</div>
          <div class="mt-1 text-sm font-mono text-accent">{build.configFlags.versionOverride}</div>
        </div>
      {/if}
    </div>

    <!-- Error message (for FAILED builds) -->
    {#if build.status === 'FAILED' && build.errorMessage}
      <div class="mb-6 rounded-lg border border-error/30 bg-error/5 p-4">
        <h3 class="text-sm font-medium text-error mb-2">Build Failed</h3>
        <pre class="text-xs font-mono text-error/80 whitespace-pre-wrap overflow-auto max-h-48">{build.errorMessage}</pre>
      </div>
    {/if}

    <!-- Build Log -->
    {#if logLines.length > 0}
      <div class="mb-6">
        <h2 class="mb-3 text-sm font-medium text-text-primary">Build Log</h2>
        <BuildLogViewer lines={logLines} streaming={isActive} />
      </div>
    {:else if isActive}
      <div class="mb-6">
        <h2 class="mb-3 text-sm font-medium text-text-primary">Build Log</h2>
        <div class="card card-sm text-center text-xs text-text-tertiary">
          Waiting for build output...
        </div>
      </div>
    {/if}

    <!-- Artifacts -->
    {#if artifacts.length > 0}
      <div class="mb-6">
        <h2 class="mb-3 text-sm font-medium text-text-primary flex items-center gap-2">
          <FileText size={16} class="text-text-tertiary" />
          Artifacts
          <span class="text-text-tertiary font-normal">({artifacts.length})</span>
        </h2>
        <div class="space-y-1">
          {#each artifacts as artifact (artifact.id)}
            <div class="flex items-center gap-3 rounded-lg border border-border bg-surface-0 px-3 py-2">
              <FileText size={14} class="flex-shrink-0 text-text-tertiary" />
              <span class="flex-1 text-sm font-mono text-text-primary truncate">{artifact.name}</span>
              <span class="text-2xs text-text-tertiary tabular-nums">
                {formatSize(String(artifact.sizeBytes))}
              </span>
              {#if artifact.checksum}
                <span class="font-mono text-2xs text-text-tertiary" title="SHA-256: {artifact.checksum}">
                  {artifact.checksum.slice(0, 8)}
                </span>
              {/if}
              <a
                href="/v2/builds/{buildId}/artifacts/{artifact.name}"
                class="btn btn-sm text-2xs flex items-center gap-1"
                target="_blank"
              >
                <Download size={12} />
                Download
              </a>
            </div>
          {/each}
        </div>
      </div>
    {:else if !isActive && build.status !== 'QUEUED'}
      <div class="mb-6">
        <h2 class="mb-3 text-sm font-medium text-text-primary flex items-center gap-2">
          <FileText size={16} class="text-text-tertiary" />
          Artifacts
        </h2>
        <div class="card card-sm text-center text-xs text-text-tertiary">
          No artifacts generated.
        </div>
      </div>
    {/if}

    <!-- Metadata footer -->
    <div class="mt-6 flex flex-wrap items-center gap-4 text-2xs text-text-tertiary">
      <span>Created {formatDateTime(build.createdAt)}</span>
      {#if build.startedAt}
        <span>Started {formatDateTime(build.startedAt)}</span>
      {/if}
      {#if build.finishedAt}
        <span>Finished {formatDateTime(build.finishedAt)}</span>
      {/if}
      <span class="font-mono opacity-50">{build.id}</span>
    </div>
  {/if}
</div>
