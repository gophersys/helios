<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import {
    ChevronLeft,
    ChevronRight,
    ChevronsLeft,
    ChevronsRight,
    Clock,
    Cpu,
    FlaskConical,
    GitBranch,
    GitCommit,
    Grid3X3,
    Hammer,
    Layers,
    Moon,
    Package,
    Plus,
    Radio,
    RefreshCw,
    Upload,
    X,
    Zap,
  } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';
  import type { BuildJob, BuildArtifact, BuildRunDetail, MatrixLabel, ValidationStage } from '$lib/types/ci';
  import { MATRIX_LABEL_DISPLAY, STAGE_DISPLAY } from '$lib/types/ci';
  import type { Pagination, Product } from '$lib/types/models';
  import { fetchBuildRuns, fetchBuilds, triggerBuildRun, createManualBuild, uploadBuildArtifact } from '$lib/services/ci';
  import { fetchProducts as fetchProductList } from '$lib/services/products';
  import { getTriggerConfig, getProductInfo } from '$lib/constants/builds';
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

  const auth = getAuth();
  const canManage = $derived(auth.hasPermission('builds:manage'));

  const STATUS_OPTIONS = [
    { value: 'BUILDING', label: 'Building' },
    { value: 'SUCCESS', label: 'Success' },
    { value: 'FAILED', label: 'Failed' },
    { value: 'CANCELLED', label: 'Cancelled' },
  ];

  const STAGE_OPTIONS = [
    { value: 'smoke', label: 'Smoke' },
    { value: 'silicon', label: 'Silicon' },
    { value: 'integration', label: 'Integration' },
    { value: 'nightly', label: 'Nightly' },
    { value: 'fuota', label: 'FUOTA' },
  ];

  const TRIGGER_TYPE_OPTIONS = [
    { value: 'worker', label: 'Worker' },
    { value: 'manual', label: 'Manual' },
    { value: 'webhook', label: 'Webhook' },
  ];

  // Trigger type badge config for build jobs
  const TRIGGER_TYPE_BADGE: Record<string, { color: string; label: string }> = {
    worker: { color: 'text-text-secondary bg-surface-2', label: 'Worker' },
    manual: { color: 'text-accent bg-accent-muted', label: 'Manual' },
    webhook: { color: 'text-info bg-info-muted', label: 'Webhook' },
  };

  // Per-stage icon and color config for list badges
  const STAGE_BADGE: Record<string, { icon: typeof Zap; color: string }> = {
    smoke:       { icon: Zap,    color: 'text-text-secondary bg-surface-2' },
    silicon:     { icon: Cpu,    color: 'text-text-secondary bg-surface-2' },
    integration: { icon: Layers, color: 'text-text-secondary bg-surface-2' },
    nightly:     { icon: Moon,   color: 'text-warning bg-warning-muted' },
    fuota:       { icon: Radio,  color: 'text-info bg-info-muted' },
  };

  // Get build matrix summary for validation buildRuns
  function getMatrixSummary(pipeline: BuildRunDetail): string | null {
    if (!buildRun.builds || buildRun.builds.length === 0) return null;
    if (!buildRun.matrixMode) return null;

    const statusCounts = new Map<string, number>();
    for (const build of buildRun.builds) {
      const status = build.status;
      statusCounts.set(status, (statusCounts.get(status) || 0) + 1);
    }

    const parts: string[] = [];
    const order = ['SUCCESS', 'BUILDING', 'FAILED', 'QUEUED', 'CANCELLED'];
    for (const status of order) {
      const count = statusCounts.get(status);
      if (count && count > 0) {
        parts.push(`${count} ${status.toLowerCase()}`);
      }
    }
    return parts.join(', ');
  }

  // Get unique variants from builds
  function getVariantSummary(pipeline: BuildRunDetail): string {
    if (!buildRun.builds || buildRun.builds.length === 0) return '';
    const variants = new Set(buildRun.builds.map(b => b.variant));
    return Array.from(variants).join(', ');
  }

  type ViewMode = 'buildRuns' | 'jobs';
  let viewMode = $state<ViewMode>('jobs');

  let buildRuns = $state<BuildRunDetail[]>([]);
  let buildJobs = $state<BuildJob[]>([]);
  let pagination = $state<Pagination>({ page: 1, limit: 25, total: 0, pages: 0 });
  let loading = $state(true);
  let error = $state<string | null>(null);
  let statusFilter = $state('');
  let productFilter = $state('');
  let branchFilter = $state('');
  let stageFilter = $state('');
  let triggerTypeFilter = $state('');
  let currentPage = $state(1);
  let refreshing = $state(false);
  let productOptions = $state<{ value: string; label: string }[]>([]);

  // Upload modal state
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

  // Trigger form
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

  async function loadPipelines(): Promise<void> {
    try {
      const res = await fetchBuildRuns({
        page: currentPage,
        limit: 25,
        status: statusFilter || undefined,
        product: productFilter || undefined,
        branch: branchFilter || undefined,
        matrixMode: stageFilter || undefined,
      });
      buildRuns = res.data;
      pagination = res.pagination;
      error = null;

      // Extract unique products for filter dropdown (only on first load)
      if (productOptions.length === 0 && res.data.length > 0) {
        const products = new Set<string>();
        res.data.forEach(p => { if (p.product) products.add(p.product); });
        productOptions = Array.from(products).sort().map(p => ({ value: p, label: p }));
      }
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to load buildRuns';
    } finally {
      loading = false;
      refreshing = false;
    }
  }

  async function loadBuildJobs(): Promise<void> {
    try {
      const res = await fetchBuilds({
        page: currentPage,
        limit: 25,
        status: statusFilter || undefined,
        triggerType: triggerTypeFilter || undefined,
      });
      buildJobs = res.data;
      pagination = res.pagination;
      error = null;
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to load build jobs';
    } finally {
      loading = false;
      refreshing = false;
    }
  }

  function loadData(): void {
    if (viewMode === 'buildRuns') loadPipelines();
    else loadBuildJobs();
  }

  function refresh(): void {
    refreshing = true;
    loadData();
  }

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
      const buildRun = await triggerBuildRun({
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
      goto(`/builds/runs/${buildRun.id}`);
    } catch (err: unknown) {
      error = err instanceof Error ? err.message : 'Failed to trigger build';
    } finally {
      submitting = false;
    }
  }

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

  function pipelineDuration(pipeline: BuildRunDetail): string {
    // For list view, calculate from startedAt/finishedAt or use build durations
    if (buildRun.startedAt && buildRun.finishedAt) {
      const duration = new Date(buildRun.finishedAt).getTime() - new Date(buildRun.startedAt).getTime();
      return formatDuration(duration);
    }
    if (buildRun.builds && buildRun.builds.length > 0) {
      const totalSeconds = buildRun.builds.reduce((sum, b) => sum + (b.durationSeconds ?? 0), 0);
      if (totalSeconds > 0) return formatDuration(totalSeconds * 1000);
    }
    return '--';
  }

  onMount(() => {
    if (!auth.hasPermission('builds:view')) {
      goto('/');
      return;
    }
    loadData();

    // Auto-refresh every 10s
    const interval = setInterval(() => {
      loadData();
    }, 10000);
    return () => clearInterval(interval);
  });

  $effect(() => {
    const _p = currentPage;
    loadData();
  });

  $effect(() => {
    const _s = statusFilter;
    const _p = productFilter;
    const _b = branchFilter;
    const _st = stageFilter;
    const _tt = triggerTypeFilter;
    currentPage = 1;
  });
</script>

<svelte:head>
  <title>Builds - Concord</title>
</svelte:head>

<div class="animate-fade-in">
  <div class="mb-6">
    <PageHeader
      title="Builds"
      description="Firmware build buildRuns - build, flash, and validate in one flow."
    />
  </div>

  <ErrorAlert message={error} />

  {#if showForm}
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

  <div class="mb-4 flex flex-wrap items-center gap-3">
    <Select
      bind:value={statusFilter}
      placeholder="All statuses"
      options={STATUS_OPTIONS}
    />
    {#if productOptions.length > 0}
      <Select
        bind:value={productFilter}
        placeholder="All products"
        options={productOptions}
      />
    {/if}
    <Select
      bind:value={stageFilter}
      placeholder="All stages"
      options={STAGE_OPTIONS}
    />
    <Select
      bind:value={triggerTypeFilter}
      placeholder="All triggers"
      options={TRIGGER_TYPE_OPTIONS}
    />
    <TextInput
      bind:value={branchFilter}
      placeholder="Filter by branch..."
    />
    <span class="ml-auto text-2xs text-text-tertiary">
      {pagination.total} builds
    </span>
    <button
      onclick={refresh}
      disabled={refreshing}
      class="btn btn-sm flex items-center gap-1.5"
      title="Refresh"
    >
      <RefreshCw size={14} class={refreshing ? 'animate-spin' : ''} />
    </button>
    {#if canManage}
      <button
        onclick={() => openUploadModal()}
        class="btn btn-sm flex items-center gap-1.5"
      >
        <Upload size={14} />
        Upload Build
      </button>
      <button
        onclick={() => { showForm = true; }}
        class="btn btn-sm btn-primary flex items-center gap-1.5"
      >
        <Plus size={14} />
        Trigger Build
      </button>
    {/if}
  </div>

  <!-- View toggle -->
  <div class="mb-4 flex gap-1 border-b border-border">
    <button
      onclick={() => { viewMode = 'jobs'; loading = true; loadData(); }}
      class="px-4 py-2 text-sm font-medium transition-colors {viewMode === 'jobs' ? 'border-b-2 border-accent text-accent' : 'text-text-tertiary hover:text-text-secondary'}"
    >
      Build Jobs
    </button>
    <button
      onclick={() => { viewMode = 'buildRuns'; loading = true; loadData(); }}
      class="px-4 py-2 text-sm font-medium transition-colors {viewMode === 'buildRuns' ? 'border-b-2 border-accent text-accent' : 'text-text-tertiary hover:text-text-secondary'}"
    >
      Pipelines
    </button>
  </div>

  {#if loading}
    <LoadingState message="Loading {viewMode === 'buildRuns' ? 'buildRuns' : 'build jobs'}..." />
  {:else if viewMode === 'jobs'}
    {#if buildJobs.length === 0}
      <EmptyState message="No build jobs found." />
    {:else}
      <div class="space-y-2">
        {#each buildJobs as build (build.id)}
          <button
            onclick={() => goto(`/builds/${build.status === 'CACHED' && build.reusedFromId ? build.reusedFromId : build.id}`)}
            class="w-full rounded-lg border border-border bg-surface-0 px-4 py-3 text-left transition-colors hover:bg-surface-1"
          >
            <div class="flex items-center justify-between gap-4">
              <div class="flex items-center gap-3 min-w-0">
                <Hammer size={16} class="flex-shrink-0 text-text-tertiary" />
                <span class="text-sm font-medium text-text-primary">
                  {build.product || 'Unknown'}
                </span>
                <span class="inline-flex items-center rounded bg-surface-2 px-1.5 py-0.5 text-2xs text-text-secondary font-mono">
                  {build.variant}
                </span>
                {#if build.board}
                  <span class="inline-flex items-center rounded bg-surface-2 px-1.5 py-0.5 text-2xs text-text-tertiary">
                    {build.board}
                  </span>
                {/if}
                {#if build.branch}
                  <span class="inline-flex items-center gap-1 rounded bg-surface-2 px-1.5 py-0.5 text-2xs text-text-secondary">
                    <GitBranch size={10} />
                    {build.branch}
                  </span>
                {/if}
                {#if build.commitSha}
                  <span class="inline-flex items-center gap-1 rounded bg-info-muted px-1.5 py-0.5 text-2xs text-info font-mono font-medium">
                    <GitCommit size={10} />
                    {build.commitSha.slice(0, 7)}
                  </span>
                {/if}
                {#if build.versionString}
                  <span class="inline-flex items-center rounded bg-accent-muted px-1.5 py-0.5 text-2xs text-accent font-mono font-medium">
                    v{build.versionString}
                  </span>
                {/if}
                {#if build.triggerType && build.triggerType !== 'worker'}
                  {@const triggerBadge = TRIGGER_TYPE_BADGE[build.triggerType] || TRIGGER_TYPE_BADGE.worker}
                  <span class="inline-flex items-center rounded px-1.5 py-0.5 text-2xs font-medium {triggerBadge.color}">
                    {triggerBadge.label}
                  </span>
                {/if}
                <StatusBadge status={build.status} />
              </div>
              <div class="flex items-center gap-3 text-2xs text-text-tertiary flex-shrink-0">
                {#if build.durationSeconds}
                  <span class="tabular-nums">{formatDuration(build.durationSeconds * 1000)}</span>
                {/if}
                <span title={formatDateTime(build.createdAt)}>
                  {formatTimeAgo(build.createdAt)}
                </span>
              </div>
            </div>
            {#if build.configFlags?.versionOverride}
              <div class="mt-1.5 text-2xs text-text-tertiary">
                Version override: <span class="font-mono text-text-secondary">{build.configFlags.versionOverride}</span>
              </div>
            {/if}
            {#if build.artifacts && build.artifacts.length > 0}
              <div class="mt-1.5 flex items-center gap-2 text-2xs text-text-tertiary">
                <span>{build.artifacts.length} artifact{build.artifacts.length !== 1 ? 's' : ''}</span>
                {#each build.artifacts.slice(0, 4) as art}
                  <span class="font-mono bg-surface-2 px-1 py-0.5 rounded">{art.name}</span>
                {/each}
                {#if build.artifacts.length > 4}
                  <span>+{build.artifacts.length - 4} more</span>
                {/if}
              </div>
            {/if}
          </button>
        {/each}
      </div>
    {/if}
  {:else if buildRuns.length === 0}
    <EmptyState message="No buildRuns found." />
  {:else}
    <div class="space-y-2">
      {#each buildRuns as buildRun (buildRun.id)}
        {@const trigger = getTriggerConfig(buildRun.triggerType)}
        {@const productInfo = getProductInfo(buildRun.product ?? '')}
        <button
          onclick={() => goto(`/builds/runs/${buildRun.id}`)}
          class="w-full rounded-lg border border-border bg-surface-0 px-4 py-3 text-left transition-colors hover:bg-surface-1"
        >
          <div class="flex items-center justify-between gap-4 mb-2">
            <div class="flex items-center gap-3 min-w-0">
              <Package size={16} class="flex-shrink-0 text-text-tertiary" />
              <span class="text-sm font-medium text-text-primary truncate">
                {productInfo.name}
              </span>
              {#if productInfo.rev}
                <span class="inline-flex items-center gap-1 rounded bg-info-muted px-1.5 py-0.5 text-2xs text-info font-medium">
                  {productInfo.rev}
                </span>
              {/if}
              {#if buildRun.branch}
                <span class="inline-flex items-center gap-1 rounded bg-surface-2 px-1.5 py-0.5 text-2xs text-text-secondary">
                  <GitBranch size={10} />
                  {buildRun.branch}
                </span>
              {/if}
              {#if buildRun.commitSha}
                <span class="inline-flex items-center gap-1 rounded bg-surface-2 px-1.5 py-0.5 text-2xs font-mono text-text-tertiary">
                  <GitCommit size={10} />
                  {buildRun.commitSha.slice(0, 7)}
                </span>
              {/if}
              <StatusBadge status={buildRun.status} />
            </div>
            <div class="flex items-center gap-3 text-2xs text-text-tertiary flex-shrink-0">
              <span class="tabular-nums">{pipelineDuration( buildRun)}</span>
              <span title={formatDateTime(buildRun.createdAt)}>
                {formatTimeAgo(buildRun.createdAt)}
              </span>
            </div>
          </div>
          <!-- Build info row with trigger source -->
          <div class="flex items-center gap-3 text-2xs flex-wrap">
            <span class="text-text-tertiary">
              {buildRun.completedBuilds ?? 0}/{buildRun.expectedBuilds ?? 0} builds
            </span>
            <!-- Trigger source badge (only for non-manual triggers) -->
            {#if buildRun.triggerType && buildRun.triggerType !== 'manual'}
              {@const TriggerIcon = trigger.icon}
              <span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded {trigger.color} font-medium">
                <TriggerIcon size={10} />
                {trigger.label}
              </span>
            {/if}
            <!-- Stage indicator -->
            {#if buildRun.matrixMode && STAGE_BADGE[buildRun.matrixMode]}
              {@const badge = STAGE_BADGE[buildRun.matrixMode]}
              {@const stage = STAGE_DISPLAY[buildRun.matrixMode as ValidationStage]}
              {@const BadgeIcon = badge.icon}
              <span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded {badge.color} font-medium" title={stage?.description ?? buildRun.matrixMode}>
                <BadgeIcon size={10} />
                {stage?.name ?? buildRun.matrixMode}
              </span>
            {/if}
            <!-- Validation indicator -->
            {#if buildRun.validationRunId}
              <span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-success-muted text-success font-medium" title="Validation run linked">
                <FlaskConical size={10} />
                Validated
              </span>
            {:else if buildRun.autoValidate}
              <span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-accent-muted text-accent font-medium" title="Will auto-trigger validation">
                <FlaskConical size={10} />
                Auto
              </span>
            {/if}
            <!-- Build summary -->
            {#if buildRun.builds && buildRun.builds.length > 0}
              {@const summary = getMatrixSummary( buildRun)}
              {#if summary}
                <span class="text-text-tertiary">{summary}</span>
              {:else}
                <span class="text-text-tertiary">
                  {getVariantSummary( buildRun)}
                </span>
              {/if}
            {/if}
            <!-- Show build versions with status colors and duration -->
            {#if buildRun.builds && buildRun.builds.length > 0}
              <div class="flex items-center gap-1.5 ml-auto">
                {#each buildRun.builds.slice(0, 6) as build}
                  <span
                    class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-2xs font-mono {
                      build.status === 'SUCCESS' ? 'bg-success-muted text-success' :
                      build.status === 'FAILED' ? 'bg-error-muted text-error' :
                      build.status === 'BUILDING' ? 'bg-warning-muted text-warning animate-pulse' :
                      build.status === 'BLOCKED' ? 'bg-surface-2 text-text-tertiary' :
                      'bg-surface-2 text-text-tertiary'
                    }"
                    title="{build.variant ?? ''} {build.versionString ?? ''} - {build.status}{build.durationSeconds ? ` (${formatDuration(build.durationSeconds * 1000)})` : ''}"
                  >
                    {build.versionString ?? '...'}
                  </span>
                {/each}
                {#if buildRun.builds.length > 6}
                  <span class="text-2xs text-text-tertiary">+{buildRun.builds.length - 6}</span>
                {/if}
              </div>
            {/if}
          </div>
        </button>
      {/each}
    </div>
  {/if}

  {#if pagination.pages > 1}
    <div class="mt-4 flex items-center justify-between">
      <span class="text-2xs text-text-tertiary">
        Page {pagination.page} of {pagination.pages}
      </span>
      <div class="flex items-center gap-1">
        <button
          onclick={() => (currentPage = 1)}
          disabled={currentPage <= 1}
          aria-label="First page"
          class="rounded-lg p-2 text-text-secondary transition-colors hover:bg-surface-1 disabled:opacity-30 disabled:hover:bg-transparent"
        >
          <ChevronsLeft size={16} />
        </button>
        <button
          onclick={() => (currentPage = Math.max(1, currentPage - 1))}
          disabled={currentPage <= 1}
          aria-label="Previous page"
          class="rounded-lg p-2 text-text-secondary transition-colors hover:bg-surface-1 disabled:opacity-30 disabled:hover:bg-transparent"
        >
          <ChevronLeft size={16} />
        </button>
        <button
          onclick={() => (currentPage = Math.min(pagination.pages, currentPage + 1))}
          disabled={currentPage >= pagination.pages}
          aria-label="Next page"
          class="rounded-lg p-2 text-text-secondary transition-colors hover:bg-surface-1 disabled:opacity-30 disabled:hover:bg-transparent"
        >
          <ChevronRight size={16} />
        </button>
        <button
          onclick={() => (currentPage = pagination.pages)}
          disabled={currentPage >= pagination.pages}
          aria-label="Last page"
          class="rounded-lg p-2 text-text-secondary transition-colors hover:bg-surface-1 disabled:opacity-30 disabled:hover:bg-transparent"
        >
          <ChevronsRight size={16} />
        </button>
      </div>
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
          class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
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
