<script lang="ts">
  import { onMount } from 'svelte';
  import { ChevronRight, ChevronLeft, Check, Loader2, Box, Factory, Cpu, CircuitBoard, Wrench, X, FlaskConical, LayoutGrid, Cable } from 'lucide-svelte';
  import Modal from '$lib/components/ui/modal.svelte';
  import CharCounter from '$lib/components/ui/char-counter.svelte';
  import { apiFetch, api } from '$lib/api';
  import type { ApiResponse } from '$lib/types';
  import type { Product, TestBedDesign } from '$lib/types/models';
  import { toasts } from '$lib/stores/toast.svelte';
  import { makeWizardKeyHandler } from '$lib/utils/wizard-keys';

  const FIXTURE_NAME_MAX = 80;

  interface Props {
    open: boolean;
    onClose: () => void;
    onCreated: () => void;
  }

  let { open, onClose, onCreated }: Props = $props();

  // Wizard state
  let step = $state(1);
  let error = $state<string | null>(null);
  let submitting = $state(false);

  // Step 1: Product
  let products = $state<Product[]>([]);
  let selectedProductId = $state('');
  const selectedProduct = $derived(products.find(p => p.id === selectedProductId));

  // Step 2: Type
  let selectedType = $state<'MANUFACTURING' | 'VALIDATION' | ''>('');

  // Step 3: Hardware Revision
  let revisions = $state<{ id: string; version: string; ckBoardsName: string }[]>([]);
  let selectedRevisionId = $state('');
  const selectedRevision = $derived(revisions.find(r => r.id === selectedRevisionId));

  // Step 4: TestBed Design
  let designs = $state<TestBedDesign[]>([]);
  let selectedDesignId = $state('');
  const selectedDesign = $derived(designs.find(d => d.id === selectedDesignId));

  // Step 5: Panel Layout
  let panelRows = $state(1);
  let panelCols = $state(1);
  let hasStandaloneSlot = $state(false);

  const panelSlotCount = $derived(panelRows * panelCols);
  const totalSlotCount = $derived(panelSlotCount + (hasStandaloneSlot ? 1 : 0));

  // Generate slot grid: panel slots (row-major) + optional standalone slot
  const slotGrid = $derived.by(() => {
    const grid: { index: number; row: number; col: number; label: string; standalone: boolean }[] = [];
    let idx = 1;
    for (let r = 0; r < panelRows; r++) {
      for (let c = 0; c < panelCols; c++) {
        grid.push({ index: idx, row: r, col: c, label: `Slot ${idx}`, standalone: false });
        idx++;
      }
    }
    if (hasStandaloneSlot) {
      grid.push({ index: idx, row: -1, col: -1, label: 'Standalone', standalone: true });
    }
    return grid;
  });

  // Step 6: MTIB Mapping (discovery-based)
  interface AssignableNode {
    id: string | null;
    name: string;
    hostname: string;
    ipAddress: string | null;
    source: 'registered' | 'discovered';
  }

  let assignableNodes = $state<AssignableNode[]>([]);
  let slotMtibMap = $state<Record<number, string>>({}); // slotIndex → nodeId
  let discoverLoading = $state(false);
  let registeringNode = $state<string | null>(null);

  function mtibNameFromHostname(hostname: string): string {
    const digits = hostname.replace(/\D/g, '');
    return `MTIB-${digits.slice(-4)}`;
  }

  async function loadAssignableNodes() {
    discoverLoading = true;
    assignableNodes = [];
    try {
      // 1. Discover K8s edge nodes (finds unregistered arm64 nodes)
      let discovered: AssignableNode[] = [];
      try {
        const discoverRes = await api.post<ApiResponse<any>>('/v2/devices/mtibs/discover', {});
        const discoverData = discoverRes.data;
        for (const n of (discoverData.discovered ?? [])) {
          discovered.push({ id: null, name: mtibNameFromHostname(n.hostname), hostname: n.hostname, ipAddress: n.ip ?? null, source: 'discovered' });
        }
      } catch { /* K8s not available in dev — fall through to registered */ }

      // 2. Fetch registered nodes — only unassigned ones are available
      let registered: AssignableNode[] = [];
      try {
        const listRes = await apiFetch<ApiResponse<any>>(`/v2/devices/mtibs?type=${selectedType}&limit=100`);
        const payload = listRes.data;
        const nodes = Array.isArray(payload) ? payload : (payload as any)?.data ?? [];
        for (const n of nodes) {
          if (n.fixtureSlot) continue; // already assigned — not available
          registered.push({ id: n.id, name: n.name, hostname: n.hostname, ipAddress: n.ipAddress ?? null, source: 'registered' });
        }
      } catch { /* ignore */ }

      // 3. Merge — discovered nodes that were just registered won't appear in both
      //    because discover only returns nodes NOT in DB
      assignableNodes = [...registered, ...discovered];
    } finally {
      discoverLoading = false;
    }
  }

  $effect(() => {
    if (step === 6 && selectedType) {
      slotMtibMap = {};
      loadAssignableNodes();
    }
  });

  async function autoRegisterNode(hostname: string): Promise<string | null> {
    registeringNode = hostname;
    try {
      const res = await api.post<ApiResponse<any>>('/v2/devices/mtibs', { name: mtibNameFromHostname(hostname), hostname, type: selectedType });
      const created = res.data;
      assignableNodes = assignableNodes.map(n =>
        n.hostname === hostname ? { ...n, id: created.id, name: created.name, source: 'registered' as const } : n
      );
      return created.id;
    } catch {
      return null;
    } finally {
      registeringNode = null;
    }
  }

  async function handleSlotNodeSelect(slotIndex: number, value: string) {
    if (!value) {
      const copy = { ...slotMtibMap };
      delete copy[slotIndex];
      slotMtibMap = copy;
      return;
    }
    const node = assignableNodes.find(n => (n.id ?? n.hostname) === value);
    if (!node) return;

    if (node.source === 'discovered' && !node.id) {
      const newId = await autoRegisterNode(node.hostname);
      if (newId) slotMtibMap = { ...slotMtibMap, [slotIndex]: newId };
    } else if (node.id) {
      slotMtibMap = { ...slotMtibMap, [slotIndex]: node.id };
    }
  }

  // Step 7: Name
  let fixtureName = $state('');

  const suggestedName = $derived.by(() => {
    const prod = selectedProduct?.name ?? '';
    const rev = selectedRevision?.version ?? '';
    const type = selectedType === 'MANUFACTURING' ? 'Mfg' : selectedType === 'VALIDATION' ? 'Val' : '';
    return prod && rev && type ? `${prod} ${rev} ${type} Fixture 1` : '';
  });

  const totalSteps = 7;

  const stepLabels = ['Product', 'Type', 'Revision', 'Design', 'Panel', 'MTIBs', 'Name'];

  const stepIcons = [Box, Factory, CircuitBoard, Wrench, LayoutGrid, Cable, Check];

  // Load products on open
  $effect(() => {
    if (open && products.length === 0) {
      apiFetch<ApiResponse<any>>('/v2/products').then(res => {
        const payload = res.data;
        products = Array.isArray(payload) ? payload : (payload as any)?.data ?? [];
      }).catch(() => { products = []; });
    }
  });

  // Load revisions when product changes
  $effect(() => {
    if (selectedProductId) {
      apiFetch<ApiResponse<Product>>(`/v2/products/${selectedProductId}`).then(res => {
        const boards = res.data.boards ?? [];
        revisions = boards.flatMap((b: any) =>
          (b.revisions ?? []).map((r: any) => ({
            id: r.id,
            version: r.version,
            ckBoardsName: r.ckBoardsName ?? `${b.name} ${r.version}`,
          }))
        );
      }).catch(() => { revisions = []; });
    } else {
      revisions = [];
      selectedRevisionId = '';
    }
  });

  // Load designs when revision + type change
  $effect(() => {
    if (selectedRevisionId && selectedType) {
      apiFetch<ApiResponse<any>>(`/v2/test-bed-designs?boardRevisionId=${selectedRevisionId}&type=${selectedType}`).then(res => {
        const payload = res.data;
        designs = Array.isArray(payload) ? payload : (payload as any)?.data ?? [];
      }).catch(() => { designs = []; });
    } else {
      designs = [];
      selectedDesignId = '';
    }
  });

  function selectProduct(id: string) {
    selectedProductId = id;
    selectedType = '';
    selectedRevisionId = '';
    selectedDesignId = '';
    step = 2;
  }

  function selectType(type: 'MANUFACTURING' | 'VALIDATION') {
    selectedType = type;
    selectedRevisionId = '';
    selectedDesignId = '';
    step = 3;
  }

  function selectRevision(id: string) {
    selectedRevisionId = id;
    selectedDesignId = '';
    step = 4;
  }

  function selectDesign(id: string) {
    selectedDesignId = id;
    step = 5;
  }

  function goToStep(s: number) {
    if (s < step) step = s;
  }

  // Auto-suggest name when entering the Name step
  $effect(() => {
    if (step === 7 && !fixtureName) {
      fixtureName = suggestedName;
    }
  });

  let createProgress = $state('');

  async function handleCreate() {
    if (!fixtureName.trim() || !selectedDesignId) return;
    submitting = true;
    error = null;
    createProgress = 'Creating fixture...';

    try {
      const slots = slotGrid.map(slot => ({
        slotIndex: slot.index - 1, // 0-based in DB
        label: slot.label,
      }));

      const res = await api.post<ApiResponse<any>>('/v2/fixtures', {
        name: fixtureName.trim(),
        productId: selectedProductId,
        designId: selectedDesignId,
        type: selectedType,
        panelRows,
        panelCols,
        slots,
        metadata: hasStandaloneSlot ? { hasStandaloneSlot: true } : undefined,
      });

      const fixture = res.data;
      const fixtureId = fixture.id;
      const createdSlots: { id: string; slotIndex: number }[] = fixture.slots ?? [];

      // Assign MTIB nodes to slots
      const mappedEntries = Object.entries(slotMtibMap);
      if (mappedEntries.length > 0 && createdSlots.length > 0) {
        let assigned = 0;
        const total = mappedEntries.length;

        for (const [wizardIdx, nodeId] of mappedEntries) {
          const dbSlotIndex = Number(wizardIdx) - 1; // wizard uses 1-based, DB uses 0-based
          const slot = createdSlots.find(s => s.slotIndex === dbSlotIndex);
          if (!slot) continue;

          assigned++;
          createProgress = `Assigning MTIB ${assigned} of ${total}...`;

          try {
            await api.post(`/v2/fixtures/${fixtureId}/slots/${slot.id}/assign`, { nodeId });
          } catch (e: any) {
            const msg = e?.data?.errors?.[0]?.message || 'Assignment failed';
            console.warn(`Slot ${dbSlotIndex} assignment failed: ${msg}`);
          }
        }
      }

      createProgress = '';
      toasts.success(`Fixture "${fixtureName.trim()}" created`);
      onCreated();
      resetAndClose();
    } catch (e: any) {
      error = e?.data?.errors?.[0]?.message || (e instanceof Error ? e.message : 'Failed to create fixture');
      toasts.error(error || 'Failed to create fixture');
      createProgress = '';
    } finally {
      submitting = false;
    }
  }

  // Enter advances steps where possible; on the final step it submits.
  // Escape cancels (resets and closes).
  function handleEnterKey() {
    if (!open) return;
    if (step < totalSteps) {
      const canAdvance =
        (step === 1 && !!selectedProductId) ||
        (step === 2 && !!selectedType) ||
        (step === 3 && !!selectedRevisionId) ||
        (step === 4 && !!selectedDesignId) ||
        step === 5 ||
        step === 6;
      if (canAdvance) step++;
      return;
    }
    if (!submitting && fixtureName.trim()) handleCreate();
  }

  const handleWizardKey = makeWizardKeyHandler(() => ({
    onEnter: handleEnterKey,
    onEscape: () => { if (!submitting) resetAndClose(); },
    disabled: !open,
  }));

  function resetAndClose() {
    step = 1;
    selectedProductId = '';
    selectedType = '';
    selectedRevisionId = '';
    selectedDesignId = '';
    fixtureName = '';
    error = null;
    createProgress = '';
    slotMtibMap = {};
    assignableNodes = [];
    panelRows = 1;
    panelCols = 1;
    hasStandaloneSlot = false;
    onClose();
  }
</script>

<svelte:window onkeydown={handleWizardKey} />

<Modal {open} onclose={resetAndClose} size="full" title="" noPadding showCloseButton={false} closeOnEscape={false}>
  <div class="flex flex-col h-[90vh]">
    <!-- Header (compact) -->
    <div class="flex items-center gap-3 px-6 py-3 border-b border-border shrink-0">
      <div class="flex items-center justify-center w-9 h-9 rounded-lg bg-accent/10">
        <Wrench size={18} class="text-accent" />
      </div>
      <div class="flex-1 min-w-0">
        <h2 class="text-sm font-semibold text-text-primary">Create Fixture</h2>
        <p class="text-2xs text-text-tertiary truncate">
          {#if selectedProduct}
            {selectedProduct.name}
            {#if selectedType} · {selectedType}{/if}
            {#if selectedRevision} · {selectedRevision.version}{/if}
          {:else}
            Set up a new test fixture instance
          {/if}
        </p>
      </div>

      <div class="flex items-center gap-3">
        {#if selectedRevision}
          <div class="flex items-center gap-2 rounded-lg border border-accent/30 bg-accent-muted px-3 py-2">
            <CircuitBoard size={14} class="text-accent" />
            <span class="text-sm font-semibold text-text-primary">{selectedRevision.version}</span>
            <span class="font-mono text-2xs text-text-tertiary">{selectedRevision.ckBoardsName}</span>
          </div>
        {/if}
      </div>

      <button onclick={resetAndClose} class="rounded-lg p-2 text-text-tertiary hover:bg-surface-2 hover:text-text-primary transition-colors">
        <X size={18} />
      </button>
    </div>

    <!-- Step indicator (compact) -->
    <div class="flex items-center gap-2 px-6 py-2.5 border-b border-border-subtle bg-surface-0/50 shrink-0">
      {#each stepLabels as label, i}
        {@const stepNum = i + 1}
        {@const isComplete = step > stepNum}
        {@const isCurrent = step === stepNum}
        <button
          onclick={() => { if (isComplete || isCurrent) goToStep(stepNum); }}
          disabled={stepNum > step}
          class="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors
            {isCurrent ? 'bg-accent text-white shadow-sm' :
             isComplete ? 'bg-success-muted text-success' :
             'bg-surface-2 text-text-tertiary hover:text-text-secondary'}"
        >
          {#if isComplete}
            <Check size={14} />
          {:else}
            <span class="w-5 h-5 flex items-center justify-center rounded-full text-xs border
              {isCurrent ? 'border-white/50' : 'border-text-tertiary/30'}">{stepNum}</span>
          {/if}
          {label}
        </button>
        {#if i < stepLabels.length - 1}
          <div class="h-px flex-1 bg-border-subtle max-w-8"></div>
        {/if}
      {/each}
    </div>

    <!-- Content area -->
    <div class="flex-1 overflow-y-auto px-6 py-4">
      <!-- Step 1: Product -->
      {#if step === 1}
        <div class="max-w-3xl space-y-4">
          <p class="text-sm text-text-secondary">Which product will this fixture test?</p>
          <div class="grid gap-3">
            {#each products.filter(p => p.status === 'ACTIVE') as product}
              <button
                onclick={() => selectProduct(product.id)}
                class="card card-md text-left transition-all
                  {selectedProductId === product.id
                    ? 'border-accent bg-accent-muted'
                    : 'hover:border-text-tertiary'}"
              >
                <div class="flex items-center gap-4">
                  <div class="flex h-10 w-10 items-center justify-center rounded-lg bg-surface-2 text-text-tertiary shrink-0">
                    <Box size={20} />
                  </div>
                  <div class="flex-1 min-w-0">
                    <span class="text-sm font-semibold text-text-primary">{product.name}</span>
                    {#if product.slug}
                      <p class="text-2xs text-text-tertiary">{product.slug}</p>
                    {/if}
                  </div>
                  <ChevronRight size={16} class="text-text-tertiary shrink-0" />
                </div>
              </button>
            {/each}
            {#if products.filter(p => p.status === 'ACTIVE').length === 0}
              <p class="text-sm text-text-tertiary text-center py-8">No active products found.</p>
            {/if}
          </div>
        </div>

      <!-- Step 2: Type -->
      {:else if step === 2}
        <div class="max-w-3xl space-y-4">
          <p class="text-sm text-text-secondary">What kind of testing will this fixture do?</p>
          <div class="grid gap-3 sm:grid-cols-2">
            {#each [
              { value: 'MANUFACTURING', label: 'Manufacturing', desc: 'Production flashing, electrical testing, and POST.', icon: Factory },
              { value: 'VALIDATION', label: 'Validation', desc: 'Firmware validation, regression testing, and FUOTA.', icon: FlaskConical },
            ] as opt}
              <button
                onclick={() => selectType(opt.value as any)}
                class="card card-md text-left transition-all
                  {selectedType === opt.value
                    ? 'border-accent bg-accent-muted'
                    : 'hover:border-text-tertiary'}"
              >
                <div class="flex items-center gap-2 mb-2">
                  <opt.icon size={18} class={selectedType === opt.value ? 'text-accent' : 'text-text-tertiary'} />
                  <span class="text-sm font-semibold text-text-primary">{opt.label}</span>
                </div>
                <p class="text-2xs text-text-secondary">{opt.desc}</p>
              </button>
            {/each}
          </div>
        </div>

      <!-- Step 3: Hardware Revision -->
      {:else if step === 3}
        <div class="max-w-3xl space-y-4">
          <p class="text-sm text-text-secondary">Which PCB revision will this fixture test?</p>
          {#if revisions.length === 0}
            <p class="text-sm text-text-tertiary text-center py-8">No board revisions found. Add revisions in the product's Hardware tab.</p>
          {:else}
            <div class="grid gap-3">
              {#each revisions as rev}
                <button
                  onclick={() => selectRevision(rev.id)}
                  class="card card-md text-left transition-all
                    {selectedRevisionId === rev.id
                      ? 'border-accent bg-accent-muted'
                      : 'hover:border-text-tertiary'}"
                >
                  <div class="flex items-center gap-4">
                    <div class="flex h-10 w-10 items-center justify-center rounded-lg bg-surface-2 text-sm font-bold text-text-tertiary shrink-0">
                      {rev.version}
                    </div>
                    <div class="flex-1">
                      <span class="text-sm font-semibold text-text-primary">{rev.ckBoardsName}</span>
                      <p class="text-2xs text-text-tertiary">{rev.version} revision</p>
                    </div>
                    <ChevronRight size={16} class="text-text-tertiary shrink-0" />
                  </div>
                </button>
              {/each}
            </div>
          {/if}
        </div>

      <!-- Step 4: TestBed Design -->
      {:else if step === 4}
        <div class="max-w-3xl space-y-4">
          <p class="text-sm text-text-secondary">Select the hardware design this fixture is built from.</p>
          {#if designs.length === 0}
            <div class="card card-md text-center py-8 border-dashed">
              <Wrench size={28} class="mx-auto mb-3 text-text-tertiary" />
              <p class="text-sm text-text-secondary">No TestBed designs available.</p>
              <p class="text-2xs text-text-tertiary mt-1">Release a test app to publish a TestBed design for this revision.</p>
            </div>
          {:else}
            <div class="grid gap-3">
              {#each designs as design}
                <button
                  onclick={() => selectDesign(design.id)}
                  class="card card-md text-left transition-all
                    {selectedDesignId === design.id
                      ? 'border-accent bg-accent-muted'
                      : 'hover:border-text-tertiary'}"
                >
                  <div class="flex items-center gap-4">
                    <div class="flex h-10 w-10 items-center justify-center rounded-lg bg-surface-2 text-text-tertiary shrink-0">
                      <Wrench size={20} />
                    </div>
                    <div class="flex-1">
                      <span class="text-sm font-semibold text-text-primary">{design.name}</span>
                      <div class="flex items-center gap-2 mt-1">
                        <span class="rounded bg-surface-2 px-2 py-0.5 text-2xs font-medium text-text-secondary">Rev {design.revision}</span>
                      </div>
                    </div>
                    <ChevronRight size={16} class="text-text-tertiary shrink-0" />
                  </div>
                </button>
              {/each}
            </div>
          {/if}
        </div>

      <!-- Step 5: Panel Layout -->
      {:else if step === 5}
        <div class="max-w-3xl space-y-4">
          <p class="text-sm text-text-secondary">Define the PCB panel layout. This is a <strong>top-down view</strong> — slot 1 is top-left.</p>

          <!-- Row/Col selectors -->
          <div class="card card-md space-y-4">
            <h4 class="text-2xs font-semibold text-text-tertiary uppercase tracking-wider">Panel Grid</h4>
            <div class="flex items-center gap-6">
              <label class="flex items-center gap-2">
                <span class="text-sm font-medium text-text-secondary">Rows</span>
                <select bind:value={panelRows} class="input input-sm w-20">
                  {#each Array.from({length: 10}, (_, i) => i + 1) as n}
                    <option value={n}>{n}</option>
                  {/each}
                </select>
              </label>
              <span class="text-text-tertiary">×</span>
              <label class="flex items-center gap-2">
                <span class="text-sm font-medium text-text-secondary">Columns</span>
                <select bind:value={panelCols} class="input input-sm w-20">
                  {#each Array.from({length: 10}, (_, i) => i + 1) as n}
                    <option value={n}>{n}</option>
                  {/each}
                </select>
              </label>
              <span class="text-sm text-text-tertiary">= {panelSlotCount} panel slot{panelSlotCount !== 1 ? 's' : ''}</span>
            </div>

            <!-- Standalone slot toggle -->
            <label class="flex items-center gap-3 cursor-pointer">
              <input type="checkbox" bind:checked={hasStandaloneSlot} class="h-4 w-4 rounded border-border text-accent focus:ring-accent" />
              <div>
                <span class="text-sm font-medium text-text-primary">Include standalone slot</span>
                <p class="text-2xs text-text-tertiary">An additional single-board slot outside the panel grid, for standalone DUT testing.</p>
              </div>
            </label>
          </div>

          <!-- Panel grid preview -->
          <div class="card card-md">
            <div class="flex items-center gap-2 mb-3">
              <LayoutGrid size={14} class="text-text-tertiary" />
              <span class="text-2xs font-semibold text-text-tertiary uppercase tracking-wider">Top-Down View</span>
              <span class="text-2xs text-text-tertiary ml-auto">{totalSlotCount} total slot{totalSlotCount !== 1 ? 's' : ''}</span>
            </div>

            <!-- Panel grid -->
            <div
              class="grid gap-2 mx-auto"
              style="grid-template-columns: repeat({panelCols}, minmax(0, 1fr)); max-width: {Math.min(panelCols * 100, 600)}px;"
            >
              {#each slotGrid.filter(s => !s.standalone) as slot}
                <div class="flex flex-col items-center justify-center rounded-lg border-2 border-accent/30 bg-accent-muted/30 aspect-square min-h-16 transition-all">
                  <span class="text-lg font-bold text-accent">{slot.index}</span>
                  <span class="text-2xs text-text-tertiary">{slot.label}</span>
                </div>
              {/each}
            </div>

            <!-- Standalone slot (below the grid) -->
            {#if hasStandaloneSlot}
              {@const standaloneSlot = slotGrid.find(s => s.standalone)}
              {#if standaloneSlot}
                <div class="mt-4 pt-4 border-t border-border-subtle">
                  <div class="flex items-center gap-3">
                    <div class="flex flex-col items-center justify-center rounded-lg border-2 border-warning/30 bg-warning-muted/30 w-20 h-20">
                      <span class="text-lg font-bold text-warning">{standaloneSlot.index}</span>
                      <span class="text-2xs text-text-tertiary">Standalone</span>
                    </div>
                    <div>
                      <p class="text-sm font-medium text-text-primary">Standalone Slot</p>
                      <p class="text-2xs text-text-tertiary">Single-board position, separate from the panel grid.</p>
                    </div>
                  </div>
                </div>
              {/if}
            {/if}

            <p class="text-2xs text-text-tertiary mt-3 text-center">
              Panel: left→right, top→bottom.{hasStandaloneSlot ? ' Standalone slot is independent.' : ''}
            </p>
          </div>
        </div>

      <!-- Step 6: MTIB Mapping -->
      {:else if step === 6}
        <div class="max-w-3xl space-y-4">
          <div class="flex items-center justify-between">
            <p class="text-sm text-text-secondary">Assign an MTIB controller to each slot. Discovered nodes are auto-registered on selection.</p>
            <button onclick={loadAssignableNodes} disabled={discoverLoading} class="btn btn-sm btn-ghost">
              {#if discoverLoading}<Loader2 size={14} class="animate-spin" />{/if}
              Refresh
            </button>
          </div>

          {#if discoverLoading && assignableNodes.length === 0}
            <div class="card card-md flex items-center justify-center py-12">
              <Loader2 size={20} class="animate-spin text-text-tertiary mr-2" />
              <span class="text-sm text-text-tertiary">Discovering MTIB nodes...</span>
            </div>
          {:else}
            <div class="card card-md">
              <div class="flex items-center gap-2 mb-3">
                <Cable size={14} class="text-text-tertiary" />
                <span class="text-2xs font-semibold text-text-tertiary uppercase tracking-wider">Top-Down View</span>
                <span class="text-2xs text-text-tertiary ml-auto">{Object.keys(slotMtibMap).length}/{totalSlotCount} assigned</span>
              </div>

              <!-- Panel grid slots -->
              <div
                class="grid gap-3 mx-auto"
                style="grid-template-columns: repeat({panelCols}, minmax(0, 1fr)); max-width: {Math.min(panelCols * 200, 800)}px;"
              >
                {#each slotGrid.filter(s => !s.standalone) as slot}
                  {@const assignedNodeId = slotMtibMap[slot.index] ?? ''}
                  {@const assignedNode = assignableNodes.find(n => n.id === assignedNodeId)}
                  {@const isRegistering = registeringNode !== null}
                  <div class="rounded-lg border-2 {assignedNodeId ? 'border-success/40 bg-success-muted/20' : 'border-border bg-surface-0'} p-3 transition-all">
                    <div class="flex items-center justify-between mb-2">
                      <span class="text-sm font-bold text-text-primary">{slot.label}</span>
                      {#if assignedNodeId}
                        <span class="badge badge-success">Assigned</span>
                      {:else}
                        <span class="badge badge-neutral">Empty</span>
                      {/if}
                    </div>
                    <select
                      value={assignedNodeId}
                      onchange={(e) => handleSlotNodeSelect(slot.index, (e.target as HTMLSelectElement).value)}
                      disabled={isRegistering}
                      class="input input-sm w-full"
                    >
                      <option value="">Select MTIB...</option>
                      {#each assignableNodes as node}
                        {@const nodeKey = node.id ?? node.hostname}
                        {@const usedByOther = Object.entries(slotMtibMap).some(([idx, nid]) => nid === nodeKey && Number(idx) !== slot.index)}
                        <option value={nodeKey} disabled={usedByOther}>
                          {node.name}{node.source === 'discovered' ? ' (new)' : ''}{usedByOther ? ' (in use)' : ''}
                        </option>
                      {/each}
                    </select>
                    {#if assignedNode}
                      <p class="text-2xs text-text-tertiary mt-1 truncate">{assignedNode.hostname}</p>
                    {/if}
                  </div>
                {/each}
              </div>

              <!-- Standalone slot -->
              {#if hasStandaloneSlot}
                {@const standaloneSlot = slotGrid.find(s => s.standalone)}
                {#if standaloneSlot}
                  {@const assignedNodeId = slotMtibMap[standaloneSlot.index] ?? ''}
                  {@const assignedNode = assignableNodes.find(n => n.id === assignedNodeId)}
                  <div class="mt-4 pt-4 border-t border-border-subtle">
                    <div class="rounded-lg border-2 {assignedNodeId ? 'border-success/40 bg-success-muted/20' : 'border-warning/30 bg-warning-muted/10'} p-3 max-w-xs">
                      <div class="flex items-center justify-between mb-2">
                        <span class="text-sm font-bold text-warning">Standalone</span>
                        {#if assignedNodeId}
                          <span class="badge badge-success">Assigned</span>
                        {:else}
                          <span class="badge badge-neutral">Empty</span>
                        {/if}
                      </div>
                      <select
                        value={assignedNodeId}
                        onchange={(e) => handleSlotNodeSelect(standaloneSlot.index, (e.target as HTMLSelectElement).value)}
                        disabled={registeringNode !== null}
                        class="input input-sm w-full"
                      >
                        <option value="">Select MTIB...</option>
                        {#each assignableNodes as node}
                          {@const nodeKey = node.id ?? node.hostname}
                          {@const usedByOther = Object.entries(slotMtibMap).some(([idx, nid]) => nid === nodeKey && Number(idx) !== standaloneSlot.index)}
                          <option value={nodeKey} disabled={usedByOther}>
                            {node.name}{node.source === 'discovered' ? ' (new)' : ''}{usedByOther ? ' (in use)' : ''}
                          </option>
                        {/each}
                      </select>
                      {#if assignedNode}
                        <p class="text-2xs text-text-tertiary mt-1 truncate">{assignedNode.hostname}</p>
                      {/if}
                    </div>
                  </div>
                {/if}
              {/if}

              {#if assignableNodes.length === 0 && !discoverLoading}
                <div class="mt-4 rounded-lg border border-warning/30 bg-warning-muted px-4 py-3 text-sm text-warning text-center">
                  No available MTIB nodes. Ensure edge nodes are powered and connected to the cluster.
                </div>
              {/if}

              <p class="text-2xs text-text-tertiary mt-3 text-center">
                1 MTIB = 1 DUT position. Nodes marked <em>(new)</em> are auto-registered when selected.
              </p>
            </div>
          {/if}
        </div>

      <!-- Step 7: Name & Create -->
      {:else if step === 7}
        <div class="max-w-3xl space-y-4">
          <p class="text-sm text-text-secondary">Give this fixture instance a descriptive name.</p>

          <!-- Summary card -->
          <div class="card card-md">
            <h4 class="text-2xs font-semibold text-text-tertiary uppercase tracking-wider mb-3">Configuration Summary</h4>
            <div class="grid grid-cols-2 gap-y-2 gap-x-8 text-sm">
              <div class="text-text-tertiary">Product</div>
              <div class="text-text-primary font-medium">{selectedProduct?.name}</div>
              <div class="text-text-tertiary">Type</div>
              <div class="text-text-primary font-medium">{selectedType === 'MANUFACTURING' ? 'Manufacturing' : 'Validation'}</div>
              <div class="text-text-tertiary">Revision</div>
              <div class="text-text-primary font-medium">{selectedRevision?.version} ({selectedRevision?.ckBoardsName})</div>
              <div class="text-text-tertiary">Design</div>
              <div class="text-text-primary font-medium">{selectedDesign?.name} <span class="text-text-tertiary font-normal">v{selectedDesign?.revision}</span></div>
            </div>
          </div>

          <!-- Name input -->
          <div>
            <label for="fixture-name" class="block text-sm font-medium text-text-secondary mb-2">Fixture Name</label>
            <input
              id="fixture-name"
              type="text"
              bind:value={fixtureName}
              maxlength={FIXTURE_NAME_MAX}
              placeholder="e.g., Alpha B0 Mfg Fixture 1"
              class="input input-md w-full"
            />
            <div class="mt-1.5 flex items-baseline justify-between gap-2">
              <p class="text-2xs text-text-tertiary">This name must be unique across all fixtures.</p>
              <CharCounter value={fixtureName} max={FIXTURE_NAME_MAX} />
            </div>
          </div>

          {#if error}
            <div class="mt-4 rounded-lg border border-error/30 bg-error-muted px-4 py-3 text-sm text-error">{error}</div>
          {/if}
        </div>
      {/if}
    </div>

    <!-- Footer (compact) -->
    <div class="flex items-center justify-between px-6 py-3 border-t border-border bg-surface-0/50 shrink-0">
      <button
        onclick={step === 1 ? resetAndClose : () => step--}
        class="flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium text-text-secondary hover:bg-surface-2 transition-colors"
      >
        <ChevronLeft size={16} />
        {step === 1 ? 'Cancel' : 'Back'}
      </button>

      <div class="flex items-center gap-3">
        {#if step < totalSteps}
          <button
            onclick={() => step++}
            disabled={(step === 1 && !selectedProductId) ||
                     (step === 2 && !selectedType) ||
                     (step === 3 && !selectedRevisionId) ||
                     (step === 4 && !selectedDesignId)}
            class="flex items-center gap-2 rounded-lg bg-accent px-6 py-2.5 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            Next <ChevronRight size={16} />
          </button>
        {:else}
          <button
            onclick={handleCreate}
            disabled={submitting || !fixtureName.trim()}
            class="flex items-center gap-2 rounded-lg bg-accent px-6 py-2.5 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50 transition-colors"
          >
            {#if submitting}
              <Loader2 size={16} class="animate-spin" /> {createProgress || 'Creating...'}
            {:else}
              <Check size={16} /> Create Fixture
            {/if}
          </button>
        {/if}
      </div>
    </div>
  </div>
</Modal>
