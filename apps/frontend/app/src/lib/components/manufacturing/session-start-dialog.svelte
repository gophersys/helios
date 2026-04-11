<script lang="ts">
  import { onMount } from 'svelte';
  import { X, Loader2, Play } from 'lucide-svelte';
  import { api } from '$lib/api';
  import type { ApiResponse } from '$lib/types';
  import type { AssetSet, ManufacturingSession } from '$lib/types/models';

  let {
    productId,
    fixtureId,
    fixtureName,
    productName,
    onStart,
    onCancel,
  }: {
    productId: string;
    fixtureId: string;
    fixtureName: string;
    productName: string;
    onStart: (sessionId: string) => void;
    onCancel: () => void;
  } = $props();

  let assetSets = $state<AssetSet[]>([]);
  let loadingAssets = $state(true);
  let selectedAssetSetId = $state<string>('');
  let notes = $state('');
  let submitting = $state(false);
  let error = $state<string | null>(null);

  async function fetchAssetSets() {
    loadingAssets = true;
    try {
      const res = await api.get<ApiResponse<AssetSet[]>>(
        `/v2/products/${productId}/asset-sets?status=COMPLETE`
      );
      assetSets = res.data || [];
    } catch {
      // Asset sets may not be available; proceed with "latest" only
      assetSets = [];
    } finally {
      loadingAssets = false;
    }
  }

  async function handleStart() {
    submitting = true;
    error = null;
    try {
      const body: Record<string, unknown> = { productId, fixtureId };
      if (selectedAssetSetId) {
        body.assetSetId = selectedAssetSetId;
      }
      if (notes.trim()) {
        body.notes = notes.trim();
      }
      const res = await api.post<ApiResponse<ManufacturingSession>>(
        '/v2/manufacturing/sessions',
        body
      );
      onStart(res.data.id);
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to create session';
    } finally {
      submitting = false;
    }
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') {
      onCancel();
    } else if (e.key === 'Enter' && !submitting) {
      handleStart();
    }
  }

  onMount(() => {
    fetchAssetSets();
  });
</script>

<!-- Overlay -->
<div
  class="fixed inset-0 z-modal-backdrop bg-overlay animate-overlay-in"
  onclick={onCancel}
  onkeydown={handleKeydown}
  role="presentation"
  tabindex="-1"
></div>

<!-- Dialog -->
<div class="fixed inset-0 z-modal flex items-center justify-center p-4">
  <div
    class="w-full max-w-md animate-modal-in rounded-lg border border-border bg-surface-1 shadow-xl"
    role="dialog"
    aria-modal="true"
    aria-labelledby="session-start-title"
  >
    <!-- Header -->
    <div class="flex items-center justify-between border-b border-border px-6 py-4">
      <h2 id="session-start-title" class="text-sm font-semibold text-text-primary">
        New Manufacturing Session
      </h2>
      <button
        onclick={onCancel}
        class="flex h-8 w-8 items-center justify-center rounded-lg text-text-tertiary hover:bg-surface-2 hover:text-text-primary"
        title="Cancel"
        aria-label="Cancel"
      >
        <X size={20} strokeWidth={1.75} />
      </button>
    </div>

    <!-- Body -->
    <div class="p-6 space-y-4">
      {#if error}
        <div class="rounded-lg bg-error-muted px-3 py-2 text-sm text-error">
          {error}
        </div>
      {/if}

      <!-- Read-only context -->
      <div class="space-y-2">
        <div>
          <label class="block text-2xs font-medium text-text-tertiary">Product</label>
          <p class="text-sm text-text-primary">{productName}</p>
        </div>
        <div>
          <label class="block text-2xs font-medium text-text-tertiary">Fixture</label>
          <p class="text-sm text-text-primary">{fixtureName}</p>
        </div>
      </div>

      <!-- Firmware version -->
      <div>
        <label for="asset-set-select" class="mb-1 block text-2xs font-medium text-text-tertiary">
          Firmware version
        </label>
        {#if loadingAssets}
          <div class="flex items-center gap-2 rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-tertiary">
            <Loader2 size={14} class="animate-spin" />
            Loading firmware versions...
          </div>
        {:else}
          <select
            id="asset-set-select"
            bind:value={selectedAssetSetId}
            class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-hidden"
          >
            <option value="">Latest available</option>
            {#each assetSets as set}
              <option value={set.id}>
                {set.version} ({set.variant}) — {set.status}
              </option>
            {/each}
          </select>
        {/if}
      </div>

      <!-- Notes -->
      <div>
        <label for="session-notes" class="mb-1 block text-2xs font-medium text-text-tertiary">
          Notes (optional)
        </label>
        <textarea
          id="session-notes"
          bind:value={notes}
          rows="2"
          placeholder="Batch number, shift notes, etc."
          class="w-full resize-none rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-hidden"
        ></textarea>
      </div>
    </div>

    <!-- Footer -->
    <div class="flex justify-end gap-2 border-t border-border px-6 py-4">
      <button
        onclick={onCancel}
        disabled={submitting}
        class="rounded-lg px-4 py-2 text-sm font-medium text-text-secondary hover:bg-surface-2 disabled:opacity-50"
      >
        Cancel
      </button>
      <button
        onclick={handleStart}
        disabled={submitting}
        class="flex items-center gap-1.5 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
      >
        {#if submitting}
          <Loader2 size={14} class="animate-spin" />
          Starting...
        {:else}
          <Play size={14} />
          Start Session
        {/if}
      </button>
    </div>
  </div>
</div>
