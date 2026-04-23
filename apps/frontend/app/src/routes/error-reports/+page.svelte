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
    adminNotes: string | null;
    createdAt: string;
    updatedAt: string;
  }

  const auth = getAuth();
  const canManage = $derived(auth.hasPermission('system:manage'));

  let reports = $state<ErrorReportEntry[]>([]);
  let pagination = $state<Pagination>({ page: 1, limit: 50, total: 0, pages: 0 });
  let loading = $state(true);
  let error = $state<string | null>(null);
  let expandedId = $state<string | null>(null);

  // Filters
  let statusFilter = $state('');
  let typeFilter = $state('');
  let severityFilter = $state('');
  let searchQuery = $state('');
  let page = $state(1);

  const statusOptions = [
    { value: '', label: 'All statuses' },
    { value: 'OPEN', label: 'Open' },
    { value: 'ACKNOWLEDGED', label: 'Acknowledged' },
    { value: 'RESOLVED', label: 'Resolved' },
    { value: 'DISMISSED', label: 'Dismissed' },
  ];

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
      if (statusFilter) params.set('status', statusFilter);
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

  async function updateReport(id: string, data: { status?: string; adminNotes?: string }): Promise<void> {
    try {
      await apiFetch(`/v2/system/error-reports/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(data),
      });
      await fetchReports();
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to update report';
    }
  }

  async function deleteReport(id: string): Promise<void> {
    if (!confirm('Delete this error report?')) return;
    try {
      await apiFetch(`/v2/system/error-reports/${id}`, { method: 'DELETE' });
      if (expandedId === id) expandedId = null;
      await fetchReports();
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
  });

  $effect(() => {
    const _p = page;
    fetchReports();
  });

  $effect(() => {
    const _s = statusFilter;
    const _t = typeFilter;
    const _sv = severityFilter;
    const _q = searchQuery;
    page = 1;
  });

  function toggleExpand(id: string): void {
    expandedId = expandedId === id ? null : id;
  }

  function clearFilters(): void {
    statusFilter = '';
    typeFilter = '';
    severityFilter = '';
    searchQuery = '';
    page = 1;
  }

  const hasActiveFilters = $derived(!!statusFilter || !!typeFilter || !!severityFilter || !!searchQuery);
</script>

<svelte:head>
  <title>Error Reports | Concord</title>
</svelte:head>

<div class="flex h-full flex-col">
  <PageHeader title="Error Reports" description="Frontend error reports and bug submissions" />

  <FilterBar class="mx-6 mb-4">
    {#snippet filters()}
      <FilterSearch bind:value={searchQuery} placeholder="Search messages..." class="w-48" />
      <FilterSelect label="Status" value={statusFilter} onchange={(v) => { statusFilter = v; }} options={statusOptions} />
      <FilterSelect label="Type" value={typeFilter} onchange={(v) => { typeFilter = v; }} options={typeOptions} />
      <FilterSelect label="Severity" value={severityFilter} onchange={(v) => { severityFilter = v; }} options={severityOptions} />
      {#if hasActiveFilters}
        <button class="text-2xs text-text-tertiary hover:text-text-secondary" onclick={clearFilters}>Clear</button>
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
                  <div class="flex items-center gap-2 pt-2 border-t border-border">
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
                        onclick={() => updateReport(report.id, { status: 'RESOLVED' })}
                      >
                        <Check size={14} /> Resolve
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
