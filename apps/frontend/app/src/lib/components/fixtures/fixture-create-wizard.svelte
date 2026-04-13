<script lang="ts">
  import { onMount } from 'svelte';
  import { ChevronRight, Check, Loader2, Box, Factory, Cpu, CircuitBoard, Wrench, X, FlaskConical } from 'lucide-svelte';
  import Modal from '$lib/components/ui/modal.svelte';
  import { apiFetch, api } from '$lib/api';
  import type { ApiResponse } from '$lib/types';
  import type { Product, FixtureDesign } from '$lib/types/models';

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

  // Step 4: Fixture Design
  let designs = $state<FixtureDesign[]>([]);
  let selectedDesignId = $state('');
  const selectedDesign = $derived(designs.find(d => d.id === selectedDesignId));

  // Step 5: Name
  let fixtureName = $state('');

  const suggestedName = $derived.by(() => {
    const prod = selectedProduct?.name ?? '';
    const rev = selectedRevision?.version ?? '';
    const type = selectedType === 'MANUFACTURING' ? 'Mfg' : selectedType === 'VALIDATION' ? 'Val' : '';
    return prod && rev && type ? `${prod} ${rev} ${type} Fixture 1` : '';
  });

  const stepLabels = ['Product', 'Type', 'Revision', 'Design', 'Create'];

  const stepIcons = [Box, Factory, CircuitBoard, Wrench, Check];

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
      apiFetch<ApiResponse<any>>(`/v2/fixtures/designs?boardRevisionId=${selectedRevisionId}&type=${selectedType}`).then(res => {
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
    if (!fixtureName) fixtureName = suggestedName;
    step = 5;
  }

  function goToStep(s: number) {
    if (s < step) step = s;
  }

  async function handleCreate() {
    if (!fixtureName.trim() || !selectedDesignId) return;
    submitting = true;
    error = null;
    try {
      await api.post('/v2/fixtures', {
        name: fixtureName.trim(),
        productId: selectedProductId,
        designId: selectedDesignId,
        type: selectedType,
      });
      onCreated();
      resetAndClose();
    } catch (e: any) {
      error = e?.data?.errors?.[0]?.message || (e instanceof Error ? e.message : 'Failed to create fixture');
    } finally {
      submitting = false;
    }
  }

  function resetAndClose() {
    step = 1;
    selectedProductId = '';
    selectedType = '';
    selectedRevisionId = '';
    selectedDesignId = '';
    fixtureName = '';
    error = null;
    onClose();
  }
</script>

<Modal {open} onclose={resetAndClose} size="full" title="" noPadding showCloseButton={false}>
  <div class="flex flex-col h-[90vh]">
    <!-- Header -->
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

      <!-- Context badges -->
      <div class="flex items-center gap-2">
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

    <!-- Step indicator -->
    <div class="flex items-center gap-2 px-6 py-2.5 border-b border-border-subtle bg-surface-0/50 shrink-0">
      {#each stepLabels as label, i}
        {@const stepNum = i + 1}
        {@const isComplete = step > stepNum}
        {@const isCurrent = step === stepNum}
        {@const Icon = stepIcons[i]}
        <button
          onclick={() => goToStep(stepNum)}
          disabled={stepNum > step}
          class="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-2xs font-medium transition-colors
            {isCurrent ? 'bg-accent text-white' :
             isComplete ? 'bg-accent/10 text-accent hover:bg-accent/20' :
             'text-text-tertiary'}"
        >
          {#if isComplete}
            <Check size={12} strokeWidth={3} />
          {:else}
            <Icon size={12} />
          {/if}
          {label}
        </button>
        {#if i < stepLabels.length - 1}
          <ChevronRight size={12} class="text-text-tertiary" />
        {/if}
      {/each}
    </div>

    <!-- Content -->
    <div class="flex-1 overflow-y-auto p-6">
      <!-- Step 1: Product -->
      {#if step === 1}
        <div class="max-w-2xl mx-auto">
          <h3 class="text-lg font-semibold text-text-primary mb-1">Select Product</h3>
          <p class="text-sm text-text-secondary mb-6">Which product will this fixture test?</p>
          <div class="space-y-2">
            {#each products.filter(p => p.status === 'ACTIVE') as product}
              <button
                onclick={() => selectProduct(product.id)}
                class="w-full flex items-center gap-4 rounded-xl border-2 px-5 py-4 text-left transition-all
                  {selectedProductId === product.id
                    ? 'border-accent bg-accent-muted shadow-sm'
                    : 'border-border hover:border-accent/50 hover:shadow-sm'}"
              >
                <div class="flex h-12 w-12 items-center justify-center rounded-xl bg-surface-2 text-text-tertiary shrink-0">
                  <Box size={24} />
                </div>
                <div class="flex-1 min-w-0">
                  <span class="text-base font-semibold text-text-primary">{product.name}</span>
                  {#if product.slug}
                    <p class="text-sm text-text-tertiary">{product.slug}</p>
                  {/if}
                </div>
                <ChevronRight size={18} class="text-text-tertiary shrink-0" />
              </button>
            {/each}
            {#if products.filter(p => p.status === 'ACTIVE').length === 0}
              <p class="text-sm text-text-tertiary text-center py-8">No active products found.</p>
            {/if}
          </div>
        </div>

      <!-- Step 2: Type -->
      {:else if step === 2}
        <div class="max-w-2xl mx-auto">
          <h3 class="text-lg font-semibold text-text-primary mb-1">Fixture Type</h3>
          <p class="text-sm text-text-secondary mb-6">What kind of testing will this fixture do?</p>
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {#each [
              { value: 'MANUFACTURING', label: 'Manufacturing', desc: 'Production flashing, electrical testing, and POST.', icon: Factory },
              { value: 'VALIDATION', label: 'Validation', desc: 'Firmware validation, regression testing, and FUOTA.', icon: FlaskConical },
            ] as opt}
              <button
                onclick={() => selectType(opt.value as any)}
                class="flex flex-col items-center gap-3 rounded-xl border-2 px-6 py-8 text-center transition-all
                  {selectedType === opt.value
                    ? 'border-accent bg-accent-muted shadow-sm'
                    : 'border-border hover:border-accent/50 hover:shadow-sm'}"
              >
                <div class="flex h-14 w-14 items-center justify-center rounded-2xl
                  {selectedType === opt.value ? 'bg-accent text-white' : 'bg-surface-2 text-text-tertiary'}">
                  <opt.icon size={28} />
                </div>
                <div>
                  <span class="text-base font-semibold text-text-primary">{opt.label}</span>
                  <p class="text-sm text-text-tertiary mt-1">{opt.desc}</p>
                </div>
              </button>
            {/each}
          </div>
        </div>

      <!-- Step 3: Hardware Revision -->
      {:else if step === 3}
        <div class="max-w-2xl mx-auto">
          <h3 class="text-lg font-semibold text-text-primary mb-1">Hardware Revision</h3>
          <p class="text-sm text-text-secondary mb-6">Which PCB revision will this fixture test?</p>
          {#if revisions.length === 0}
            <p class="text-sm text-text-tertiary text-center py-8">No board revisions found. Add revisions in the product's Hardware tab.</p>
          {:else}
            <div class="space-y-2">
              {#each revisions as rev}
                <button
                  onclick={() => selectRevision(rev.id)}
                  class="w-full flex items-center gap-4 rounded-xl border-2 px-5 py-4 text-left transition-all
                    {selectedRevisionId === rev.id
                      ? 'border-accent bg-accent-muted shadow-sm'
                      : 'border-border hover:border-accent/50 hover:shadow-sm'}"
                >
                  <div class="flex h-12 w-12 items-center justify-center rounded-xl bg-surface-2 text-lg font-bold text-text-tertiary shrink-0">
                    {rev.version}
                  </div>
                  <div class="flex-1">
                    <span class="text-base font-semibold text-text-primary">{rev.ckBoardsName}</span>
                    <p class="text-sm text-text-tertiary">{rev.version} revision</p>
                  </div>
                  <ChevronRight size={18} class="text-text-tertiary shrink-0" />
                </button>
              {/each}
            </div>
          {/if}
        </div>

      <!-- Step 4: Fixture Design -->
      {:else if step === 4}
        <div class="max-w-2xl mx-auto">
          <h3 class="text-lg font-semibold text-text-primary mb-1">Fixture Design</h3>
          <p class="text-sm text-text-secondary mb-6">Select the hardware design this fixture is built from.</p>
          {#if designs.length === 0}
            <div class="text-center py-8 rounded-xl border-2 border-dashed border-border">
              <Wrench size={32} class="mx-auto mb-3 text-text-tertiary" />
              <p class="text-sm text-text-secondary">No fixture designs available.</p>
              <p class="text-2xs text-text-tertiary mt-1">Release a test app to publish a fixture design for this revision.</p>
            </div>
          {:else}
            <div class="space-y-2">
              {#each designs as design}
                <button
                  onclick={() => selectDesign(design.id)}
                  class="w-full flex items-center gap-4 rounded-xl border-2 px-5 py-4 text-left transition-all
                    {selectedDesignId === design.id
                      ? 'border-accent bg-accent-muted shadow-sm'
                      : 'border-border hover:border-accent/50 hover:shadow-sm'}"
                >
                  <div class="flex h-12 w-12 items-center justify-center rounded-xl bg-surface-2 text-text-tertiary shrink-0">
                    <Wrench size={24} />
                  </div>
                  <div class="flex-1">
                    <span class="text-base font-semibold text-text-primary">{design.name}</span>
                    <div class="flex items-center gap-2 mt-1">
                      <span class="rounded bg-surface-2 px-2 py-0.5 text-2xs font-medium text-text-secondary">Rev {design.revision}</span>
                      {#if design.capabilities?.length}
                        {#each design.capabilities as cap}
                          <span class="rounded bg-accent-muted px-2 py-0.5 text-2xs font-medium text-accent">{cap}</span>
                        {/each}
                      {/if}
                    </div>
                  </div>
                  <ChevronRight size={18} class="text-text-tertiary shrink-0" />
                </button>
              {/each}
            </div>
          {/if}
        </div>

      <!-- Step 5: Name & Create -->
      {:else if step === 5}
        <div class="max-w-2xl mx-auto">
          <h3 class="text-lg font-semibold text-text-primary mb-1">Name Your Fixture</h3>
          <p class="text-sm text-text-secondary mb-6">Give this fixture instance a descriptive name.</p>

          <!-- Summary card -->
          <div class="rounded-xl border border-border bg-surface-0 p-5 mb-6">
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
              {#if selectedDesign?.capabilities?.length}
                <div class="text-text-tertiary">Capabilities</div>
                <div class="flex gap-1.5 flex-wrap">
                  {#each selectedDesign.capabilities as cap}
                    <span class="rounded bg-accent-muted px-2 py-0.5 text-2xs font-medium text-accent">{cap}</span>
                  {/each}
                </div>
              {/if}
            </div>
          </div>

          <!-- Name input -->
          <div>
            <label for="fixture-name" class="block text-sm font-medium text-text-secondary mb-2">Fixture Name</label>
            <input
              id="fixture-name"
              type="text"
              bind:value={fixtureName}
              placeholder="e.g., Alpha B0 Mfg Fixture 1"
              class="input input-md w-full"
            />
            <p class="text-2xs text-text-tertiary mt-1.5">This name must be unique across all fixtures.</p>
          </div>

          {#if error}
            <div class="mt-4 rounded-lg border border-error/30 bg-error-muted px-4 py-3 text-sm text-error">{error}</div>
          {/if}
        </div>
      {/if}
    </div>

    <!-- Footer -->
    <div class="flex items-center justify-between px-6 py-3 border-t border-border shrink-0 bg-surface-0">
      <button onclick={step > 1 ? () => step-- : resetAndClose} class="btn btn-sm btn-ghost">
        {step > 1 ? '← Back' : 'Cancel'}
      </button>
      <div class="flex items-center gap-2">
        <span class="text-2xs text-text-tertiary">Step {step} of {stepLabels.length}</span>
        {#if step === 5}
          <button
            onclick={handleCreate}
            disabled={submitting || !fixtureName.trim()}
            class="btn btn-md btn-primary"
          >
            {#if submitting}<Loader2 size={14} class="animate-spin" />{/if}
            {submitting ? 'Creating...' : 'Create Fixture'}
          </button>
        {/if}
      </div>
    </div>
  </div>
</Modal>
