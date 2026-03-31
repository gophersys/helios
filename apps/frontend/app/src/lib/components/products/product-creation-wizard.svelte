<script lang="ts">
  import { ChevronLeft, ChevronRight, Check, Loader2, Cpu, CircuitBoard } from 'lucide-svelte';
  import { apiFetch, api } from '$lib/api';
  import type { ApiResponse } from '$lib/types';
  import type {
    BoardBranchesResponse,
    BoardSummary,
    BoardDetail,
    BuildConfig,
  } from '$lib/types/models';

  interface Props {
    onCreated: () => void;
    onCancel: () => void;
  }

  let { onCreated, onCancel }: Props = $props();

  // Wizard state
  let step = $state(1);
  let error = $state<string | null>(null);

  // Step 1: Branch selection
  let branches = $state<string[]>([]);
  let tags = $state<string[]>([]);
  let selectedBranch = $state('');
  let loadingBranches = $state(false);

  // Step 2: Board family selection
  let boardSummaries = $state<BoardSummary[]>([]);
  let selectedFamily = $state('');
  let loadingBoards = $state(false);

  // Step 3: Board detail
  let boardDetail = $state<BoardDetail | null>(null);
  let loadingDetail = $state(false);

  // Step 4: Confirm fields
  let productName = $state('');
  let productSlug = $state('');
  let productDescription = $state('');
  let ncsVersion = $state('v2.9.0');
  let targets = $state<Record<string, { soc: string; appId: number; role: string }>>({});
  let deviceType = $state(0);
  let deviceVariant = $state(0);
  let triggerBranches = $state('main');

  // Step 5: Submitting
  let submitting = $state(false);

  const stepLabels = ['Branch', 'Board', 'Configure', 'Create'];

  const selectedBoard = $derived(
    boardSummaries.find((b) => b.family === selectedFamily)
  );

  const canNext = $derived.by(() => {
    switch (step) {
      case 1: return selectedBranch !== '';
      case 2: return selectedFamily !== '';
      case 3: return productName.trim() !== '' && Object.keys(targets).length > 0;
      default: return false;
    }
  });

  async function loadBranches() {
    loadingBranches = true;
    error = null;
    try {
      const res = await apiFetch<ApiResponse<BoardBranchesResponse>>('/v2/products/boards/branches');
      branches = res.data.branches;
      tags = res.data.tags;
      if (branches.includes('main')) selectedBranch = 'main';
      else if (branches.length > 0) selectedBranch = branches[0];
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load branches';
    } finally {
      loadingBranches = false;
    }
  }

  async function loadBoards() {
    loadingBoards = true;
    error = null;
    try {
      const res = await apiFetch<ApiResponse<BoardSummary[]>>(
        `/v2/products/boards/discover?branch=${encodeURIComponent(selectedBranch)}`
      );
      boardSummaries = res.data;
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to discover boards';
    } finally {
      loadingBoards = false;
    }
  }

  async function loadBoardDetail() {
    loadingDetail = true;
    error = null;
    try {
      const res = await apiFetch<ApiResponse<BoardDetail>>(
        `/v2/products/boards/discover/${encodeURIComponent(selectedFamily)}?branch=${encodeURIComponent(selectedBranch)}`
      );
      boardDetail = res.data;
      // Auto-populate step 4 fields from discovery
      productName = boardDetail.family.charAt(0).toUpperCase() + boardDetail.family.slice(1);
      productSlug = boardDetail.family;
      // Collect unique SoCs across all revisions
      const allSocs = [...new Set(boardDetail.revisions.flatMap((r) => r.socs))];
      // Build targets from SoCs
      const newTargets: Record<string, { soc: string; appId: number; role: string }> = {};
      if (allSocs.length === 1) {
        newTargets['app'] = { soc: allSocs[0], appId: 0, role: 'application' };
      } else if (allSocs.length >= 2) {
        // Convention: nrf52840 = app, nrf9151 = comms
        const appSoc = allSocs.find((s) => s.includes('52840')) || allSocs[0];
        const commsSoc = allSocs.find((s) => s.includes('9151') || s.includes('9161')) || allSocs[1];
        newTargets['app'] = { soc: appSoc, appId: 0, role: 'application' };
        if (commsSoc !== appSoc) {
          newTargets['comms'] = { soc: commsSoc, appId: 0, role: 'communications' };
        }
      }
      targets = newTargets;
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load board details';
    } finally {
      loadingDetail = false;
    }
  }

  function handleNext() {
    if (!canNext) return;
    error = null;

    if (step === 1) {
      loadBoards();
    } else if (step === 2) {
      loadBoardDetail();
    }

    step = Math.min(step + 1, 4);
  }

  function handleBack() {
    error = null;
    step = Math.max(step - 1, 1);
  }

  async function handleCreate() {
    submitting = true;
    error = null;

    const buildConfig: BuildConfig = {
      board: productSlug,
      ncsVersion,
      boardRoot: 'ck_boards',
      hasVsmMerge: false,
      hasFips: false,
      confFiles: Object.fromEntries(Object.keys(targets).map((k) => [k, ['prj.conf']])),
      overlays: Object.fromEntries(Object.keys(targets).map((k) => [k, []])),
      postBuild: ['sign_mcuboot'],
      cfw: { deviceType, deviceVariant },
    };

    // Build per-revision targets: each revision gets targets based on its SoCs
    // matched against the user-configured targets (which map SoC → role/appId)
    const targetBySoc = new Map(Object.values(targets).map((t) => [t.soc, t]));

    try {
      await api.post('/v2/products', {
        name: productName.trim(),
        slug: productSlug.trim() || null,
        description: productDescription.trim() || null,
        board: boardDetail
          ? {
              ckBoardsFamily: selectedFamily,
              revisions: boardDetail.revisions.map((r) => ({
                version: r.version,
                ckBoardsName: r.ckBoardsName,
                socs: r.socs,
                targets: r.socs
                  .map((soc) => targetBySoc.get(soc))
                  .filter((t): t is NonNullable<typeof t> => t != null)
                  .map((t) => ({ role: t.role, soc: t.soc, appId: t.appId })),
              })),
            }
          : null,
        buildConfig,
        triggerBranches: triggerBranches.split(',').map((b) => b.trim()).filter(Boolean),
      });
      onCreated();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to create product';
    } finally {
      submitting = false;
    }
  }

  // Load branches on mount
  $effect(() => {
    loadBranches();
  });

</script>

<div class="rounded-xl border border-border bg-surface-1">
  <!-- Step indicator -->
  <div class="flex items-center border-b border-border px-6 py-4">
    {#each stepLabels as label, i}
      {@const stepNum = i + 1}
      <div class="flex items-center gap-2">
        <div
          class={[
            'flex h-7 w-7 items-center justify-center rounded-full text-2xs font-semibold transition-colors',
            step === stepNum
              ? 'bg-accent text-white'
              : step > stepNum
                ? 'bg-success text-white'
                : 'bg-surface-2 text-text-tertiary',
          ].join(' ')}
        >
          {#if step > stepNum}
            <Check size={14} />
          {:else}
            {stepNum}
          {/if}
        </div>
        <span
          class={[
            'text-xs font-medium',
            step === stepNum ? 'text-text-primary' : 'text-text-tertiary',
          ].join(' ')}
        >
          {label}
        </span>
      </div>
      {#if i < stepLabels.length - 1}
        <div class="mx-3 h-px flex-1 bg-border"></div>
      {/if}
    {/each}
  </div>

  <!-- Content -->
  <div class="min-h-[320px] p-6">
    {#if error}
      <div class="mb-4 rounded-lg border border-error bg-error-muted p-3 text-sm text-error">
        {error}
      </div>
    {/if}

    <!-- Step 1: Branch -->
    {#if step === 1}
      <div>
        <h3 class="mb-1 text-base font-semibold text-text-primary">Select ck_boards branch</h3>
        <p class="mb-4 text-sm text-text-secondary">
          Choose which branch of the hardware definitions repository to scan for boards.
        </p>
        {#if loadingBranches}
          <div class="flex items-center gap-2 py-8 text-sm text-text-tertiary">
            <Loader2 size={16} class="animate-spin" /> Loading branches...
          </div>
        {:else}
          <div class="max-w-md">
            <label for="branch-select" class="mb-1 block text-2xs font-medium text-text-tertiary">Branch</label>
            <select
              id="branch-select"
              bind:value={selectedBranch}
              class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none"
            >
              <optgroup label="Branches">
                {#each branches as branch}
                  <option value={branch}>{branch}</option>
                {/each}
              </optgroup>
              {#if tags.length > 0}
                <optgroup label="Tags">
                  {#each tags as tag}
                    <option value={tag}>{tag}</option>
                  {/each}
                </optgroup>
              {/if}
            </select>
          </div>
        {/if}
      </div>
    {/if}

    <!-- Step 2: Board Family -->
    {#if step === 2}
      <div>
        <h3 class="mb-1 text-base font-semibold text-text-primary">Select product family</h3>
        <p class="mb-4 text-sm text-text-secondary">
          Choose a product family discovered on the <code class="rounded bg-surface-2 px-1.5 py-0.5 text-2xs font-mono">{selectedBranch}</code> branch.
        </p>
        {#if loadingBoards}
          <div class="flex items-center gap-2 py-8 text-sm text-text-tertiary">
            <Loader2 size={16} class="animate-spin" /> Scanning boards...
          </div>
        {:else if boardSummaries.length === 0}
          <p class="py-8 text-center text-sm text-text-tertiary">No board families found on this branch.</p>
        {:else}
          <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {#each boardSummaries as board}
              <button
                onclick={() => (selectedFamily = board.family)}
                class={[
                  'rounded-lg border p-4 text-left transition-colors',
                  selectedFamily === board.family
                    ? 'border-accent bg-accent/5'
                    : 'border-border bg-surface-0 hover:border-accent/50',
                ].join(' ')}
              >
                <div class="mb-2 flex items-center gap-2">
                  <CircuitBoard size={16} class={selectedFamily === board.family ? 'text-accent' : 'text-text-tertiary'} />
                  <span class="text-sm font-semibold text-text-primary capitalize">{board.family}</span>
                </div>
                <div class="space-y-1 text-2xs text-text-tertiary">
                  <div>
                    {board.revisions.length} revision{board.revisions.length !== 1 ? 's' : ''}:
                    {board.revisions.map((r) => r.version.toUpperCase()).join(', ')}
                  </div>
                  <div class="flex items-center gap-1">
                    <Cpu size={12} />
                    <span>{[...new Set(board.revisions.flatMap((r) => r.socs))].join(', ')}</span>
                  </div>
                </div>
              </button>
            {/each}
          </div>
        {/if}
      </div>
    {/if}

    <!-- Step 3: Configure -->
    {#if step === 3}
      <div>
        <h3 class="mb-1 text-base font-semibold text-text-primary">Configure product</h3>
        <p class="mb-4 text-sm text-text-secondary">
          Confirm or override the auto-populated fields. AppIDs and device type must be set manually.
        </p>
        <div class="space-y-4">
          <!-- Product info -->
          <div class="grid gap-3 sm:grid-cols-2">
            <label class="block">
              <span class="mb-1 block text-2xs font-medium text-text-tertiary">Product Name *</span>
              <input
                type="text"
                required
                bind:value={productName}
                class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
              />
            </label>
            <label class="block">
              <span class="mb-1 block text-2xs font-medium text-text-tertiary">Slug</span>
              <input
                type="text"
                bind:value={productSlug}
                class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm font-mono text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
              />
            </label>
          </div>
          <label class="block">
            <span class="mb-1 block text-2xs font-medium text-text-tertiary">Description</span>
            <input
              type="text"
              bind:value={productDescription}
              placeholder="Optional description"
              class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
            />
          </label>

          <!-- NCS Version -->
          <label class="block max-w-xs">
            <span class="mb-1 block text-2xs font-medium text-text-tertiary">NCS Version</span>
            <input
              type="text"
              bind:value={ncsVersion}
              class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm font-mono text-text-primary focus:border-accent focus:outline-none"
            />
          </label>

          <!-- Targets (AppIDs) -->
          <div>
            <span class="mb-2 block text-xs font-medium text-text-primary">Build Targets (AppIDs)</span>
            <div class="grid gap-3 sm:grid-cols-2">
              {#each Object.entries(targets) as [role, target]}
                <div class="rounded-lg border border-border bg-surface-0 p-3">
                  <div class="mb-2 flex items-center gap-2">
                    <Cpu size={14} class="text-accent" />
                    <span class="text-xs font-semibold capitalize text-text-primary">{role}</span>
                    <span class="font-mono text-2xs text-text-tertiary">({target.soc})</span>
                  </div>
                  <label class="block">
                    <span class="mb-1 block text-2xs text-text-tertiary">AppID *</span>
                    <input
                      type="number"
                      min="0"
                      bind:value={target.appId}
                      placeholder="e.g. 109"
                      class="w-full rounded-lg border border-border bg-surface-1 px-3 py-1.5 text-sm font-mono text-text-primary focus:border-accent focus:outline-none"
                    />
                  </label>
                </div>
              {/each}
            </div>
          </div>

          <!-- CFW Config -->
          <div class="grid gap-3 sm:grid-cols-2">
            <label class="block">
              <span class="mb-1 block text-2xs font-medium text-text-tertiary">Device Type *</span>
              <input
                type="number"
                min="0"
                bind:value={deviceType}
                class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm font-mono text-text-primary focus:border-accent focus:outline-none"
              />
            </label>
            <label class="block">
              <span class="mb-1 block text-2xs font-medium text-text-tertiary">Device Variant *</span>
              <input
                type="number"
                min="0"
                bind:value={deviceVariant}
                class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm font-mono text-text-primary focus:border-accent focus:outline-none"
              />
            </label>
          </div>

          <!-- Trigger branches -->
          <label class="block">
            <span class="mb-1 block text-2xs font-medium text-text-tertiary">Trigger Branches (comma-separated)</span>
            <input
              type="text"
              bind:value={triggerBranches}
              placeholder="main, release/*"
              class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm font-mono text-text-primary focus:border-accent focus:outline-none"
            />
          </label>
        </div>
      </div>
    {/if}

    <!-- Step 5: Create -->
    {#if step === 4}
      <div>
        <h3 class="mb-1 text-base font-semibold text-text-primary">Confirm and create</h3>
        <p class="mb-4 text-sm text-text-secondary">
          Review the final configuration before creating the product.
        </p>
        <div class="space-y-3">
          <div class="rounded-lg border border-border bg-surface-0 p-4">
            <dl class="space-y-2 text-sm">
              {#each [
                ['Product', productName],
                ['Slug', productSlug || '(auto)'],
                ['Board Family', selectedFamily],
                ['Branch', selectedBranch],
                ['NCS Version', ncsVersion],
                ['Device Type', String(deviceType)],
                ['Device Variant', String(deviceVariant)],
                ['Trigger Branches', triggerBranches || '(none)'],
              ] as [label, value]}
                <div class="flex items-baseline justify-between border-b border-border-subtle py-1 last:border-0">
                  <dt class="text-xs text-text-tertiary">{label}</dt>
                  <dd class="font-mono text-xs text-text-primary">{value}</dd>
                </div>
              {/each}
            </dl>
          </div>

          <!-- Targets summary -->
          <div class="rounded-lg border border-border bg-surface-0 p-4">
            <span class="mb-2 block text-xs font-medium text-text-tertiary">Build Targets</span>
            <div class="grid gap-2 sm:grid-cols-2">
              {#each Object.entries(targets) as [role, target]}
                <div class="flex items-center justify-between rounded border border-border-subtle bg-surface-1 px-3 py-2">
                  <span class="text-xs font-medium capitalize text-text-primary">{role}</span>
                  <span class="font-mono text-2xs text-text-secondary">
                    {target.soc} &middot; AppID {target.appId}
                  </span>
                </div>
              {/each}
            </div>
          </div>
        </div>
      </div>
    {/if}
  </div>

  <!-- Footer buttons -->
  <div class="flex items-center justify-between border-t border-border px-6 py-4">
    <button
      onclick={step === 1 ? onCancel : handleBack}
      class="flex items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-medium text-text-secondary hover:bg-surface-2"
    >
      <ChevronLeft size={16} />
      {step === 1 ? 'Cancel' : 'Back'}
    </button>

    {#if step < 4}
      <button
        onclick={handleNext}
        disabled={!canNext}
        class="flex items-center gap-1.5 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
      >
        Next
        <ChevronRight size={16} />
      </button>
    {:else}
      <button
        onclick={handleCreate}
        disabled={submitting}
        class="flex items-center gap-1.5 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
      >
        {#if submitting}
          <Loader2 size={16} class="animate-spin" />
          Creating...
        {:else}
          <Check size={16} />
          Create Product
        {/if}
      </button>
    {/if}
  </div>
</div>
