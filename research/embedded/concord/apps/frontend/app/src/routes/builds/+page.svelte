<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import {
    GitBranch,
    GitCommit,
    GitPullRequest,
    Loader2,
    Package,
    Plus,
    RefreshCw,
    Upload,
    XCircle,
  } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import { api } from '$lib/api';
  import type { ApiResponse } from '$lib/types';
  import type {
    BuildJob,
    BuildArtifact,
    BuildRunDetail,
    BuildSummary,
    PrBuildSummary,
    ValidationStage,
  } from '$lib/types/ci';
  import { STAGE_DISPLAY } from '$lib/types/ci';
  import type { Pagination, Product } from '$lib/types/models';
  import {
    fetchBuildRuns,
    fetchBuildSummary,
    fetchPrBuildRuns,
    triggerBuildRun,
    createManualBuild,
    uploadBuildArtifact,
  } from '$lib/services/ci';
  import { fetchProducts as fetchProductList } from '$lib/services/products';
  import { formatTimeAgo, formatDateTime, formatDuration } from '$lib/utils/formatting';
  import EmptyState from '$lib/components/ui/empty-state.svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import FormCard from '$lib/components/ui/form-card.svelte';
  import LoadingState from '$lib/components/ui/loading-state.svelte';
  import Modal from '$lib/components/ui/modal.svelte';
  import PageHeader from '$lib/components/ui/page-header.svelte';
  import Select from '$lib/components/ui/select.svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import TextInput from '$lib/components/ui/text-input.svelte';
  import FilterBar from '$lib/components/ui/filter-bar.svelte';
  import FilterSelect from '$lib/components/ui/filter-select.svelte';
  import FilterPills from '$lib/components/ui/filter-pills.svelte';
  import PaginationNav from '$lib/components/ui/pagination.svelte';
  import SelectionBar from '$lib/components/ui/selection-bar.svelte';
  import LinkChip from '$lib/components/ui/link-chip.svelte';
  import TriggerBadge from '$lib/components/ui/trigger-badge.svelte';
  import StagePills from '$lib/components/ui/stage-pills.svelte';
  import TimeDisplay from '$lib/components/ui/time-display.svelte';
  import UserAvatar from '$lib/components/ui/user-avatar.svelte';

  const auth = getAuth();
  const canManage = $derived(auth.hasPermission('builds:manage'));

  // ── Filter options ────────────────────────────────────────────
  const STATUS_OPTIONS = [
    { value: 'SUCCESS', label: 'Success' },
    { value: 'FAILED', label: 'Failed' },
    { value: 'BUILDING', label: 'Building' },
    { value: 'CANCELLED', label: 'Cancelled' },
  ];

  const STAGE_OPTIONS = [
    { value: '1', label: 'Smoke' },
    { value: '2', label: 'Driver' },
    { value: '3', label: 'Integration' },
    { value: '4', label: 'Regression' },
    { value: '5', label: 'FUOTA' },
  ];

  const TRIGGER_TYPE_OPTIONS = [
    { value: 'pr_push', label: 'PR' },
    { value: 'manual', label: 'Manual' },
    { value: 'auto', label: 'Auto' },
    { value: 'schedule', label: 'Schedule' },
  ];

  const DATE_RANGE_OPTIONS = [
    { value: 'today', label: 'Today' },
    { value: '7d', label: '7 days' },
    { value: '30d', label: '30 days' },
  ];

  const STAGE_NAMES: Record<number, string> = { 1: 'Smoke', 2: 'Driver', 3: 'Integration', 4: 'Regression', 5: 'FUOTA' };

  // ── Tab state ─────────────────────────────────────────────────
  type Tab = 'prs' | 'runs';
  let activeTab = $state<Tab>('prs');

  // ── Shared state ──────────────────────────────────────────────
  let pagination = $state<Pagination>({ page: 1, limit: 25, total: 0, pages: 0 });
  let loading = $state(true);
  let error = $state<string | null>(null);
  let currentPage = $state(1);
  let refreshing = $state(false);
  let productOptions = $state<{ value: string; label: string }[]>([]);
  let products = $state<Product[]>([]);

  // ── Summary stats ─────────────────────────────────────────────
  let summary = $state<BuildSummary | null>(null);

  // ── PR Build Runs state ───────────────────────────────────────
  let prBuildRuns = $state<PrBuildSummary[]>([]);
  let prProductFilter = $state('');
  let prMyPrs = $state(false);
  let prDateRange = $state('');

  // ── Build Runs state ──────────────────────────────────────────
  let buildRuns = $state<BuildRunDetail[]>([]);
  let runsProductFilter = $state('');
  let runsStageFilter = $state('');
  let runsStatusFilter = $state<Set<string>>(new Set());
  let runsTriggerFilter = $state('');

  // ── Upload modal state ────────────────────────────────────────
  let showUploadModal = $state(false);
  let uploadStep = $state<'details' | 'artifacts'>('details');
  let uploadProducts = $state<Product[]>([]);
  let uploadProductId = $state('');
  let uploadBoard = $state('');
  let uploadTarget = $state('');
  let uploadVariant = $state('');
  let uploadVersion = $state('');
  let uploadBranch = $state('');
  let uploadNotes = $state('');
  let uploadSubmitting = $state(false);
  let uploadBuildId = $state<string | null>(null);
  let uploadingFile = $state(false);
  let uploadedArtifacts = $state<BuildArtifact[]>([]);
  let preselectedProductId = $state<string | null>(null);
  let artifactRole = $state('');
  let artifactProcessor = $state('');

  // ── Trigger form state ────────────────────────────────────────
  let showForm = $state(false);
  let formProduct = $state('');
  let formBoard = $state('');
  let formTarget = $state('');
  let formVariant = $state('');
  let formBranch = $state('');
  let formNodeId = $state('');
  let formSerialNumber = $state('');
  let formValidate = $state(false);
  let submitting = $state(false);

  // ── Selection + batch (runs tab only) ─────────────────────────
  let selectedRunIds = $state<Set<string>>(new Set());
  let batchLoading = $state(false);

  function toggleRun(id: string) {
    const next = new Set(selectedRunIds);
    if (next.has(id)) next.delete(id); else next.add(id);
    selectedRunIds = next;
  }
  function selectAllRuns() { selectedRunIds = new Set(buildRuns.map(r => r.id)); }
  function clearRunSelection() { selectedRunIds = new Set(); }

  async function batchCancelRuns() {
    if (selectedRunIds.size === 0) return;
    batchLoading = true;
    error = null;
    try {
      const res = await api.post<ApiResponse<any>>('/v2/builds/runs/batch', {
        action: 'cancel', ids: [...selectedRunIds],
      });
      const result = res.data;
      if (result.failed?.length > 0) {
        error = `${result.succeeded.length} cancelled, ${result.failed.length} failed`;
      }
      selectedRunIds = new Set();
      loadData();
    } catch (err: any) {
      error = err instanceof Error ? err.message : 'Batch cancel failed';
    } finally {
      batchLoading = false;
    }
  }

  // ── Helper functions ──────────────────────────────────────────

  function isActiveStatus(status: string | null): boolean {
    return status === 'BUILDING' || status === 'PENDING' || status === 'VALIDATING' || status === 'RUNNING';
  }

  function runDuration(run: BuildRunDetail): string {
    if (run.startedAt && run.finishedAt) {
      const duration = new Date(run.finishedAt).getTime() - new Date(run.startedAt).getTime();
      return formatDuration(duration);
    }
    if (run.builds && run.builds.length > 0) {
      const totalSeconds = run.builds.reduce((sum, b) => sum + (b.durationSeconds ?? 0), 0);
      if (totalSeconds > 0) return formatDuration(totalSeconds * 1000);
    }
    return '--';
  }

  function getDateFilter(range: string): { createdAfter?: string } {
    if (!range) return {};
    const now = new Date();
    if (range === 'today') {
      const start = new Date(now);
      start.setHours(0, 0, 0, 0);
      return { createdAfter: start.toISOString() };
    }
    if (range === '7d') {
      const start = new Date(now.getTime() - 7 * 86400000);
      return { createdAfter: start.toISOString() };
    }
    if (range === '30d') {
      const start = new Date(now.getTime() - 30 * 86400000);
      return { createdAfter: start.toISOString() };
    }
    return {};
  }

  function buildStagePillData(stages: Record<number, { status: string; buildRunId: string; completedBuilds: number; expectedBuilds: number } | null>): Record<number, { status: string; enabled: boolean } | null> {
    const result: Record<number, { status: string; enabled: boolean } | null> = {};
    for (const num of [1, 2, 3, 4, 5]) {
      const s = stages[num];
      result[num] = s ? { status: s.status, enabled: true } : null;
    }
    return result;
  }

  // ── Data loading ──────────────────────────────────────────────

  async function loadSummary(): Promise<void> {
    try {
      summary = await fetchBuildSummary();
    } catch {
      // Summary is non-critical
    }
  }

  async function loadProducts(): Promise<void> {
    try {
      products = await fetchProductList();
      productOptions = products.map(p => ({ value: p.id, label: p.name }));
    } catch {
      // Non-critical
    }
  }

  async function loadPrBuildRuns(): Promise<void> {
    try {
      const res = await fetchPrBuildRuns({
        page: currentPage,
        limit: 25,
        productId: prProductFilter || undefined,
      });
      let data = res.data;
      // Client-side "My PRs" filter
      if (prMyPrs && auth.user?.email) {
        const email = auth.user.email.toLowerCase();
        data = data.filter(pr => pr.prAuthor?.toLowerCase().includes(email));
      }
      prBuildRuns = data;
      pagination = res.pagination;
      error = null;
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to load PR build runs';
    } finally {
      loading = false;
      refreshing = false;
    }
  }

  async function loadBuildRuns(): Promise<void> {
    try {
      const statusArr = Array.from(runsStatusFilter);
      const res = await fetchBuildRuns({
        page: currentPage,
        limit: 25,
        status: statusArr.length === 1 ? statusArr[0] : undefined,
        productId: runsProductFilter || undefined,
        stage: runsStageFilter ? parseInt(runsStageFilter) : undefined,
        triggerType: runsTriggerFilter || undefined,
      });
      let data = res.data;
      // Client-side multi-status filter
      if (statusArr.length > 1) {
        data = data.filter(r => statusArr.includes(r.status));
      }
      buildRuns = data;
      pagination = res.pagination;
      error = null;
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to load build runs';
    } finally {
      loading = false;
      refreshing = false;
    }
  }

  function loadData(): void {
    loadSummary();
    if (activeTab === 'prs') loadPrBuildRuns();
    else loadBuildRuns();
  }

  function refresh(): void {
    refreshing = true;
    loadData();
  }

  function switchTab(tab: Tab): void {
    activeTab = tab;
    currentPage = 1;
    selectedRunIds = new Set();
    loading = true;
    loadData();
  }

  // ── Trigger form handlers ─────────────────────────────────────

  function resetForm(): void {
    formProduct = '';
    formBoard = '';
    formTarget = '';
    formVariant = '';
    formBranch = '';
    formNodeId = '';
    formSerialNumber = '';
    formValidate = false;
    showForm = false;
  }

  async function handleSubmit(e: Event): Promise<void> {
    e.preventDefault();
    error = null;
    submitting = true;
    try {
      const run = await triggerBuildRun({
        product: formProduct,
        board: formBoard,
        target: formTarget,
        variant: formVariant,
        branch: formBranch,
        validate: formValidate,
        nodeId: formNodeId || undefined,
        serialNumber: formSerialNumber || undefined,
      });
      resetForm();
      goto(`/builds/runs/${run.id}`);
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to trigger build';
    } finally {
      submitting = false;
    }
  }

  // ── Upload modal handlers ────────────────────────────────────

  async function loadUploadProducts(): Promise<void> {
    try {
      uploadProducts = await fetchProductList();
    } catch {
      uploadProducts = [];
    }
  }

  function openUploadModal(productId?: string): void {
    preselectedProductId = productId || null;
    uploadStep = 'details';
    uploadProductId = productId || '';
    uploadBoard = '';
    uploadTarget = '';
    uploadVariant = '';
    uploadVersion = '';
    uploadBranch = '';
    uploadNotes = '';
    uploadBuildId = null;
    uploadedArtifacts = [];
    artifactRole = '';
    artifactProcessor = '';
    showUploadModal = true;
    loadUploadProducts();
  }

  function closeUploadModal(): void {
    showUploadModal = false;
    if (uploadBuildId) {
      loadData();
    }
  }

  async function handleUploadCreate(e: Event): Promise<void> {
    e.preventDefault();
    error = null;
    uploadSubmitting = true;
    try {
      const build = await createManualBuild({
        product: uploadProducts.find(p => p.id === uploadProductId)?.name || uploadProductId,
        board: uploadBoard,
        target: uploadTarget,
        variant: uploadVariant,
        branch: uploadBranch,
        versionString: uploadVersion || undefined,
        notes: uploadNotes || undefined,
        productId: uploadProductId,
      });
      uploadBuildId = build.id;
      uploadStep = 'artifacts';
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to create build';
    } finally {
      uploadSubmitting = false;
    }
  }

  async function handleArtifactUpload(file: File, role: string, processor: string): Promise<void> {
    if (!uploadBuildId) return;
    uploadingFile = true;
    try {
      const artifactType = file.name.endsWith('.hex') ? 'plaintextHex'
        : file.name.endsWith('.cfw') ? 'encryptedCfw'
        : file.name.endsWith('.json') ? 'manifest'
        : undefined;

      const artifact = await uploadBuildArtifact(uploadBuildId, file, {
        role: role || undefined,
        processor: processor || undefined,
        artifactType,
      });
      uploadedArtifacts = [...uploadedArtifacts, artifact];
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to upload artifact';
    } finally {
      uploadingFile = false;
    }
  }

  // ── Lifecycle ─────────────────────────────────────────────────

  onMount(() => {
    if (!auth.hasPermission('builds:view')) {
      goto('/');
      return;
    }
    loadProducts();
    loadData();

    const interval = setInterval(() => {
      loadData();
    }, 10000);
    return () => clearInterval(interval);
  });

  // Reset page when PR filters change
  $effect(() => {
    if (activeTab === 'prs') {
      const _a = prProductFilter;
      const _b = prMyPrs;
      const _c = prDateRange;
      currentPage = 1;
    }
  });

  // Reset page when run filters change
  $effect(() => {
    if (activeTab === 'runs') {
      const _a = runsProductFilter;
      const _b = runsStageFilter;
      const _c = runsStatusFilter;
      const _d = runsTriggerFilter;
      currentPage = 1;
    }
  });

  // Reload on page change
  $effect(() => {
    const _p = currentPage;
    loadData();
  });
</script>

<svelte:head>
  <title>Builds - Concord</title>
</svelte:head>

<div class="animate-fade-in">
  <div class="mb-6">
    <PageHeader
      title="Builds"
      description="Firmware build runs -- build, flash, and validate in one flow."
    />
  </div>

  <ErrorAlert message={error} />

  <!-- Summary bar -->
  {#if summary}
    <div class="mb-4 flex items-center gap-4 text-sm text-text-secondary">
      <span class="inline-flex items-center gap-1.5">
        <span class="font-semibold tabular-nums text-text-primary">{summary.activeRuns}</span>
        active
        {#if summary.activeRuns > 0}
          <span class="relative flex h-2 w-2">
            <span class="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-75"></span>
            <span class="relative inline-flex h-2 w-2 rounded-full bg-accent"></span>
          </span>
        {/if}
      </span>
      <span class="text-text-tertiary">&middot;</span>
      <span class="inline-flex items-center gap-1.5">
        <span class="font-semibold tabular-nums text-text-primary">{summary.queuedJobs}</span>
        queued
      </span>
    </div>
  {/if}

  <!-- Trigger Form (Build Runs tab only) -->
  {#if showForm && activeTab === 'runs'}
    <FormCard title="Trigger Build" onClose={resetForm}>
      <form onsubmit={handleSubmit} class="space-y-3">
        <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <TextInput bind:value={formProduct} label="Product" placeholder="e.g. alpha" required />
          <TextInput bind:value={formBoard} label="Board" placeholder="e.g. alpha_b0" required />
        </div>
        <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <TextInput bind:value={formTarget} label="Target" placeholder="e.g. nrf52840" required />
          <Select
            bind:value={formVariant}
            label="Variant"
            placeholder="Select variant"
            options={[
              { value: 'debug', label: 'Debug' },
              { value: 'release', label: 'Release' },
              { value: 'mfg', label: 'Manufacturing' },
            ]}
            required
          />
        </div>
        <TextInput bind:value={formBranch} label="Branch" placeholder="e.g. main" required />

        <div class="flex items-center gap-2 pt-1">
          <input
            type="checkbox"
            id="validate-toggle"
            bind:checked={formValidate}
            class="rounded border-border"
          />
          <label for="validate-toggle" class="text-sm text-text-secondary">
            Run validation after build + flash
          </label>
        </div>

        {#if formValidate}
          <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <TextInput bind:value={formNodeId} label="MTIB Node ID" placeholder="Node for flashing" />
            <TextInput bind:value={formSerialNumber} label="Serial Number" placeholder="DUT serial" />
          </div>
        {/if}

        <div class="flex justify-end gap-2 pt-1">
          <button type="button" onclick={resetForm} class="btn btn-sm">Cancel</button>
          <button type="submit" disabled={submitting} class="btn btn-sm btn-primary">
            {submitting ? 'Triggering...' : 'Trigger Build'}
          </button>
        </div>
      </form>
    </FormCard>
  {/if}

  <!-- Tab bar -->
  <div class="mb-4 flex items-center gap-0 border-b border-border">
    <button
      onclick={() => switchTab('prs')}
      class="px-4 py-2 text-sm font-medium transition-colors {activeTab === 'prs' ? 'border-b-2 border-accent text-accent' : 'text-text-tertiary hover:text-text-secondary'}"
    >
      <span class="flex items-center gap-1.5">
        <GitPullRequest size={14} />
        PR Build Runs
      </span>
    </button>
    <button
      onclick={() => switchTab('runs')}
      class="px-4 py-2 text-sm font-medium transition-colors {activeTab === 'runs' ? 'border-b-2 border-accent text-accent' : 'text-text-tertiary hover:text-text-secondary'}"
    >
      <span class="flex items-center gap-1.5">
        <Package size={14} />
        Build Runs
      </span>
    </button>

    <!-- Right side: count + refresh + action buttons -->
    <div class="ml-auto flex items-center gap-2">
      <span class="text-2xs text-text-tertiary tabular-nums">
        {pagination.total} result{pagination.total !== 1 ? 's' : ''}
      </span>
      <button
        onclick={refresh}
        disabled={refreshing}
        class="btn btn-sm flex items-center gap-1.5"
        title="Refresh"
        aria-label="Refresh"
      >
        <RefreshCw size={14} class={refreshing ? 'animate-spin' : ''} />
      </button>
      {#if canManage && activeTab === 'runs'}
        <button
          onclick={() => openUploadModal()}
          class="btn btn-sm flex items-center gap-1.5"
          title="Upload Build"
          aria-label="Upload Build"
        >
          <Upload size={14} />
          Upload
        </button>
        <button
          onclick={() => { showForm = true; }}
          class="btn btn-sm btn-primary flex items-center gap-1.5"
        >
          <Plus size={14} />
          Trigger
        </button>
      {/if}
    </div>
  </div>

  <!-- Filters -->
  {#if activeTab === 'prs'}
    <div class="mb-4">
      <FilterBar>
        {#snippet filters()}
          {#if productOptions.length > 0}
            <FilterSelect
              label="Product"
              value={prProductFilter}
              options={productOptions}
              onchange={(v) => { prProductFilter = v; }}
            />
          {/if}
          <button
            type="button"
            onclick={() => { prMyPrs = !prMyPrs; }}
            class="inline-flex items-center rounded px-2.5 py-1 text-xs font-medium transition-colors cursor-pointer {prMyPrs ? 'bg-accent text-white' : 'bg-surface-2 text-text-secondary hover:bg-surface-2/80'}"
          >
            My PRs
          </button>
          <FilterSelect
            label="Date"
            value={prDateRange}
            options={DATE_RANGE_OPTIONS}
            onchange={(v) => { prDateRange = v; }}
          />
        {/snippet}
      </FilterBar>
    </div>
  {:else}
    <div class="mb-4">
      <FilterBar>
        {#snippet filters()}
          {#if productOptions.length > 0}
            <FilterSelect
              label="Product"
              value={runsProductFilter}
              options={productOptions}
              onchange={(v) => { runsProductFilter = v; }}
            />
          {/if}
          <FilterSelect
            label="Stage"
            value={runsStageFilter}
            options={STAGE_OPTIONS}
            onchange={(v) => { runsStageFilter = v; }}
          />
          <FilterPills
            options={STATUS_OPTIONS}
            selected={runsStatusFilter}
            onchange={(s) => { runsStatusFilter = s; }}
          />
          <FilterSelect
            label="Trigger"
            value={runsTriggerFilter}
            options={TRIGGER_TYPE_OPTIONS}
            onchange={(v) => { runsTriggerFilter = v; }}
          />
        {/snippet}
      </FilterBar>
    </div>
  {/if}

  <!-- Content -->
  {#if loading}
    <LoadingState message="Loading {activeTab === 'prs' ? 'PR build runs' : 'build runs'}..." />

  <!-- PR Build Runs View -->
  {:else if activeTab === 'prs'}
    {#if prBuildRuns.length === 0}
      <EmptyState message={prProductFilter || prMyPrs || prDateRange ? 'No PR build runs match your filters.' : 'No PR build runs yet.'}>
        {#if !prProductFilter && !prMyPrs && !prDateRange}
          <p class="text-2xs text-text-tertiary mt-1">Build runs appear when pull requests are opened against watched branches. <a href="/products" class="text-accent hover:text-accent-hover">Configure build triggers</a> in a product's Validation tab.</p>
        {/if}
      </EmptyState>
    {:else}
      <div class="space-y-0">
        {#each prBuildRuns as pr (pr.prNumber + '-' + pr.productId)}
          <button
            onclick={() => goto(`/builds/prs/${pr.productId}/${pr.prNumber}`)}
            class="flex w-full items-center gap-4 px-4 py-3 border-b border-border-subtle hover:bg-surface-2/50 cursor-pointer transition-colors text-left"
          >
            <!-- PR number + title -->
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2">
                <span class="text-sm font-semibold text-text-primary whitespace-nowrap">PR #{pr.prNumber}</span>
                <span class="truncate text-sm text-text-primary" title={pr.prTitle || ''}>
                  {pr.prTitle || 'Untitled'}
                </span>
              </div>
            </div>

            <!-- Author -->
            {#if pr.prAuthor}
              <div class="flex items-center gap-1.5 shrink-0">
                <UserAvatar name={pr.prAuthor} size="sm" />
                <span class="text-2xs text-text-secondary whitespace-nowrap">{pr.prAuthor}</span>
              </div>
            {/if}

            <!-- Branch -->
            {#if pr.sourceBranch}
              <div class="hidden lg:flex items-center gap-1 text-2xs text-text-secondary shrink-0">
                <GitBranch size={10} class="text-text-tertiary" />
                <span class="font-mono">{pr.sourceBranch}</span>
                {#if pr.targetBranch}
                  <span class="text-text-tertiary">&rarr;</span>
                  <span class="font-mono text-text-tertiary">{pr.targetBranch}</span>
                {/if}
              </div>
            {/if}

            <!-- Product badge -->
            <span class="badge badge-neutral shrink-0">
              {pr.product}
            </span>

            <!-- Stage pills -->
            <div class="shrink-0">
              <StagePills stages={buildStagePillData(pr.stages)} />
            </div>

            <!-- Updated time -->
            <div class="text-2xs text-text-tertiary shrink-0 w-16 text-right">
              <TimeDisplay datetime={pr.updatedAt} />
            </div>
          </button>
        {/each}
      </div>
    {/if}

  <!-- Build Runs View -->
  {:else}
    {#if canManage}
      <SelectionBar
        selectedCount={selectedRunIds.size}
        totalCount={buildRuns.length}
        onSelectAll={selectAllRuns}
        onClearSelection={clearRunSelection}
        actions={[
          { label: 'Cancel', icon: XCircle, variant: 'danger' as const, loading: batchLoading, onclick: () => batchCancelRuns() },
        ]}
      />
    {/if}

    {#if buildRuns.length === 0}
      {@const hasRunFilters = runsProductFilter || runsStageFilter || runsStatusFilter.size > 0 || runsTriggerFilter}
      <EmptyState message={hasRunFilters ? 'No build runs match your filters.' : 'No builds yet.'}>
        {#if !hasRunFilters}
          <p class="text-2xs text-text-tertiary mt-1">Builds are triggered when commits land on watched branches. <a href="/products" class="text-accent hover:text-accent-hover">Configure build triggers</a> in a product's Validation tab.</p>
        {/if}
      </EmptyState>
    {:else}
      <div class="table-wrapper">
        <table class="table">
          <thead>
            <tr class="border-b border-border">
              {#if canManage}
                <th class="table-header w-10">
                  <input
                    type="checkbox"
                    checked={selectedRunIds.size > 0 && selectedRunIds.size === buildRuns.length}
                    indeterminate={selectedRunIds.size > 0 && selectedRunIds.size < buildRuns.length}
                    onchange={() => selectedRunIds.size === buildRuns.length ? clearRunSelection() : selectAllRuns()}
                    class="h-4 w-4 rounded border-border text-accent focus:ring-accent"
                  />
                </th>
              {/if}
              <th class="table-header">Run</th>
              <th class="table-header">Product</th>
              <th class="table-header">Stage</th>
              <th class="table-header">Trigger</th>
              <th class="table-header">Status</th>
              <th class="table-header">Branch</th>
              <th class="table-header text-right">Duration</th>
              <th class="table-header text-right">Created</th>
            </tr>
          </thead>
          <tbody>
            {#each buildRuns as run (run.id)}
              <tr
                class="table-row cursor-pointer"
                onclick={() => goto(`/builds/runs/${run.id}`)}
              >
                {#if canManage}
                  <td class="table-cell w-10" onclick={(e) => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      checked={selectedRunIds.has(run.id)}
                      onchange={() => toggleRun(run.id)}
                      class="h-4 w-4 rounded border-border text-accent focus:ring-accent"
                    />
                  </td>
                {/if}
                <td class="table-cell">
                  <span class="font-mono text-2xs text-text-tertiary">{run.id.slice(0, 8)}</span>
                </td>
                <td class="table-cell">
                  <span class="font-medium text-text-primary">{run.product || 'Unknown'}</span>
                  <div class="flex flex-wrap gap-1 mt-1">
                    <LinkChip icon={GitBranch}>{run.branch}</LinkChip>
                    {#if run.prNumber}
                      <LinkChip icon={GitPullRequest} href={run.prUrl ?? undefined} external>PR #{run.prNumber}</LinkChip>
                    {/if}
                    {#if run.commitSha}
                      <LinkChip icon={GitCommit}>{run.commitSha.slice(0, 7)}</LinkChip>
                    {/if}
                  </div>
                </td>
                <td class="table-cell">
                  {#if run.stage}
                    {@const stageName = STAGE_NAMES[run.stage]}
                    <span class="badge badge-neutral">{run.stage} {stageName ?? ''}</span>
                  {:else}
                    <span class="text-text-tertiary">--</span>
                  {/if}
                </td>
                <td class="table-cell">
                  <TriggerBadge type={run.triggerType ?? 'manual'} prNumber={run.prNumber ?? undefined} />
                </td>
                <td class="table-cell">
                  <div class="flex items-center gap-2">
                    <StatusBadge status={run.status} />
                    <span class="text-2xs text-text-tertiary tabular-nums">
                      {run.completedBuilds ?? 0}/{run.expectedBuilds ?? 0}
                    </span>
                  </div>
                </td>
                <td class="table-cell">
                  {#if run.branch}
                    <div class="flex items-center gap-1 text-2xs text-text-secondary">
                      <GitBranch size={10} class="text-text-tertiary shrink-0" />
                      <span class="font-mono truncate max-w-32">{run.branch}</span>
                    </div>
                  {/if}
                </td>
                <td class="table-cell text-right">
                  <span class="text-2xs text-text-tertiary tabular-nums">{runDuration(run)}</span>
                </td>
                <td class="table-cell text-right">
                  <TimeDisplay datetime={run.createdAt} />
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  {/if}

  <!-- Pagination -->
  {#if pagination.pages > 1}
    <div class="mt-4 flex items-center justify-between">
      <span class="text-2xs text-text-tertiary">
        Page {pagination.page} of {pagination.pages}
      </span>
      <PaginationNav
        page={currentPage}
        totalPages={pagination.pages}
        onPageChange={(p) => { currentPage = p; }}
      />
    </div>
  {/if}
</div>

<!-- Upload Build Modal -->
<Modal open={showUploadModal} title={uploadStep === 'details' ? 'Upload Build' : 'Upload Artifacts'} onclose={closeUploadModal} size="lg">
  {#if uploadStep === 'details'}
    <form onsubmit={handleUploadCreate} class="space-y-3">
      <Select
        bind:value={uploadProductId}
        label="Product"
        placeholder="Select product"
        options={uploadProducts.map(p => ({ value: p.id, label: p.name }))}
        required
        disabled={!!preselectedProductId}
      />
      <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <TextInput bind:value={uploadBoard} label="Board" placeholder="e.g. alpha_b0" required />
        <Select
          bind:value={uploadTarget}
          label="Target"
          placeholder="Select target"
          options={[
            { value: 'app', label: 'App' },
            { value: 'mfg', label: 'Manufacturing' },
          ]}
          required
        />
      </div>
      <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <Select
          bind:value={uploadVariant}
          label="Variant"
          placeholder="Select variant"
          options={[
            { value: 'debug', label: 'Debug' },
            { value: 'release', label: 'Release' },
          ]}
          required
        />
        <TextInput bind:value={uploadVersion} label="Version" placeholder="e.g. 0.8.3" />
      </div>
      <TextInput bind:value={uploadBranch} label="Branch" placeholder="e.g. main" required />
      <div>
        <label for="upload-notes" class="mb-1 block text-2xs font-medium text-text-tertiary">Notes</label>
        <textarea
          id="upload-notes"
          bind:value={uploadNotes}
          placeholder="Optional notes about this build..."
          rows="2"
          class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-hidden"
        ></textarea>
      </div>
      <div class="flex justify-end gap-2 pt-2">
        <button type="button" onclick={closeUploadModal} class="btn btn-sm">Cancel</button>
        <button type="submit" disabled={uploadSubmitting} class="btn btn-sm btn-primary">
          {uploadSubmitting ? 'Creating...' : 'Create Build'}
        </button>
      </div>
    </form>
  {:else}
    <!-- Artifact upload step -->
    <div class="space-y-4">
      <div class="rounded-lg border border-border bg-surface-0 p-3">
        <div class="text-2xs text-text-tertiary mb-1">Build created</div>
        <div class="text-sm font-mono text-text-primary">{uploadBuildId?.slice(0, 12)}</div>
      </div>

      {#if uploadedArtifacts.length > 0}
        <div>
          <div class="text-2xs font-medium text-text-tertiary mb-2">Uploaded ({uploadedArtifacts.length})</div>
          <div class="space-y-1">
            {#each uploadedArtifacts as artifact}
              <div class="flex items-center gap-2 rounded border border-border bg-surface-0 px-3 py-1.5 text-sm">
                <span class="flex-1 font-mono text-text-primary truncate">{artifact.name}</span>
                <span class="text-2xs text-success">Uploaded</span>
              </div>
            {/each}
          </div>
        </div>
      {/if}

      <div class="rounded-lg border-2 border-dashed border-border bg-surface-0 p-4">
        <div class="text-sm font-medium text-text-primary mb-3">Add Artifact</div>
        <div class="grid grid-cols-1 gap-3 sm:grid-cols-2 mb-3">
          <Select
            bind:value={artifactRole}
            label="Role"
            placeholder="Select role"
            options={[
              { value: 'app', label: 'App' },
              { value: 'comms', label: 'Comms' },
              { value: 'modem', label: 'Modem' },
            ]}
          />
          <Select
            bind:value={artifactProcessor}
            label="Processor"
            placeholder="Select processor"
            options={[
              { value: 'nrf52840', label: 'nRF52840' },
              { value: 'nrf9151', label: 'nRF9151' },
            ]}
          />
        </div>
        <label
          for="upload-artifact-file"
          class="flex cursor-pointer flex-col items-center gap-2 rounded-lg border border-dashed border-border p-4 transition-colors hover:border-text-tertiary hover:bg-surface-1"
        >
          <Upload size={20} class="text-text-tertiary" />
          <span class="text-2xs text-text-tertiary">
            {uploadingFile ? 'Uploading...' : 'Click to select .hex or .cfw file'}
          </span>
          <input
            id="upload-artifact-file"
            type="file"
            accept=".hex,.cfw,.bin,.json"
            class="hidden"
            disabled={uploadingFile}
            onchange={(e) => {
              const input = e.target as HTMLInputElement;
              const file = input.files?.[0];
              if (file) {
                handleArtifactUpload(file, artifactRole, artifactProcessor);
              }
              input.value = '';
            }}
          />
        </label>
      </div>

      <div class="flex justify-end gap-2 pt-2">
        <button onclick={closeUploadModal} class="btn btn-sm btn-primary">
          Done
        </button>
      </div>
    </div>
  {/if}
</Modal>
