<script lang="ts">
  import { ChevronLeft, ChevronRight, Check, Loader2, Cpu, CircuitBoard, Zap } from 'lucide-svelte';
  import { apiFetch, api } from '$lib/api';
  import type { ApiResponse } from '$lib/types';
  import type {
    BoardBranchesResponse,
    BoardSummary,
    BoardDetail,
    DtsPeripheral,
    BuildConfig,
    BuildConfigTarget,
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

  // Step 2: Board selection
  let boardSummaries = $state<BoardSummary[]>([]);
  let selectedBoardName = $state('');
  let loadingBoards = $state(false);

  // Step 3: Board detail
  let boardDetail = $state<BoardDetail | null>(null);
  let loadingDetail = $state(false);

  // Step 4: Confirm fields
  let productName = $state('');
  let productSlug = $state('');
  let productDescription = $state('');
  let fwRepoSlug = $state('');
  let mfgRepoSlug = $state('');
  let ncsVersion = $state('v2.9.0');
  let targets = $state<Record<string, { soc: string; appId: number; role: string }>>({});
  let deviceType = $state(0);
  let deviceVariant = $state(0);
  let triggerBranches = $state('main');

  // Step 5: Submitting
  let submitting = $state(false);

  const stepLabels = ['Branch', 'Board', 'Review', 'Configure', 'Create'];

  const selectedBoard = $derived(
    boardSummaries.find((b) => b.board === selectedBoardName)
  );

  const canNext = $derived.by(() => {
    switch (step) {
      case 1: return selectedBranch !== '';
      case 2: return selectedBoardName !== '';
      case 3: return boardDetail !== null;
      case 4: return productName.trim() !== '' && Object.keys(targets).length > 0;
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
        `/v2/products/boards/discover/${encodeURIComponent(selectedBoardName)}?branch=${encodeURIComponent(selectedBranch)}`
      );
      boardDetail = res.data;
      // Auto-populate step 4 fields from discovery
      productName = boardDetail.board.charAt(0).toUpperCase() + boardDetail.board.slice(1);
      productSlug = boardDetail.board;
      fwRepoSlug = `${boardDetail.board}_fw`;
      mfgRepoSlug = `${boardDetail.board}_mfg_fw`;
      // Build targets from SoCs
      const newTargets: Record<string, { soc: string; appId: number; role: string }> = {};
      const socs = boardDetail.socs;
      if (socs.length === 1) {
        newTargets['app'] = { soc: socs[0], appId: 0, role: 'application' };
      } else if (socs.length >= 2) {
        // Convention: nrf52840 = app, nrf9151 = comms
        const appSoc = socs.find((s) => s.includes('52840')) || socs[0];
        const commsSoc = socs.find((s) => s.includes('9151') || s.includes('9161')) || socs[1];
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

    step = Math.min(step + 1, 5);
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
      targets: Object.fromEntries(
        Object.entries(targets).map(([key, t]) => [key, { soc: t.soc, appId: t.appId, role: t.role }])
      ),
      hasVsmMerge: false,
      hasFips: false,
      confFiles: Object.fromEntries(Object.keys(targets).map((k) => [k, ['prj.conf']])),
      overlays: Object.fromEntries(Object.keys(targets).map((k) => [k, []])),
      postBuild: ['sign_mcuboot'],
      cfw: { deviceType, deviceVariant },
    };

    try {
      await api.post('/v2/products', {
        name: productName.trim(),
        slug: productSlug.trim() || null,
        description: productDescription.trim() || null,
        repoSlug: fwRepoSlug.trim() || null,
        mfgRepoSlug: mfgRepoSlug.trim() || null,
        buildConfig,
        triggerBranches: triggerBranches.split(',').map((b) => b.trim()).filter(Boolean),
        boardDiscovery: boardDetail
          ? {
              branch: selectedBranch,
              board: selectedBoardName,
              socs: boardDetail.socs,
              revisions: boardDetail.revisions,
              variants: boardDetail.variants,
            }
          : null,
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

  function peripheralIcon(type: string): string {
    const map: Record<string, string> = {
      accelerometer: 'motion',
      charger: 'battery',
      'fuel-gauge': 'battery',
      ppg: 'heart',
      'ir-temp': 'thermometer',
      'gpio-expander': 'chip',
    };
    return map[type] || 'chip';
  }
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
            <label class="mb-1 block text-2xs font-medium text-text-tertiary">Branch</label>
            <select
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

    <!-- Step 2: Board -->
    {#if step === 2}
      <div>
        <h3 class="mb-1 text-base font-semibold text-text-primary">Select board</h3>
        <p class="mb-4 text-sm text-text-secondary">
          Choose a board discovered on the <code class="rounded bg-surface-2 px-1.5 py-0.5 text-2xs font-mono">{selectedBranch}</code> branch.
        </p>
        {#if loadingBoards}
          <div class="flex items-center gap-2 py-8 text-sm text-text-tertiary">
            <Loader2 size={16} class="animate-spin" /> Scanning boards...
          </div>
        {:else if boardSummaries.length === 0}
          <p class="py-8 text-center text-sm text-text-tertiary">No boards found on this branch.</p>
        {:else}
          <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {#each boardSummaries as board}
              <button
                onclick={() => (selectedBoardName = board.board)}
                class={[
                  'rounded-lg border p-4 text-left transition-colors',
                  selectedBoardName === board.board
                    ? 'border-accent bg-accent/5'
                    : 'border-border bg-surface-0 hover:border-accent/50',
                ].join(' ')}
              >
                <div class="mb-2 flex items-center gap-2">
                  <CircuitBoard size={16} class={selectedBoardName === board.board ? 'text-accent' : 'text-text-tertiary'} />
                  <span class="text-sm font-semibold text-text-primary">{board.board}</span>
                </div>
                <div class="space-y-1 text-2xs text-text-tertiary">
                  <div class="flex items-center gap-1">
                    <Cpu size={12} />
                    <span>{board.socs.join(', ')}</span>
                  </div>
                  <div>
                    {board.revisions.length} revision{board.revisions.length !== 1 ? 's' : ''} &middot;
                    {board.variants.length} variant{board.variants.length !== 1 ? 's' : ''}
                  </div>
                </div>
              </button>
            {/each}
          </div>
        {/if}
      </div>
    {/if}

    <!-- Step 3: Review -->
    {#if step === 3}
      <div>
        <h3 class="mb-1 text-base font-semibold text-text-primary">Review board details</h3>
        <p class="mb-4 text-sm text-text-secondary">
          Auto-populated from ck_boards. Review the hardware revisions and peripheral manifests.
        </p>
        {#if loadingDetail}
          <div class="flex items-center gap-2 py-8 text-sm text-text-tertiary">
            <Loader2 size={16} class="animate-spin" /> Parsing board DTS files...
          </div>
        {:else if boardDetail}
          <div class="space-y-4">
            <!-- SoCs -->
            <div>
              <span class="mb-2 block text-xs font-medium text-text-tertiary">Processors</span>
              <div class="flex flex-wrap gap-2">
                {#each boardDetail.socs as soc}
                  <span class="rounded-full bg-accent/10 px-3 py-1 text-xs font-mono text-accent">
                    {soc}
                  </span>
                {/each}
              </div>
            </div>

            <!-- Variants -->
            <div>
              <span class="mb-2 block text-xs font-medium text-text-tertiary">Variants</span>
              <div class="flex flex-wrap gap-2">
                {#each boardDetail.variants as variant}
                  <span class="rounded border border-border bg-surface-0 px-2.5 py-1 text-xs font-mono text-text-secondary">
                    {variant}
                  </span>
                {/each}
              </div>
            </div>

            <!-- Revisions with peripherals -->
            {#each boardDetail.revisions as rev}
              <div class="rounded-lg border border-border bg-surface-0 p-4">
                <h4 class="mb-3 text-sm font-semibold text-text-primary">{rev.name}</h4>
                {#if rev.peripherals.length === 0}
                  <p class="text-2xs text-text-tertiary">No peripherals detected in DTS.</p>
                {:else}
                  <div class="grid gap-2 sm:grid-cols-2">
                    {#each rev.peripherals as peripheral}
                      <div class="flex items-center gap-2 rounded border border-border-subtle bg-surface-1 px-3 py-2">
                        <Zap size={14} class="shrink-0 text-warning" />
                        <div class="min-w-0 flex-1">
                          <div class="text-2xs font-medium text-text-primary">{peripheral.type}</div>
                          <div class="truncate font-mono text-2xs text-text-tertiary">{peripheral.compatible}</div>
                        </div>
                        <span class="shrink-0 rounded bg-surface-2 px-1.5 py-0.5 text-2xs text-text-tertiary uppercase">
                          {peripheral.bus}
                        </span>
                      </div>
                    {/each}
                  </div>
                {/if}
              </div>
            {/each}
          </div>
        {/if}
      </div>
    {/if}

    <!-- Step 4: Configure -->
    {#if step === 4}
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

          <!-- Repos -->
          <div class="grid gap-3 sm:grid-cols-2">
            <label class="block">
              <span class="mb-1 block text-2xs font-medium text-text-tertiary">FW Repo Slug</span>
              <input
                type="text"
                bind:value={fwRepoSlug}
                class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm font-mono text-text-primary focus:border-accent focus:outline-none"
              />
            </label>
            <label class="block">
              <span class="mb-1 block text-2xs font-medium text-text-tertiary">Mfg Repo Slug</span>
              <input
                type="text"
                bind:value={mfgRepoSlug}
                class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm font-mono text-text-primary focus:border-accent focus:outline-none"
              />
            </label>
          </div>

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
    {#if step === 5}
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
                ['Board', selectedBoardName],
                ['Branch', selectedBranch],
                ['NCS Version', ncsVersion],
                ['FW Repo', fwRepoSlug || '(none)'],
                ['Mfg Repo', mfgRepoSlug || '(none)'],
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

    {#if step < 5}
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
