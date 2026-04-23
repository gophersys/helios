<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import {
    ChevronDown,
    ChevronRight,
    CheckCircle2,
    XCircle,
    AlertTriangle,
    GitCommit,
    GitBranch,
    GitPullRequest,
    Tag,
    Clock,
    Plus,
    Minus,
    User,
    Bot,
  } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import { apiFetch } from '$lib/api';
  import type { PlatformRelease, Pagination, ErrorReportSummary, ReleaseTestSuite } from '$lib/types/models';
  import type { ApiResponse } from '$lib/types';
  import { formatDateTime, formatDate } from '$lib/utils/formatting';
  import EmptyState from '$lib/components/ui/empty-state.svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import LoadingState from '$lib/components/ui/loading-state.svelte';
  import FilterBar from '$lib/components/ui/filter-bar.svelte';
  import FilterSelect from '$lib/components/ui/filter-select.svelte';
  import PaginationControls from '$lib/components/ui/pagination.svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';

  const auth = getAuth();

  let releases = $state<PlatformRelease[]>([]);
  let pagination = $state<Pagination>({ page: 1, limit: 50, total: 0, pages: 0 });
  let loading = $state(true);
  let error = $state<string | null>(null);
  let expandedId = $state<string | null>(null);
  let expandedRelease = $state<(PlatformRelease & { resolvedBugs?: ErrorReportSummary[] }) | null>(null);
  let expandedLoading = $state(false);

  let statusFilter = $state('');
  let page = $state(1);

  const statusOptions = [
    { value: '', label: 'All statuses' },
    { value: 'DRAFT', label: 'Draft' },
    { value: 'STAGED', label: 'Staged' },
    { value: 'RELEASED', label: 'Released' },
    { value: 'ROLLED_BACK', label: 'Rolled Back' },
  ];

  const currentRelease = $derived(
    releases.find(r => r.status === 'RELEASED')
  );

  function gateIcon(gateStatus: string | null): typeof CheckCircle2 {
    if (gateStatus === 'passed') return CheckCircle2;
    if (gateStatus === 'failed') return XCircle;
    if (gateStatus === 'overridden') return AlertTriangle;
    return CheckCircle2;
  }

  function gateColor(gateStatus: string | null): string {
    if (gateStatus === 'passed') return 'text-success';
    if (gateStatus === 'failed') return 'text-error';
    if (gateStatus === 'overridden') return 'text-warning';
    return 'text-text-tertiary';
  }

  function gateLabel(gateStatus: string | null): string {
    if (gateStatus === 'passed') return 'Passed';
    if (gateStatus === 'failed') return 'Failed';
    if (gateStatus === 'overridden') return 'Overridden';
    return 'N/A';
  }

  function testBarWidth(passed: number | null, failed: number | null): { passPct: number; failPct: number } {
    const p = passed ?? 0;
    const f = failed ?? 0;
    const total = p + f;
    if (total === 0) return { passPct: 0, failPct: 0 };
    return {
      passPct: (p / total) * 100,
      failPct: (f / total) * 100,
    };
  }

  function formatDuration(ms: number | null): string {
    if (ms == null) return 'N/A';
    if (ms < 1000) return `${ms}ms`;
    const s = ms / 1000;
    if (s < 60) return `${s.toFixed(1)}s`;
    const m = Math.floor(s / 60);
    const rem = Math.round(s % 60);
    return rem > 0 ? `${m}m ${rem}s` : `${m}m`;
  }

  function releaseDate(release: PlatformRelease): string | null {
    if (release.releasedAt) return formatDate(release.releasedAt);
    if (release.stagedAt) return formatDate(release.stagedAt);
    return null;
  }

  function simpleMarkdown(md: string): string {
    let html = md
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/^### (.+)$/gm, '<h4 class="text-sm font-semibold text-text-primary mt-3 mb-1">$1</h4>')
      .replace(/^## (.+)$/gm, '<h3 class="text-sm font-semibold text-text-primary mt-3 mb-1">$1</h3>')
      .replace(/^# (.+)$/gm, '<h3 class="text-base font-semibold text-text-primary mt-3 mb-1">$1</h3>')
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/`(.+?)`/g, '<code class="rounded bg-surface-2 px-1 py-0.5 text-2xs font-mono">$1</code>')
      .replace(/^- (.+)$/gm, '<li class="ml-4 list-disc text-sm text-text-secondary">$1</li>')
      .replace(/\n\n/g, '<br/><br/>')
      .replace(/\n/g, '<br/>');
    return html;
  }

  async function fetchReleases(): Promise<void> {
    loading = true;
    error = null;
    try {
      const params = new URLSearchParams();
      params.set('page', String(page));
      params.set('limit', '50');
      if (statusFilter) params.set('status', statusFilter);

      const res = await apiFetch<ApiResponse<{ data: PlatformRelease[]; pagination: Pagination }>>(
        '/v2/releases?' + params.toString()
      );

      releases = res.data.data;
      pagination = res.data.pagination;
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to load releases';
    } finally {
      loading = false;
    }
  }

  async function fetchReleaseDetail(id: string): Promise<void> {
    expandedLoading = true;
    try {
      const res = await apiFetch<ApiResponse<PlatformRelease & { resolvedBugs?: ErrorReportSummary[] }>>(
        `/v2/releases/${id}`
      );
      expandedRelease = res.data;
    } catch {
      expandedRelease = null;
    } finally {
      expandedLoading = false;
    }
  }

  function toggleExpand(id: string): void {
    if (expandedId === id) {
      expandedId = null;
      expandedRelease = null;
    } else {
      expandedId = id;
      expandedRelease = null;
      fetchReleaseDetail(id);
    }
  }

  onMount(() => {
    if (!auth.user) {
      goto('/login');
      return;
    }
    fetchReleases();
  });

  $effect(() => {
    const _p = page;
    fetchReleases();
  });

  $effect(() => {
    const _s = statusFilter;
    page = 1;
  });

  function clearFilters(): void {
    statusFilter = '';
    page = 1;
  }

  const hasActiveFilters = $derived(!!statusFilter);
</script>

<svelte:head>
  <title>Releases | Concord</title>
</svelte:head>

<div class="flex h-full flex-col">
  <div class="px-6 pt-6 pb-2">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-xl font-semibold text-text-primary">Releases</h1>
        <p class="mt-1 text-sm text-text-secondary">Platform release history and version tracking</p>
      </div>
      {#if currentRelease}
        <div class="flex items-center gap-2">
          <span class="text-2xs text-text-tertiary">Current</span>
          <span class="inline-flex items-center gap-1.5 rounded-full bg-success-muted px-3 py-1 text-sm font-semibold text-success">
            <Tag size={14} />
            v{currentRelease.version}
          </span>
        </div>
      {/if}
    </div>
  </div>

  <FilterBar class="mx-6 mb-4">
    {#snippet filters()}
      <FilterSelect label="Status" value={statusFilter} onchange={(v) => { statusFilter = v; }} options={statusOptions} />
      {#if hasActiveFilters}
        <button class="text-2xs text-text-tertiary hover:text-text-secondary" onclick={clearFilters}>Clear</button>
      {/if}
    {/snippet}
    <span class="ml-auto text-2xs text-text-tertiary shrink-0">
      {pagination.total} release{pagination.total === 1 ? '' : 's'}
    </span>
  </FilterBar>

  <div class="flex-1 overflow-auto px-6 pb-6">
    {#if loading}
      <LoadingState message="Loading releases..." />
    {:else if error}
      <ErrorAlert message={error} />
    {:else if releases.length === 0}
      <EmptyState
        message={hasActiveFilters ? 'No releases match the current filters.' : 'No releases have been created yet.'}
      />
    {:else}
      <div class="space-y-3">
        {#each releases as release (release.id)}
          {@const isExpanded = expandedId === release.id}
          {@const bars = testBarWidth(release.testsPassed, release.testsFailed)}
          {@const hasTests = (release.testsPassed ?? 0) + (release.testsFailed ?? 0) > 0}
          {@const dateFmt = releaseDate(release)}
          {@const hasDiffStats = release.linesAdded != null || release.linesRemoved != null}

          <div class="rounded-lg border border-border bg-surface-1 transition-colors">
            <!-- Card header -->
            <button
              class="flex w-full items-start gap-4 px-4 py-4 text-left hover:bg-surface-2 transition-colors"
              onclick={() => toggleExpand(release.id)}
            >
              <div class="shrink-0 mt-0.5 text-text-tertiary">
                {#if isExpanded}
                  <ChevronDown size={16} />
                {:else}
                  <ChevronRight size={16} />
                {/if}
              </div>

              <div class="min-w-0 flex-1">
                <div class="flex items-center gap-3">
                  <span class="text-base font-bold text-text-primary">v{release.version}</span>
                  <StatusBadge status={release.status} />
                  {#if dateFmt}
                    <span class="text-2xs text-text-tertiary">{dateFmt}</span>
                  {/if}
                  {#if release.gateStatus}
                    {@const GateIcon = gateIcon(release.gateStatus)}
                    <span class="inline-flex items-center gap-1 text-2xs {gateColor(release.gateStatus)}">
                      <GateIcon size={12} />
                      {gateLabel(release.gateStatus)}
                    </span>
                  {/if}
                  {#if release.releaseOrigin}
                    <span class="inline-flex items-center gap-1 rounded-full bg-surface-2 px-2 py-0.5 text-2xs text-text-tertiary">
                      {#if release.releaseOrigin === 'ci'}
                        <Bot size={10} />
                        CI
                      {:else}
                        <User size={10} />
                        Manual
                      {/if}
                    </span>
                  {/if}
                </div>

                {#if release.summary}
                  <p class="mt-1.5 text-sm text-text-secondary line-clamp-1">{release.summary}</p>
                {:else if release.changelog}
                  <p class="mt-1.5 text-sm text-text-secondary line-clamp-1">{release.changelog.split('\n')[0]}</p>
                {/if}

                <div class="mt-2 flex flex-wrap items-center gap-2">
                  {#if release.corekinectVersion}
                    <span class="rounded-full bg-surface-2 px-2 py-0.5 text-2xs text-text-secondary">
                      corekinect {release.corekinectVersion}
                    </span>
                  {/if}
                  {#if release.corectlMinVersion}
                    <span class="rounded-full bg-surface-2 px-2 py-0.5 text-2xs text-text-secondary">
                      corectl {release.corectlMinVersion}+
                    </span>
                  {/if}
                  {#if release.protoVersion}
                    <span class="rounded-full bg-surface-2 px-2 py-0.5 text-2xs text-text-secondary">
                      proto {release.protoVersion}
                    </span>
                  {/if}

                  {#if hasTests}
                    <div class="flex items-center gap-2">
                      <div class="flex h-1.5 w-20 overflow-hidden rounded-full bg-surface-2">
                        {#if bars.passPct > 0}
                          <div class="bg-success" style:width="{bars.passPct}%"></div>
                        {/if}
                        {#if bars.failPct > 0}
                          <div class="bg-error" style:width="{bars.failPct}%"></div>
                        {/if}
                      </div>
                      <span class="text-2xs text-text-tertiary">
                        {release.testsPassed} passed{release.testsFailed ? `, ${release.testsFailed} failed` : ''}
                        {#if release.testCoverage != null}
                          &middot; {release.testCoverage}%
                        {/if}
                      </span>
                    </div>
                  {/if}

                  {#if hasDiffStats}
                    <span class="inline-flex items-center gap-1.5 text-2xs text-text-tertiary">
                      {#if release.linesAdded != null}
                        <span class="text-success">+{release.linesAdded.toLocaleString()}</span>
                      {/if}
                      {#if release.linesRemoved != null}
                        <span class="text-error">-{release.linesRemoved.toLocaleString()}</span>
                      {/if}
                    </span>
                  {/if}

                  {#if release.prUrl}
                    <a
                      href={release.prUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      class="inline-flex items-center gap-1 rounded-full bg-surface-2 px-2 py-0.5 text-2xs text-accent hover:text-accent-hover transition-colors"
                      onclick={(e) => e.stopPropagation()}
                    >
                      <GitPullRequest size={10} />
                      PR
                    </a>
                  {/if}

                  {#if release.breakingChanges}
                    <span class="inline-flex items-center gap-1 rounded-full bg-error-muted px-2 py-0.5 text-2xs font-medium text-error">
                      <AlertTriangle size={10} />
                      Breaking
                    </span>
                  {/if}
                </div>
              </div>
            </button>

            <!-- Expanded detail -->
            {#if isExpanded}
              <div class="border-t border-border px-4 py-4 space-y-4">
                {#if expandedLoading}
                  <div class="py-4 text-center text-sm text-text-tertiary">Loading release details...</div>
                {:else}
                  <!-- Test Results — Backend vs Frontend breakdown -->
                  {#if hasTests || release.testDetails}
                    {@const details = release.testDetails}
                    {@const be = details?.backend as ReleaseTestSuite | undefined}
                    {@const fe = details?.frontend as ReleaseTestSuite | undefined}
                    <div>
                      <div class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">Test Results</div>

                      {#if be || fe}
                        <!-- Per-suite breakdown -->
                        <div class="mt-2 grid grid-cols-1 gap-3 sm:grid-cols-2">
                          {#each [{ label: 'Backend', suite: be }, { label: 'Frontend', suite: fe }] as { label, suite }}
                            {#if suite}
                              {@const sb = testBarWidth(suite.passed, suite.failed)}
                              {@const total = suite.passed + suite.failed}
                              <div class="rounded-lg bg-surface-0 p-3 space-y-2">
                                <div class="flex items-center justify-between">
                                  <span class="text-sm font-medium text-text-primary">{label}</span>
                                  <span class="text-2xs text-text-tertiary">{total} tests</span>
                                </div>
                                <div class="flex h-2 overflow-hidden rounded-full bg-surface-2">
                                  {#if sb.passPct > 0}
                                    <div class="bg-success transition-all" style:width="{sb.passPct}%"></div>
                                  {/if}
                                  {#if sb.failPct > 0}
                                    <div class="bg-error transition-all" style:width="{sb.failPct}%"></div>
                                  {/if}
                                </div>
                                <div class="flex items-center justify-between text-2xs">
                                  <span>
                                    <span class="text-success font-medium">{suite.passed}</span> passed,
                                    <span class="{suite.failed > 0 ? 'text-error font-medium' : 'text-text-tertiary'}">{suite.failed}</span> failed
                                  </span>
                                  <div class="flex items-center gap-3">
                                    {#if suite.coverage != null}
                                      <span class="text-text-secondary"><span class="font-medium">{suite.coverage}%</span> cov</span>
                                    {/if}
                                    {#if suite.durationMs != null}
                                      <span class="inline-flex items-center gap-1 text-text-tertiary">
                                        <Clock size={10} />
                                        {formatDuration(suite.durationMs)}
                                      </span>
                                    {/if}
                                  </div>
                                </div>
                              </div>
                            {/if}
                          {/each}
                        </div>

                        <!-- Overall summary row -->
                        <div class="mt-2 flex items-center gap-4 rounded-lg bg-surface-0 px-3 py-2">
                          <span class="text-2xs font-medium text-text-tertiary uppercase">Overall</span>
                          <div class="flex h-1.5 flex-1 overflow-hidden rounded-full bg-surface-2">
                            {#if bars.passPct > 0}
                              <div class="bg-success" style:width="{bars.passPct}%"></div>
                            {/if}
                            {#if bars.failPct > 0}
                              <div class="bg-error" style:width="{bars.failPct}%"></div>
                            {/if}
                          </div>
                          <span class="shrink-0 text-2xs text-text-secondary">
                            <span class="text-success font-medium">{release.testsPassed}</span> /
                            <span class="{(release.testsFailed ?? 0) > 0 ? 'text-error font-medium' : 'text-text-tertiary'}">{release.testsFailed ?? 0}</span>
                            {#if release.testCoverage != null}
                              &middot; <span class="font-medium">{release.testCoverage}%</span>
                            {/if}
                            {#if release.testDurationMs != null}
                              &middot; {formatDuration(release.testDurationMs)}
                            {/if}
                          </span>
                        </div>
                      {:else if hasTests}
                        <!-- No per-suite breakdown, show overall only -->
                        <div class="mt-2 flex items-center gap-4">
                          <div class="flex h-2 flex-1 overflow-hidden rounded-full bg-surface-2">
                            {#if bars.passPct > 0}
                              <div class="bg-success transition-all" style:width="{bars.passPct}%"></div>
                            {/if}
                            {#if bars.failPct > 0}
                              <div class="bg-error transition-all" style:width="{bars.failPct}%"></div>
                            {/if}
                          </div>
                          <span class="shrink-0 text-sm text-text-secondary">
                            <span class="text-success font-medium">{release.testsPassed}</span> passed,
                            <span class="{(release.testsFailed ?? 0) > 0 ? 'text-error font-medium' : 'text-text-tertiary'}">{release.testsFailed ?? 0}</span> failed
                            {#if release.testCoverage != null}
                              &middot; <span class="font-medium">{release.testCoverage}%</span> coverage
                            {/if}
                            {#if release.testDurationMs != null}
                              &middot; {formatDuration(release.testDurationMs)}
                            {/if}
                          </span>
                        </div>
                      {/if}
                    </div>
                  {/if}

                  <!-- Changelog -->
                  {#if release.changelog}
                    <div>
                      <div class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">Changelog</div>
                      <div class="mt-2 rounded-lg bg-surface-0 p-4 text-sm text-text-secondary leading-relaxed">
                        {@html simpleMarkdown(release.changelog)}
                      </div>
                    </div>
                  {/if}

                  <!-- Breaking changes -->
                  {#if release.breakingChanges}
                    <div>
                      <div class="text-2xs font-medium uppercase tracking-wider text-error">Breaking Changes</div>
                      <div class="mt-2 rounded-lg border border-error/20 bg-error-muted p-4 text-sm text-error leading-relaxed">
                        {@html simpleMarkdown(release.breakingChanges)}
                      </div>
                    </div>
                  {/if}

                  <!-- Resolved bugs -->
                  {#if expandedRelease?.resolvedBugs && expandedRelease.resolvedBugs.length > 0}
                    <div>
                      <div class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">
                        Resolved Bug Reports ({expandedRelease.resolvedBugs.length})
                      </div>
                      <div class="mt-2 space-y-1">
                        {#each expandedRelease.resolvedBugs as bug}
                          <div class="flex items-center gap-2 rounded-lg bg-surface-0 px-3 py-2">
                            <div class="shrink-0 w-2 h-2 rounded-full {
                              bug.severity === 'critical' ? 'bg-error' :
                              bug.severity === 'error' ? 'bg-error' :
                              bug.severity === 'warning' ? 'bg-warning' : 'bg-accent'
                            }"></div>
                            <span class="min-w-0 flex-1 truncate text-sm text-text-secondary">{bug.message}</span>
                            <StatusBadge status={bug.status} />
                          </div>
                        {/each}
                      </div>
                    </div>
                  {/if}

                  <!-- Details grid -->
                  <div>
                    <div class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">Details</div>
                    <div class="mt-2 grid grid-cols-2 gap-x-8 gap-y-2 text-sm sm:grid-cols-3 lg:grid-cols-4">
                      <div>
                        <div class="text-2xs text-text-tertiary">Commit</div>
                        <div class="mt-0.5 flex items-center gap-1.5">
                          <GitCommit size={12} class="text-text-tertiary" />
                          <code class="font-mono text-text-primary">{release.commitSha?.slice(0, 8) || 'N/A'}</code>
                        </div>
                      </div>
                      <div>
                        <div class="text-2xs text-text-tertiary">Branch</div>
                        <div class="mt-0.5 flex items-center gap-1.5">
                          <GitBranch size={12} class="text-text-tertiary" />
                          <span class="text-text-primary">{release.branch || 'N/A'}</span>
                        </div>
                      </div>
                      {#if release.previousVersion}
                        <div>
                          <div class="text-2xs text-text-tertiary">Previous</div>
                          <div class="mt-0.5 text-text-primary">v{release.previousVersion}</div>
                        </div>
                      {/if}
                      {#if release.prUrl}
                        <div>
                          <div class="text-2xs text-text-tertiary">Pull Request</div>
                          <a
                            href={release.prUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            class="mt-0.5 inline-flex items-center gap-1.5 text-accent hover:text-accent-hover transition-colors"
                          >
                            <GitPullRequest size={12} />
                            <span class="truncate max-w-[180px]">{release.prUrl.split('/').slice(-1)[0] ? `#${release.prUrl.split('/').pop()}` : 'View PR'}</span>
                          </a>
                        </div>
                      {/if}
                      {#if hasDiffStats}
                        <div>
                          <div class="text-2xs text-text-tertiary">Lines Changed</div>
                          <div class="mt-0.5 flex items-center gap-2">
                            {#if release.linesAdded != null}
                              <span class="inline-flex items-center gap-0.5 text-success font-medium">
                                <Plus size={12} />
                                {release.linesAdded.toLocaleString()}
                              </span>
                            {/if}
                            {#if release.linesRemoved != null}
                              <span class="inline-flex items-center gap-0.5 text-error font-medium">
                                <Minus size={12} />
                                {release.linesRemoved.toLocaleString()}
                              </span>
                            {/if}
                          </div>
                        </div>
                      {/if}
                      {#if release.releaseOrigin}
                        <div>
                          <div class="text-2xs text-text-tertiary">Origin</div>
                          <div class="mt-0.5 flex items-center gap-1.5 text-text-primary">
                            {#if release.releaseOrigin === 'ci'}
                              <Bot size={12} class="text-text-tertiary" />
                              CI Pipeline
                            {:else}
                              <User size={12} class="text-text-tertiary" />
                              Manual Release
                            {/if}
                          </div>
                        </div>
                      {/if}
                      {#if release.releaseDurationMs != null}
                        <div>
                          <div class="text-2xs text-text-tertiary">Release Duration</div>
                          <div class="mt-0.5 flex items-center gap-1.5 text-text-primary">
                            <Clock size={12} class="text-text-tertiary" />
                            {formatDuration(release.releaseDurationMs)}
                          </div>
                        </div>
                      {/if}
                      {#if release.migrationHash}
                        <div>
                          <div class="text-2xs text-text-tertiary">Migration</div>
                          <code class="mt-0.5 block font-mono text-2xs text-text-primary">{release.migrationHash.slice(0, 12)}</code>
                        </div>
                      {/if}
                      {#if release.corekinectVersion}
                        <div>
                          <div class="text-2xs text-text-tertiary">CoreKinect</div>
                          <div class="mt-0.5 text-text-primary">{release.corekinectVersion}</div>
                        </div>
                      {/if}
                      {#if release.corectlMinVersion}
                        <div>
                          <div class="text-2xs text-text-tertiary">corectl (min)</div>
                          <div class="mt-0.5 text-text-primary">{release.corectlMinVersion}</div>
                        </div>
                      {/if}
                      {#if release.protoVersion}
                        <div>
                          <div class="text-2xs text-text-tertiary">Proto</div>
                          <div class="mt-0.5 text-text-primary">{release.protoVersion}</div>
                        </div>
                      {/if}
                      {#if release.gateStatus}
                        {@const GateIcon = gateIcon(release.gateStatus)}
                        <div>
                          <div class="text-2xs text-text-tertiary">Gate</div>
                          <div class="mt-0.5 flex items-center gap-1 {gateColor(release.gateStatus)}">
                            <GateIcon size={14} />
                            <span class="font-medium">{gateLabel(release.gateStatus)}</span>
                          </div>
                          {#if release.gateOverrideBy}
                            <div class="mt-0.5 text-2xs text-text-tertiary">
                              by {release.gateOverrideBy}
                              {#if release.gateOverrideReason}
                                &mdash; {release.gateOverrideReason}
                              {/if}
                            </div>
                          {/if}
                        </div>
                      {/if}
                    </div>
                  </div>

                  <!-- Timestamps -->
                  <div class="flex items-center gap-4 border-t border-border pt-3 text-2xs text-text-tertiary">
                    <span>Created {formatDateTime(release.createdAt)}</span>
                    {#if release.stagedAt}
                      <span>Staged {formatDateTime(release.stagedAt)}</span>
                    {/if}
                    {#if release.releasedAt}
                      <span>Released {formatDateTime(release.releasedAt)}</span>
                    {/if}
                    {#if release.rolledBackAt}
                      <span class="text-error">Rolled back {formatDateTime(release.rolledBackAt)}</span>
                    {/if}
                  </div>
                {/if}
              </div>
            {/if}
          </div>
        {/each}
      </div>

      {#if pagination.pages > 1}
        <div class="mt-4 flex justify-center">
          <PaginationControls
            page={pagination.page}
            totalPages={pagination.pages}
            onPageChange={(p) => { page = p; }}
          />
        </div>
      {/if}

      <div class="mt-2 text-center text-2xs text-text-tertiary">
        {pagination.total} release{pagination.total === 1 ? '' : 's'}
      </div>
    {/if}
  </div>
</div>
