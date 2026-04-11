<script lang="ts">
  import { onMount } from 'svelte';
  import { Loader2, Play } from 'lucide-svelte';
  import Modal from '$lib/components/ui/modal.svelte';
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
    if (e.key === 'Enter' && !submitting) {
      handleStart();
    }
  }

  onMount(() => {
    fetchAssetSets();
  });
</script>

<svelte:window onkeydown={handleKeydown} />

<Modal open={true} title="New Manufacturing Session" onclose={onCancel} size="md">
  <div class="space-y-4">
    {#if error}
      <div class="rounded-lg bg-error-muted px-3 py-2 text-sm text-error">
        {error}
      </div>
    {/if}

    <!-- Read-only context -->
    <div class="space-y-2">
      <div class="form-group">
        <label class="form-label text-2xs text-text-tertiary">Product</label>
        <p class="text-sm text-text-primary">{productName}</p>
      </div>
      <div class="form-group">
        <label class="form-label text-2xs text-text-tertiary">Fixture</label>
        <p class="text-sm text-text-primary">{fixtureName}</p>
      </div>
    </div>

    <!-- Firmware version -->
    <div class="form-group">
      <label for="asset-set-select" class="form-label text-2xs text-text-tertiary">
        Firmware version
      </label>
      {#if loadingAssets}
        <div class="flex items-center gap-2 input input-md text-text-tertiary">
          <Loader2 size={14} class="animate-spin" />
          Loading firmware versions...
        </div>
      {:else}
        <select
          id="asset-set-select"
          bind:value={selectedAssetSetId}
          class="input input-md"
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
    <div class="form-group">
      <label for="session-notes" class="form-label text-2xs text-text-tertiary">
        Notes (optional)
      </label>
      <textarea
        id="session-notes"
        bind:value={notes}
        rows="2"
        placeholder="Batch number, shift notes, etc."
        class="input px-3 py-2 resize-none"
      ></textarea>
    </div>
  </div>

  {#snippet footer()}
    <button
      onclick={onCancel}
      disabled={submitting}
      class="btn btn-sm btn-ghost"
    >
      Cancel
    </button>
    <button
      onclick={handleStart}
      disabled={submitting}
      class="btn btn-sm btn-primary"
    >
      {#if submitting}
        <Loader2 size={14} class="animate-spin" />
        Starting...
      {:else}
        <Play size={14} />
        Start Session
      {/if}
    </button>
  {/snippet}
</Modal>
