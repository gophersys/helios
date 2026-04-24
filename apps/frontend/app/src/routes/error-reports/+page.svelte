<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import {
    ChevronDown,
    ChevronRight,
    Trash2,
    Check,
    Eye,
    X,
  } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import { apiFetch } from '$lib/api';
  import type { Pagination } from '$lib/types/models';
  import type { ApiResponse } from '$lib/types';
  import { formatTimeAgo, formatDateTime } from '$lib/utils/formatting';
  import EmptyState from '$lib/components/ui/empty-state.svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import LoadingState from '$lib/components/ui/loading-state.svelte';
  import PageHeader from '$lib/components/ui/page-header.svelte';
  import FilterBar from '$lib/components/ui/filter-bar.svelte';
  import FilterSelect from '$lib/components/ui/filter-select.svelte';
  import FilterSearch from '$lib/components/ui/filter-search.svelte';
  import PaginationControls from '$lib/components/ui/pagination.svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';

  interface ErrorReportEntry {
    id: string;
    status: string;
    type: string;
    severity: string;
    message: string;
    context: Record<string, unknown> | null;
    currentPath: string | null;
    userEmail: string | null;
    userId: string | null;
    appVersion: string | null;
    resolvedById: string | null;
    resolvedAt: string | null;
    resolvedInReleaseId: string | null;
    resolvedInRelease: { id: string; version: string; releasedAt: string | null } | null;
    adminNotes: string | null;
    createdAt: string;
    updatedAt: string;
  }

  interface ReleaseOption {
    id: string;
    version: string;
    releasedAt: string | null;
    summary: string | null;
  }

  type Tab = 'open' | 'fixed' | 'dismissed' | 'all';

  const auth = getAuth();
  const canManage = $derived(auth.hasPermission('system:manage'));

  let reports = $state<ErrorReportEntry[]>([]);
  let pagination = $state<Pagination>({ page: 1, limit: 50, total: 0, pages: 0 });
  let loading = $state(true);
  let error = $state<string | null>(null);
  let expandedId = $state<string | null>(null);

  // Filters
  let activeTab = $state<Tab>('open');
  let typeFilter = $state('');
  let severityFilter = $state('');
  let searchQuery = $state('');
  let page = $state(1);

  // Counts for tab badges
  let counts = $state<{ open: number; fixed: number; dismissed: number; all: number }>({
    open: 0, fixed: 0, dismissed: 0, all: 0,
  });

  const TAB_STATUS_MAP: Record<Tab, string> = {
    open: 'OPEN,ACKNOWLEDGED',
    fixed: 'RESOLVED',
    dismissed: 'DISMISSED',
    all: '',
  };

  // Link-to-release modal state
  let linkingReportId = $state<string | null>(null);
  let linkReleaseOptions = $state<ReleaseOption[]>([]);
  let linkSelectedReleaseId = $state<string>('');
  let linkSubmitting = $state(false);

  const typeOptions = [
    { value: '', label: 'All types' },
    { value: 'js', label: 'JS Error' },
    { value: 'api', label: 'API Error' },
    { value: 'websocket', label: 'WebSocket' },
    { value: 'validation', label: 'Validation' },
    { value: 'unhandled', label: 'Unhandled' },
    { value: 'user_report', label: 'Bug Report' },
  ];

  const severityOptions = [
    { value: '', label: 'All severities' },
    { value: 'critical', label: 'Critical' },
    { value: 'error', label: 'Error' },
    { value: 'warning', label: 'Warning' },
    { value: 'info', label: 'Info' },
  ];

  function severityColor(severity: string): string {
    switch (severity) {
      case 'critical': return 'text-error';
      case 'error': return 'text-error';
      case 'warning': return 'text-warning';
      case 'info': return 'text-accent';
      default: return 'text-text-secondary';
    }
  }

  function typeLabel(type: string): string {
    const labels: Record<string, string> = {
      js: 'JS',
      api: 'API',
      websocket: 'WS',
      validation: 'VAL',
      unhandled: 'ERR',
      user_report: 'BUG',
    };
    return labels[type] || type.toUpperCase();
  }

  async function fetchReports(): Promise<void> {
    loading = true;
    error = null;
    try {
      const params = new URLSearchParams();
      params.set('page', String(page));
      params.set('limit', '50');
      const statusParam = TAB_STATUS_MAP[activeTab];
      if (statusParam) params.set('status', statusParam);
      if (typeFilter) params.set('type', typeFilter);
      if (severityFilter) params.set('severity', severityFilter);
      if (searchQuery) params.set('search', searchQuery);

      const res = await apiFetch<ApiResponse<{ data: ErrorReportEntry[]; pagination: Pagination }>>(
        '/v2/system/error-reports?' + params.toString()
      );

      reports = res.data.data;
      pagination = res.data.pagination;
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to load error reports';
    } finally {
      loading = false;
    }
  }

  async function fetchCounts(): Promise<void> {
    // Small parallel pings to keep the tab badges honest
    try {
      const [open, fixed, dismissed, all] = await Promise.all([
        apiFetch<ApiResponse<{ data: ErrorReportEntry[]; pagination: Pagination }>>(
          '/v2/system/error-reports?status=OPEN,ACKNOWLEDGED&limit=1',
        ),
        apiFetch<ApiResponse<{ data: ErrorReportEntry[]; pagination: Pagination }>>(
          '/v2/system/error-reports?status=RESOLVED&limit=1',
        ),
        apiFetch<ApiResponse<{ data: ErrorReportEntry[]; pagination: Pagination }>>(
          '/v2/system/error-reports?status=DISMISSED&limit=1',
        ),
        apiFetch<ApiResponse<{ data: ErrorReportEntry[]; pagination: Pagination }>>(
          '/v2/system/error-reports?limit=1',
        ),
      ]);
      counts = {
        open: open.data.pagination.total,
        fixed: fixed.data.pagination.total,
        dismissed: dismissed.data.pagination.total,
        all: all.data.pagination.total,
      };
    } catch {
      // Non-fatal — leave counts at last known values
    }
  }

  async function openLinkDialog(reportId: string): Promise<void> {
    linkingReportId = reportId;
    linkSelectedReleaseId = '';
    try {
      const res = await apiFetch<ApiResponse<{ data: ReleaseOption[]; pagination: Pagination }>>(
        '/v2/releases?status=RELEASED&limit=20',
      );
      linkReleaseOptions = res.data.data;
      if (linkReleaseOptions.length > 0) {
        linkSelectedReleaseId = linkReleaseOptions[0].id;
      }
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to load releases';
      linkingReportId = null;
    }
  }

  function closeLinkDialog(): void {
    linkingReportId = null;
    linkSelectedReleaseId = '';
    linkReleaseOptions = [];
  }

  async function submitLink(): Promise<void> {
    if (!linkingReportId || !linkSelectedReleaseId) return;
    linkSubmitting = true;
    try {
      await apiFetch(`/v2/releases/${linkSelectedReleaseId}/link-bugs`, {
        method: 'POST',
        body: JSON.stringify({ errorReportIds: [linkingReportId] }),
      });
      closeLinkDialog();
      await Promise.all([fetchReports(), fetchCounts()]);
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to link report to release';
    } finally {
      linkSubmitting = false;
    }
  }

  async function updateReport(id: string, data: { status?: string; adminNotes?: string }): Promise<void> {
    try {
      await apiFetch(`/v2/system/error-reports/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(data),
      });
      await Promise.all([fetchReports(), fetchCounts()]);
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to update report';
    }
  }

  async function deleteReport(id: string): Promise<void> {
    if (!confirm('Delete this error report?')) return;
    try {
      await apiFetch(`/v2/system/error-reports/${id}`, { method: 'DELETE' });
      if (expandedId === id) expandedId = null;
      await Promise.all([fetchReports(), fetchCounts()]);
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to delete report';
    }
  }

  onMount(() => {
    if (!auth.hasPermission('system:view')) {
      goto('/');
      return;
    }
    fetchReports();
    fetchCounts();
  });

  $effect(() => {
    const _p = page;
    fetchReports();
  });

  $effect(() => {
    const _tab = activeTab;
    const _t = typeFilter;
    const _sv = severityFilter;
    const _q = searchQuery;
    page = 1;
  });

  function toggleExpand(id: string): void {
    expandedId = expandedId === id ? null : id;
  }

  function clearFilters(): void {
    activeTab = 'open';
    typeFilter = '';
    severityFilter = '';
    searchQuery = '';
    page = 1;
  }

  const hasActiveFilters = $derived(activeTab !== 'open' || !!typeFilter || !!severityFilter || !!searchQuery);
</script>

<svelte:head>
  <title>Error Reports | Concord</title>
</svelte:head>

<div class="flex h-full flex-col">
  <PageHeader title="Error Reports" description="Frontend error reports and bug submissions" />

  <!-- Tabs -->
  <div class="mx-6 mb-3 flex gap-1 border-b border-border">
    {#each [
      { key: 'open', label: 'Open', count: counts.open },
      { key: 'fixed', label: 'Fixed', count: counts.fixed },
      { key: 'dismissed', label: 'Dismissed', count: counts.dismissed },
      { key: 'all', label: 'All', count: counts.all },
    ] as tab}
      <button
        onclick={() => (activeTab = tab.key as Tab)}
        class={[
          'inline-flex items-center gap-2 px-4 py-2 text-sm font-medium transition-colors',
          activeTab === tab.key
            ? 'border-b-2 border-accent text-accent'
            : 'text-text-tertiary hover:text-text-secondary'
        ].join(' ')}
      >
        {tab.label}
        <span class="inline-flex min-w-[1.5rem] justify-center rounded-full bg-surface-2 px-1.5 text-2xs text-text-tertiary">
          {tab.count}
        </span>
      </button>
    {/each}
  </div>

  <FilterBar class="mx-6 mb-4">
    {#snippet filters()}
      <FilterSearch bind:value={searchQuery} placeholder="Search messages..." class="w-48" />
      <FilterSelect label="Type" value={typeFilter} onchange={(v) => { typeFilter = v; }} options={typeOptions} />
      <FilterSelect label="Severity" value={severityFilter} onchange={(v) => { severityFilter = v; }} options={severityOptions} />
      {#if hasActiveFilters}
        <button class="text-2xs text-text-tertiary hover:text-text-secondary" onclick={clearFilters}>Reset</button>
      {/if}
    {/snippet}
  </FilterBar>

  <div class="flex-1 overflow-auto px-6 pb-6">
    {#if loading}
      <LoadingState message="Loading error reports..." />
    {:else if error}
      <ErrorAlert message={error} />
    {:else if reports.length === 0}
      <EmptyState
        message={hasActiveFilters ? 'No reports match the current filters.' : 'No error reports have been submitted yet.'}
      />
    {:else}
      <div class="space-y-2">
        {#each reports as report (report.id)}
          {@const isExpanded = expandedId === report.id}
          <div class="rounded-lg border border-border bg-surface-1">
            <!-- Row header -->
            <button
              class="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-surface-2 transition-colors"
              onclick={() => toggleExpand(report.id)}
            >
              <div class="shrink-0 text-text-tertiary">
                {#if isExpanded}
                  <ChevronDown size={16} />
                {:else}
                  <ChevronRight size={16} />
                {/if}
              </div>

              <!-- Severity dot -->
              <div class="shrink-0 w-2 h-2 rounded-full {
                report.severity === 'critical' ? 'bg-error' :
                report.severity === 'error' ? 'bg-error' :
                report.severity === 'warning' ? 'bg-warning' : 'bg-accent'
              }"></div>

              <!-- Type badge -->
              <span class="shrink-0 inline-flex items-center rounded px-1.5 py-0.5 text-2xs font-mono font-medium bg-surface-0 text-text-secondary border border-border">
                {typeLabel(report.type)}
              </span>

              <!-- Message -->
              <span class="min-w-0 flex-1 truncate text-sm text-text-primary">
                {report.message}
              </span>

              <!-- User -->
              {#if report.userEmail}
                <span class="hidden shrink-0 text-2xs text-text-tertiary sm:block">
                  {report.userEmail}
                </span>
              {/if}

              <!-- Path -->
              {#if report.currentPath}
                <span class="hidden shrink-0 font-mono text-2xs text-text-tertiary lg:block">
                  {report.currentPath}
                </span>
              {/if}

              <!-- Fixed-in pill (only when linked to a release) -->
              {#if report.resolvedInRelease}
                <span
                  class="shrink-0 inline-flex items-center gap-1 rounded-full bg-success/10 px-2 py-0.5 text-2xs font-medium text-success"
                  title="Fixed in release v{report.resolvedInRelease.version}"
                >
                  <Check size={10} /> v{report.resolvedInRelease.version}
                </span>
              {/if}

              <!-- Status -->
              <StatusBadge status={report.status} />

              <!-- Time -->
              <span class="shrink-0 text-2xs text-text-tertiary" title={formatDateTime(report.createdAt)}>
                {formatTimeAgo(report.createdAt)}
              </span>
            </button>

            <!-- Expanded detail -->
            {#if isExpanded}
              <div class="border-t border-border px-4 py-4 space-y-4">
                <!-- Meta grid -->
                <div class="grid grid-cols-2 gap-x-8 gap-y-2 text-sm sm:grid-cols-4">
                  <div>
                    <div class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">Severity</div>
                    <div class="mt-0.5 {severityColor(report.severity)} font-medium">{report.severity}</div>
                  </div>
                  <div>
                    <div class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">Type</div>
                    <div class="mt-0.5 text-text-primary">{report.type}</div>
                  </div>
                  <div>
                    <div class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">Status</div>
                    <div class="mt-0.5"><StatusBadge status={report.status} /></div>
                  </div>
                  <div>
                    <div class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">Reported</div>
                    <div class="mt-0.5 text-text-primary">{formatDateTime(report.createdAt)}</div>
                  </div>
                  {#if report.userEmail}
                    <div>
                      <div class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">User</div>
                      <div class="mt-0.5 text-text-primary">{report.userEmail}</div>
                    </div>
                  {/if}
                  {#if report.currentPath}
                    <div>
                      <div class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">Path</div>
                      <div class="mt-0.5 font-mono text-text-primary">{report.currentPath}</div>
                    </div>
                  {/if}
                  {#if report.appVersion}
                    <div>
                      <div class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">Version</div>
                      <div class="mt-0.5 font-mono text-text-primary">{report.appVersion}</div>
                    </div>
                  {/if}
                  {#if report.resolvedAt}
                    <div>
                      <div class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">Resolved</div>
                      <div class="mt-0.5 text-text-primary">{formatDateTime(report.resolvedAt)}</div>
                    </div>
                  {/if}
                  {#if report.resolvedInRelease}
                    <div>
                      <div class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">Fixed In</div>
                      <div class="mt-0.5 text-text-primary">
                        <a href="/releases" class="text-accent hover:underline font-mono">v{report.resolvedInRelease.version}</a>
                      </div>
                    </div>
                  {/if}
                </div>

                <!-- Message -->
                <div>
                  <div class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">Message</div>
                  <div class="mt-1 text-sm text-text-primary whitespace-pre-wrap break-words">{report.message}</div>
                </div>

                <!-- Context JSON -->
                {#if report.context}
                  {@const ctx = report.context as Record<string, unknown>}

                  <!-- Stack trace -->
                  {#if ctx.stack}
                    <div>
                      <div class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">Stack Trace</div>
                      <pre class="mt-1 max-h-48 overflow-auto rounded bg-surface-0 p-3 text-2xs text-text-secondary font-mono">{ctx.stack}</pre>
                    </div>
                  {/if}

                  <!-- API context -->
                  {#if ctx.status || ctx.url}
                    <div>
                      <div class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">API Context</div>
                      <div class="mt-1 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
                        {#if ctx.method}<div><span class="text-text-tertiary">Method:</span> <span class="font-mono">{ctx.method}</span></div>{/if}
                        {#if ctx.status}<div><span class="text-text-tertiary">Status:</span> <span class="font-mono">{ctx.status}</span></div>{/if}
                        {#if ctx.url}<div class="col-span-2"><span class="text-text-tertiary">URL:</span> <span class="font-mono break-all">{ctx.url}</span></div>{/if}
                        {#if ctx.requestDurationMs}<div><span class="text-text-tertiary">Duration:</span> <span class="font-mono">{ctx.requestDurationMs}ms</span></div>{/if}
                      </div>
                    </div>
                  {/if}

                  <!-- Recent actions / breadcrumbs -->
                  {#if Array.isArray(ctx.recentActions) && ctx.recentActions.length > 0}
                    <div>
                      <div class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">Recent Actions</div>
                      <div class="mt-1 max-h-32 overflow-auto rounded bg-surface-0 p-3">
                        {#each ctx.recentActions as action}
                          <div class="font-mono text-2xs text-text-secondary">{action}</div>
                        {/each}
                      </div>
                    </div>
                  {/if}

                  <!-- User notes -->
                  {#if ctx.userNotes}
                    <div>
                      <div class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">User Notes</div>
                      <div class="mt-1 text-sm text-text-primary whitespace-pre-wrap">{ctx.userNotes}</div>
                    </div>
                  {/if}

                  <!-- Full JSON (collapsed) -->
                  <details class="group">
                    <summary class="cursor-pointer text-2xs font-medium uppercase tracking-wider text-text-tertiary hover:text-text-secondary">
                      Full Report JSON
                    </summary>
                    <pre class="mt-1 max-h-64 overflow-auto rounded bg-surface-0 p-3 text-2xs text-text-secondary font-mono">{JSON.stringify(report.context, null, 2)}</pre>
                  </details>
                {/if}

                <!-- Admin notes -->
                {#if report.adminNotes}
                  <div>
                    <div class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">Admin Notes</div>
                    <div class="mt-1 text-sm text-text-primary whitespace-pre-wrap">{report.adminNotes}</div>
                  </div>
                {/if}

                <!-- Actions -->
                {#if canManage}
                  <div class="flex flex-wrap items-center gap-2 pt-2 border-t border-border">
                    {#if report.status === 'OPEN'}
                      <button
                        class="inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium bg-accent/10 text-accent hover:bg-accent/20 transition-colors"
                        onclick={() => updateReport(report.id, { status: 'ACKNOWLEDGED' })}
                      >
                        <Eye size={14} /> Acknowledge
                      </button>
                    {/if}
                    {#if report.status !== 'RESOLVED'}
                      <button
                        class="inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium bg-success/10 text-success hover:bg-success/20 transition-colors"
                        onclick={() => openLinkDialog(report.id)}
                      >
                        <Check size={14} /> Link to release
                      </button>
                    {/if}
                    {#if report.status === 'RESOLVED'}
                      <button
                        class="inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium bg-surface-2 text-text-secondary hover:bg-surface-3 transition-colors"
                        onclick={() => openLinkDialog(report.id)}
                        title="Link this resolved report to a different release"
                      >
                        <Check size={14} /> Change release
                      </button>
                    {/if}
                    {#if report.status !== 'DISMISSED'}
                      <button
                        class="inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium bg-surface-2 text-text-secondary hover:bg-surface-3 transition-colors"
                        onclick={() => updateReport(report.id, { status: 'DISMISSED' })}
                      >
                        <X size={14} /> Dismiss
                      </button>
                    {/if}
                    {#if report.status !== 'OPEN'}
                      <button
                        class="inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium bg-surface-2 text-text-secondary hover:bg-surface-3 transition-colors"
                        onclick={() => updateReport(report.id, { status: 'OPEN' })}
                      >
                        Reopen
                      </button>
                    {/if}
                    <div class="flex-1"></div>
                    <button
                      class="inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium text-error hover:bg-error/10 transition-colors"
                      onclick={() => deleteReport(report.id)}
                    >
                      <Trash2 size={14} /> Delete
                    </button>
                  </div>
                {/if}
              </div>
            {/if}
          </div>
        {/each}
      </div>

      <!-- Pagination -->
      {#if pagination.pages > 1}
        <div class="mt-4 flex justify-center">
          <PaginationControls
            page={pagination.page}
            totalPages={pagination.pages}
            onPageChange={(p) => { page = p; }}
          />
        </div>
      {/if}

      <!-- Summary -->
      <div class="mt-2 text-center text-2xs text-text-tertiary">
        {pagination.total} report{pagination.total === 1 ? '' : 's'}
      </div>
    {/if}
  </div>
</div>

<!-- Link-to-release dialog -->
{#if linkingReportId}
  <div
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
    role="dialog"
    aria-modal="true"
    onclick={closeLinkDialog}
    onkeydown={(e) => { if (e.key === 'Escape') closeLinkDialog(); }}
    tabindex="-1"
  >
    <div
      class="w-full max-w-md rounded-lg border border-border bg-surface-1 p-5 shadow-elevated"
      role="document"
      onclick={(e) => e.stopPropagation()}
      onkeydown={(e) => e.stopPropagation()}
    >
      <h2 class="text-base font-semibold text-text-primary">Link to release</h2>
      <p class="mt-1 text-xs text-text-tertiary">
        Choose the release that fixed this bug. The report will be marked <span class="font-medium text-success">RESOLVED</span> and linked to the release.
      </p>

      {#if linkReleaseOptions.length === 0}
        <p class="mt-4 text-sm text-text-secondary">No released versions available.</p>
      {:else}
        <label class="mt-4 block">
          <span class="mb-1 block text-2xs font-medium text-text-tertiary">Release</span>
          <select
            bind:value={linkSelectedReleaseId}
            class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-hidden"
          >
            {#each linkReleaseOptions as rel (rel.id)}
              <option value={rel.id}>
                v{rel.version}{rel.releasedAt ? ' — ' + formatDateTime(rel.releasedAt) : ''}
              </option>
            {/each}
          </select>
        </label>
      {/if}

      <div class="mt-5 flex justify-end gap-2">
        <button
          class="inline-flex items-center rounded-md px-3 py-1.5 text-xs font-medium bg-surface-2 text-text-secondary hover:bg-surface-3 transition-colors"
          onclick={closeLinkDialog}
          disabled={linkSubmitting}
        >
          Cancel
        </button>
        <button
          class="inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium bg-success/10 text-success hover:bg-success/20 transition-colors disabled:opacity-60"
          onclick={submitLink}
          disabled={linkSubmitting || !linkSelectedReleaseId}
        >
          {#if linkSubmitting}
            Linking…
          {:else}
            <Check size={14} /> Link and resolve
          {/if}
        </button>
      </div>
    </div>
  </div>
{/if}
