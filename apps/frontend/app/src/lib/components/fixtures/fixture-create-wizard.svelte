<script lang="ts">
  import { onMount } from 'svelte';
  import { ChevronRight, Check, Loader2, Box } from 'lucide-svelte';
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
  let selectedType = $state<'MANUFACTURING' | 'VALIDATION'>('MANUFACTURING');

  // Step 3: Hardware Revision
  let revisions = $state<{ id: string; version: string; ckBoardsName: string }[]>([]);
  let selectedRevisionId = $state('');

  // Step 4: Fixture Design
  let designs = $state<FixtureDesign[]>([]);
  let selectedDesignId = $state('');
  const selectedDesign = $derived(designs.find(d => d.id === selectedDesignId));

  // Step 5: Name
  let fixtureName = $state('');

  // Auto-suggest name
  const suggestedName = $derived(() => {
    const prod = selectedProduct?.name ?? '';
    const rev = revisions.find(r => r.id === selectedRevisionId)?.version ?? '';
    const type = selectedType === 'MANUFACTURING' ? 'Mfg' : 'Val';
    return prod && rev ? `${prod} ${rev} ${type} Fixture 1` : '';
  });

  // Load products on mount
  onMount(async () => {
    try {
      const res = await apiFetch<ApiResponse<any>>('/v2/products');
      const payload = res.data;
      products = Array.isArray(payload) ? payload : (payload as any)?.data ?? [];
    } catch { products = []; }
  });

  // Load revisions when product changes
  $effect(() => {
    if (selectedProductId) {
      loadRevisions(selectedProductId);
    } else {
      revisions = [];
      selectedRevisionId = '';
    }
  });

  // Load designs when revision + type change
  $effect(() => {
    if (selectedRevisionId && selectedType) {
      loadDesigns(selectedRevisionId, selectedType);
    } else {
      designs = [];
      selectedDesignId = '';
    }
  });

  async function loadRevisions(pid: string) {
    try {
      const res = await apiFetch<ApiResponse<Product>>(`/v2/products/${pid}`);
      const boards = res.data.boards ?? [];
      revisions = boards.flatMap((b: any) =>
        (b.revisions ?? []).map((r: any) => ({
          id: r.id,
          version: r.version,
          ckBoardsName: r.ckBoardsName ?? `${b.name} ${r.version}`,
        }))
      );
    } catch { revisions = []; }
  }

  async function loadDesigns(revId: string, type: string) {
    try {
      const res = await apiFetch<ApiResponse<any>>(`/v2/fixtures/designs?boardRevisionId=${revId}&type=${type}`);
      const payload = res.data;
      designs = Array.isArray(payload) ? payload : (payload as any)?.data ?? [];
    } catch { designs = []; }
  }

  function nextStep() {
    if (step === 1 && !selectedProductId) return;
    if (step === 2) { /* type always has a value */ }
    if (step === 3 && !selectedRevisionId) return;
    if (step === 4 && !selectedDesignId) return;
    step++;
    if (step === 5 && !fixtureName) {
      fixtureName = suggestedName();
    }
  }

  function prevStep() {
    if (step > 1) step--;
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
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to create fixture';
    } finally {
      submitting = false;
    }
  }

  function resetAndClose() {
    step = 1;
    selectedProductId = '';
    selectedType = 'MANUFACTURING';
    selectedRevisionId = '';
    selectedDesignId = '';
    fixtureName = '';
    error = null;
    onClose();
  }

  const stepLabels = ['Product', 'Type', 'Revision', 'Design', 'Name'];
</script>

<Modal {open} title="Create Fixture" size="md" onclose={resetAndClose}>
  {#snippet children()}
    <!-- Step indicator -->
    <div class="flex items-center gap-1 mb-6">
      {#each stepLabels as label, i}
        {@const active = i + 1 === step}
        {@const done = i + 1 < step}
        <div class="flex items-center gap-1">
          <div class="flex h-5 w-5 items-center justify-center rounded-full text-2xs font-bold
            {done ? 'bg-accent text-white' : active ? 'bg-accent text-white' : 'bg-surface-2 text-text-tertiary'}">
            {#if done}<Check size={10} strokeWidth={3} />{:else}{i + 1}{/if}
          </div>
          <span class="text-2xs {active ? 'text-text-primary font-medium' : 'text-text-tertiary'}">{label}</span>
        </div>
        {#if i < stepLabels.length - 1}
          <div class="flex-1 h-px bg-border-subtle mx-1"></div>
        {/if}
      {/each}
    </div>

    <div class="min-h-[200px]">
      <!-- Step 1: Product -->
      {#if step === 1}
        <p class="text-sm text-text-secondary mb-3">Which product is this fixture for?</p>
        <div class="space-y-1.5">
          {#each products.filter(p => p.status === 'ACTIVE') as product}
            <button
              onclick={() => { selectedProductId = product.id; nextStep(); }}
              class="w-full flex items-center gap-3 rounded-lg border px-4 py-3 text-left transition-colors
                {selectedProductId === product.id
                  ? 'border-accent bg-accent-muted'
                  : 'border-border hover:border-accent/50 hover:bg-surface-0/50'}"
            >
              <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-surface-2 text-text-tertiary">
                <Box size={16} />
              </div>
              <div class="flex-1 min-w-0">
                <span class="text-sm font-semibold text-text-primary">{product.name}</span>
                {#if product.slug}
                  <span class="text-2xs text-text-tertiary ml-2">{product.slug}</span>
                {/if}
              </div>
              <ChevronRight size={14} class="text-text-tertiary" />
            </button>
          {/each}
        </div>

      <!-- Step 2: Type -->
      {:else if step === 2}
        <p class="text-sm text-text-secondary mb-3">What type of fixture?</p>
        <div class="space-y-1.5">
          {#each [
            { value: 'MANUFACTURING', label: 'Manufacturing', desc: 'Production flashing and POST testing' },
            { value: 'VALIDATION', label: 'Validation', desc: 'Firmware validation and regression testing' },
          ] as opt}
            <button
              onclick={() => { selectedType = opt.value as any; nextStep(); }}
              class="w-full flex items-center gap-3 rounded-lg border px-4 py-3 text-left transition-colors
                {selectedType === opt.value
                  ? 'border-accent bg-accent-muted'
                  : 'border-border hover:border-accent/50 hover:bg-surface-0/50'}"
            >
              <div class="flex-1">
                <span class="text-sm font-semibold text-text-primary">{opt.label}</span>
                <p class="text-2xs text-text-tertiary">{opt.desc}</p>
              </div>
              <ChevronRight size={14} class="text-text-tertiary" />
            </button>
          {/each}
        </div>

      <!-- Step 3: Hardware Revision -->
      {:else if step === 3}
        <p class="text-sm text-text-secondary mb-3">Which hardware revision?</p>
        {#if revisions.length === 0}
          <p class="text-sm text-text-tertiary py-4 text-center">No board revisions found for this product.</p>
        {:else}
          <div class="space-y-1.5">
            {#each revisions as rev}
              <button
                onclick={() => { selectedRevisionId = rev.id; nextStep(); }}
                class="w-full flex items-center gap-3 rounded-lg border px-4 py-3 text-left transition-colors
                  {selectedRevisionId === rev.id
                    ? 'border-accent bg-accent-muted'
                    : 'border-border hover:border-accent/50 hover:bg-surface-0/50'}"
              >
                <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-surface-2 text-sm font-bold text-text-tertiary">
                  {rev.version}
                </div>
                <div class="flex-1">
                  <span class="text-sm font-semibold text-text-primary">{rev.ckBoardsName}</span>
                </div>
                <ChevronRight size={14} class="text-text-tertiary" />
              </button>
            {/each}
          </div>
        {/if}

      <!-- Step 4: Fixture Design -->
      {:else if step === 4}
        <p class="text-sm text-text-secondary mb-3">Select a fixture design.</p>
        {#if designs.length === 0}
          <div class="text-center py-6">
            <p class="text-sm text-text-secondary">No fixture designs available.</p>
            <p class="text-2xs text-text-tertiary mt-1">Release a test app to publish a fixture design.</p>
          </div>
        {:else}
          <div class="space-y-1.5">
            {#each designs as design}
              <button
                onclick={() => { selectedDesignId = design.id; nextStep(); }}
                class="w-full flex items-center gap-3 rounded-lg border px-4 py-3 text-left transition-colors
                  {selectedDesignId === design.id
                    ? 'border-accent bg-accent-muted'
                    : 'border-border hover:border-accent/50 hover:bg-surface-0/50'}"
              >
                <div class="flex-1">
                  <span class="text-sm font-semibold text-text-primary">{design.name}</span>
                  <div class="flex items-center gap-2 mt-0.5">
                    <span class="text-2xs text-text-tertiary">Rev {design.revision}</span>
                    {#if design.capabilities?.length}
                      <span class="text-2xs text-text-tertiary">·</span>
                      {#each design.capabilities as cap}
                        <span class="rounded bg-surface-2 px-1.5 py-0.5 text-2xs font-medium text-text-secondary">{cap}</span>
                      {/each}
                    {/if}
                  </div>
                </div>
                <ChevronRight size={14} class="text-text-tertiary" />
              </button>
            {/each}
          </div>
        {/if}

      <!-- Step 5: Name -->
      {:else if step === 5}
        <p class="text-sm text-text-secondary mb-3">Name this fixture instance.</p>

        <div class="space-y-4">
          <!-- Summary -->
          <div class="rounded-lg border border-border bg-surface-0 p-3 space-y-1 text-2xs text-text-secondary">
            <div><span class="text-text-tertiary">Product:</span> {selectedProduct?.name}</div>
            <div><span class="text-text-tertiary">Type:</span> {selectedType}</div>
            <div><span class="text-text-tertiary">Revision:</span> {revisions.find(r => r.id === selectedRevisionId)?.version}</div>
            <div><span class="text-text-tertiary">Design:</span> {selectedDesign?.name} v{selectedDesign?.revision}</div>
          </div>

          <div>
            <label for="fixture-name" class="block text-2xs font-medium text-text-secondary mb-1">Fixture Name</label>
            <input
              id="fixture-name"
              type="text"
              bind:value={fixtureName}
              placeholder="e.g., Alpha B0 Mfg Fixture 1"
              class="input input-sm w-full"
            />
          </div>

          {#if error}
            <div class="rounded-lg border border-error/30 bg-error-muted px-3 py-2 text-sm text-error">{error}</div>
          {/if}
        </div>
      {/if}
    </div>

    <!-- Footer -->
    <div class="flex justify-between mt-6 pt-4 border-t border-border-subtle">
      <button onclick={step > 1 ? prevStep : resetAndClose} class="btn btn-sm btn-ghost">
        {step > 1 ? 'Back' : 'Cancel'}
      </button>
      {#if step === 5}
        <button
          onclick={handleCreate}
          disabled={submitting || !fixtureName.trim()}
          class="btn btn-sm btn-primary"
        >
          {#if submitting}<Loader2 size={12} class="animate-spin" />{/if}
          {submitting ? 'Creating...' : 'Create Fixture'}
        </button>
      {/if}
    </div>
  {/snippet}
</Modal>
