<script lang="ts">
  import { page } from '$app/state';
  import { goto } from '$app/navigation';
  import { onMount } from 'svelte';
  import {
    ArrowLeft, Check, ExternalLink, GitBranch, GitCommit,
    GitPullRequest, Loader2, X, Clock, Package, RefreshCw,
    Ban, RotateCcw, Zap,
  } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import type { BuildRunDetail } from '$lib/types/ci';
  import type { Pagination } from '$lib/types/models';
  import { fetchBuildRuns, cancelPipeline, retriggerPipeline } from '$lib/services/ci';
  import { api } from '$lib/api';
  import { formatTimeAgo, formatDateTime, formatDuration } from '$lib/utils/formatting';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import LoadingState from '$lib/components/ui/loading-state.svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import EmptyState from '$lib/components/ui/empty-state.svelte';

  const auth = getAuth();
  const canManage = $derived(auth.hasPermission('builds:manage'));
  const productId = $derived(page.params.productId);
  const prNumber = $derived(Number(page.params.prNumber));

  const STAGE_NAMES: Record<number, string> = { 1: 'Smoke', 2: 'Silicon', 3: 'Integration', 4: 'Nightly', 5: 'FUOTA' };
  const STAGE_ABBREV: Record<number, string> = { 1: 'SM', 2: 'SI', 3: 'IN', 4: 'NY', 5: 'FU' };
  const BITBUCKET_WORKSPACE = 'corekinect';

  let runs = $state<BuildRunDetail[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let refreshing = $state(false);

  // Derived: PR metadata from the first run
  const prMeta = $derived.by(() => {
    if (!runs.length) return null;
    const first = runs[0];
    return {
      prTitle: first.prTitle || `PR #${prNumber}`,
      prAuthor: first.prAuthor || '',
      prUrl: first.prUrl || '',
      product: first.product || '',
      sourceBranch: first.sourceBranch || first.branch || '',
      targetBranch: first.targetBranch || '',
      fwRepoSlug: '', // derived from product if needed
    };
  });

  // Derived: latest status per stage (for the overview bar)
  const latestPerStage = $derived.by(() => {
    const stages: Record<number, BuildRunDetail> = {};
    for (const run of runs) {
      const s = run.stage;
      if (s && (!stages[s] || run.createdAt > stages[s].createdAt)) {
        stages[s] = run;
      }
    }
    return stages;
  });

  // Derived: runs grouped by commit SHA, newest first
  const commitGroups = $derived.by(() => {
    const groups: Map<string, { sha: string; runs: BuildRunDetail[]; latestTime: string }> = new Map();
    for (const run of runs) {
      const sha = run.commitSha || 'unknown';
      if (!groups.has(sha)) {
        groups.set(sha, { sha, runs: [], latestTime: run.createdAt });
      }
      const group = groups.get(sha)!;
      group.runs.push(run);
      if (run.createdAt > group.latestTime) {
        group.latestTime = run.createdAt;
      }
    }
    // Sort groups newest first
    return Array.from(groups.values()).sort((a, b) => b.latestTime.localeCompare(a.latestTime));
  });

  // Derived: is anything still active?
  const hasActiveBuilds = $derived(runs.some(r =>
    r.status === 'BUILDING' || r.status === 'PENDING' || r.status === 'VALIDATING'
  ));

  async function loadRuns() {
    try {
      const res = await fetchBuildRuns({
        prNumber,
        productId,
        limit: 50,
      });
      runs = res.data;
      error = null;
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to load PR builds';
    } finally {
      loading = false;
      refreshing = false;
    }
  }

  function refresh() {
    refreshing = true;
    loadRuns();
  }

  function getStatusColor(status: string): string {
    switch (status) {
      case 'SUCCESS': case 'COMPLETED': return 'bg-success-muted text-success';
      case 'FAILED': case 'BUILD_FAILED': return 'bg-error-muted text-error';
      case 'BUILDING': case 'PENDING': case 'VALIDATING': return 'bg-warning-muted text-warning';
      case 'CANCELLED': return 'bg-surface-2 text-text-tertiary';
      default: return 'bg-surface-2 text-text-tertiary';
    }
  }

  function isActive(status: string): boolean {
    return ['BUILDING', 'PENDING', 'VALIDATING'].includes(status);
  }

  let cancellingId = $state<string | null>(null);
  let retriggeringId = $state<string | null>(null);

  async function handleCancel(runId: string, e: Event) {
    e.stopPropagation();
    cancellingId = runId;
    try {
      await cancelPipeline(runId);
      await loadRuns();
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to cancel';
    } finally {
      cancellingId = null;
    }
  }

  async function handleRetrigger(runId: string, e: Event) {
    e.stopPropagation();
    retriggeringId = runId;
    try {
      const result = await retriggerPipeline(runId);
      await loadRuns();
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to retrigger';
    } finally {
      retriggeringId = null;
    }
  }

  function getBitbucketCommitUrl(sha: string): string {
    const slug = runs[0]?.product?.toLowerCase().replace(/\s+/g, '_') + '_fw';
    return `https://bitbucket.org/${BITBUCKET_WORKSPACE}/${slug}/commits/${sha}`;
  }

  // Auto-refresh: always poll to catch new commits + build progress
  let refreshInterval: ReturnType<typeof setInterval> | null = null;

  onMount(() => {
    loadRuns();
    refreshInterval = setInterval(() => {
      loadRuns();
    }, 5000);
    return () => { if (refreshInterval) clearInterval(refreshInterval); };
  });
</script>

<div class="animate-fade-in space-y-6">
  <ErrorAlert message={error} />

  <!-- Back + Header -->
  <div>
    <button
      onclick={() => goto('/builds')}
      class="mb-4 flex items-center gap-1.5 text-sm text-text-secondary hover:text-text-primary transition-colors"
    >
      <ArrowLeft size={16} />
      Back to Builds
    </button>

    {#if loading}
      <LoadingState message="Loading PR pipeline..." />
    {:else if prMeta}
      <!-- PR Header -->
      <div class="rounded-xl border border-border bg-surface-1 p-5">
        <!-- Title row -->
        <div class="flex items-start justify-between gap-4 mb-3">
          <div class="flex items-center gap-3">
            <GitPullRequest size={20} class="text-accent flex-shrink-0" />
            <h1 class="text-xl font-semibold text-text-primary">
              PR #{prNumber}: {prMeta.prTitle}
            </h1>
          </div>
          <div class="flex items-center gap-2">
            <button
              onclick={refresh}
              disabled={refreshing}
              class="rounded-lg border border-border p-1.5 text-text-secondary hover:bg-surface-2 disabled:opacity-50"
              title="Refresh"
            >
              <RefreshCw size={14} class={refreshing ? 'animate-spin' : ''} />
            </button>
            {#if prMeta.prUrl}
              <a
                href={prMeta.prUrl}
                target="_blank"
                rel="noopener noreferrer"
                class="flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-sm text-text-secondary hover:bg-surface-2"
              >
                View on Bitbucket
                <ExternalLink size={12} />
              </a>
            {/if}
          </div>
        </div>

        <!-- Meta row -->
        <div class="flex items-center gap-3 text-sm text-text-secondary mb-4">
          <span class="font-medium text-text-primary">{prMeta.product}</span>
          {#if prMeta.prAuthor}
            <span class="text-text-tertiary">by</span>
            <span>{prMeta.prAuthor}</span>
          {/if}
          {#if prMeta.sourceBranch}
            <span class="inline-flex items-center gap-1 rounded bg-surface-2 px-2 py-0.5 text-2xs font-mono">
              <GitBranch size={10} />
              {prMeta.sourceBranch}
            </span>
          {/if}
          {#if prMeta.targetBranch}
            <span class="text-text-tertiary">→</span>
            <span class="inline-flex items-center gap-1 rounded bg-surface-2 px-2 py-0.5 text-2xs font-mono">
              {prMeta.targetBranch}
            </span>
          {/if}
        </div>

        <!-- Stage overview bar -->
        <div class="flex items-center gap-1.5">
          {#each [1, 2, 3, 4, 5] as stageNum}
            {@const latest = latestPerStage[stageNum]}
            {#if latest}
              <button
                onclick={() => goto(`/builds/runs/${latest.id}`)}
                class="inline-flex items-center gap-1 rounded px-2.5 py-1 text-2xs font-semibold transition-colors hover:opacity-80 {getStatusColor(latest.status)}"
                title="{STAGE_NAMES[stageNum]}: {latest.status} ({latest.completedBuilds}/{latest.expectedBuilds} builds)"
              >
                {STAGE_ABBREV[stageNum]}
                {#if latest.status === 'SUCCESS' || latest.status === 'COMPLETED'}
                  <Check size={10} />
                {:else if isActive(latest.status)}
                  <Loader2 size={10} class="animate-spin" />
                {:else if latest.status === 'FAILED' || latest.status === 'BUILD_FAILED'}
                  <X size={10} />
                {/if}
              </button>
            {:else}
              <span class="inline-flex items-center gap-1 rounded px-2.5 py-1 text-2xs font-semibold bg-surface-2 text-text-tertiary">
                {STAGE_ABBREV[stageNum]}
                <span>&mdash;</span>
              </span>
            {/if}
          {/each}
        </div>
      </div>
    {/if}
  </div>

  <!-- Commit History -->
  {#if !loading}
    <div>
      <h2 class="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-3">
        Commit History
      </h2>

      {#if commitGroups.length === 0}
        <EmptyState message="No build runs found for this PR." />
      {:else}
        <div class="space-y-3">
          {#each commitGroups as commit, i}
            <div class="rounded-lg border border-border bg-surface-0 overflow-hidden">
              <!-- Commit header -->
              <div class="flex items-center justify-between gap-4 px-4 py-3 bg-surface-1 border-b border-border-subtle">
                <div class="flex items-center gap-3 min-w-0">
                  <a
                    href={getBitbucketCommitUrl(commit.sha)}
                    target="_blank"
                    rel="noopener noreferrer"
                    class="inline-flex items-center gap-1.5 rounded bg-surface-2 px-2 py-0.5 text-2xs font-mono text-accent hover:text-accent-hover transition-colors"
                  >
                    <GitCommit size={12} />
                    {commit.sha.slice(0, 7)}
                  </a>
                  {#if i === 0}
                    <span class="rounded bg-accent-muted px-1.5 py-0.5 text-2xs font-semibold text-accent">latest</span>
                  {/if}
                </div>
                <span class="text-2xs text-text-tertiary" title={formatDateTime(commit.latestTime)}>
                  {formatTimeAgo(commit.latestTime)}
                </span>
              </div>

              <!-- Stages for this commit -->
              <div class="divide-y divide-border-subtle">
                {#each commit.runs.sort((a, b) => (a.stage ?? 0) - (b.stage ?? 0)) as run}
                  <!-- svelte-ignore a11y_no_static_element_interactions -->
                  <div
                    role="button"
                    tabindex="0"
                    onclick={() => goto(`/builds/runs/${run.id}`)}
                    onkeydown={(e) => e.key === 'Enter' && goto(`/builds/runs/${run.id}`)}
                    class="w-full flex items-center justify-between gap-4 px-4 py-3 text-left hover:bg-surface-1 transition-colors cursor-pointer"
                  >
                    <div class="flex items-center gap-3">
                      <!-- Stage badge -->
                      <span class="inline-flex items-center gap-1 rounded px-2 py-0.5 text-2xs font-semibold {getStatusColor(run.status)}">
                        {#if run.stage}
                          {STAGE_ABBREV[run.stage]}
                        {/if}
                        {#if run.status === 'SUCCESS' || run.status === 'COMPLETED'}
                          <Check size={10} />
                        {:else if isActive(run.status)}
                          <Loader2 size={10} class="animate-spin" />
                        {:else if run.status === 'FAILED' || run.status === 'BUILD_FAILED'}
                          <X size={10} />
                        {/if}
                      </span>

                      <!-- Stage name -->
                      <span class="text-sm text-text-primary">
                        {run.stage ? STAGE_NAMES[run.stage] : 'Build'}
                      </span>

                      <!-- Build count -->
                      <span class="text-2xs text-text-tertiary">
                        {run.completedBuilds}/{run.expectedBuilds} builds
                      </span>
                    </div>

                    <div class="flex items-center gap-3 text-2xs text-text-tertiary">
                      <!-- Duration -->
                      {#if run.startedAt && run.finishedAt}
                        {@const dur = new Date(run.finishedAt).getTime() - new Date(run.startedAt).getTime()}
                        <span class="inline-flex items-center gap-1">
                          <Clock size={10} />
                          {formatDuration(dur)}
                        </span>
                      {:else if isActive(run.status)}
                        <span class="inline-flex items-center gap-1 text-warning">
                          <Loader2 size={10} class="animate-spin" />
                          running
                        </span>
                      {/if}

                      <!-- Status text -->
                      <StatusBadge status={run.status} />

                      <!-- Actions -->
                      {#if canManage}
                        {#if isActive(run.status)}
                          <button
                            onclick={(e) => handleCancel(run.id, e)}
                            disabled={cancellingId === run.id}
                            class="rounded p-1 text-text-tertiary hover:text-error hover:bg-error-muted transition-colors"
                            title="Cancel"
                          >
                            {#if cancellingId === run.id}
                              <Loader2 size={12} class="animate-spin" />
                            {:else}
                              <Ban size={12} />
                            {/if}
                          </button>
                        {:else if run.status === 'FAILED' || run.status === 'BUILD_FAILED' || run.status === 'CANCELLED'}
                          <button
                            onclick={(e) => handleRetrigger(run.id, e)}
                            disabled={retriggeringId === run.id}
                            class="rounded p-1 text-text-tertiary hover:text-accent hover:bg-accent-muted transition-colors"
                            title="Re-trigger"
                          >
                            {#if retriggeringId === run.id}
                              <Loader2 size={12} class="animate-spin" />
                            {:else}
                              <RotateCcw size={12} />
                            {/if}
                          </button>
                        {/if}
                      {/if}
                    </div>
                  </div>
                {/each}
              </div>
            </div>
          {/each}
        </div>
      {/if}
    </div>
  {/if}
</div>
