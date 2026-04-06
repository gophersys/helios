<script lang="ts">
  import { Package, Plus, Loader2, ChevronDown, Download, Trash2, Cpu } from 'lucide-svelte';
  import { apiFetch, api } from '$lib/api';
  import type { ApiResponse } from '$lib/types';
  import type { FirmwareSet } from '$lib/types/models';

  interface Props {
    productId: string;
    canManage: boolean;
  }

  let { productId, canManage }: Props = $props();

  let firmwareSets = $state<FirmwareSet[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let showCreate = $state(false);
  let expandedSet = $state<string | null>(null);

  // Create form
  let newVersion = $state('');
  let newVariant = $state('debug');
  let newTrack = $state('bench');
  let creating = $state(false);

  async function loadFirmware() {
    loading = true;
    error = null;
    try {
      const res = await apiFetch<ApiResponse<{ data: FirmwareSet[]; pagination: any }>>(
        `/v2/products/${productId}/firmware?limit=50`
      );
      firmwareSets = res.data?.data ?? [];
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load firmware';
    } finally {
      loading = false;
    }
  }

  async function createSet() {
    if (!newVersion.trim()) return;
    creating = true;
    try {
      await api.post(`/v2/products/${productId}/firmware`, {
        version: newVersion.trim(),
        variant: newVariant,
        releaseTrack: newTrack,
      });
      showCreate = false;
      newVersion = '';
      await loadFirmware();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to create firmware set';
    } finally {
      creating = false;
    }
  }

  async function deleteSet(setId: string) {
    try {
      await api.delete(`/v2/products/${productId}/firmware/${setId}`);
      await loadFirmware();
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to delete';
    }
  }

  const TRACK_COLORS: Record<string, string> = {
    bench: 'bg-warning-muted text-warning',
    engineering: 'bg-info-muted text-info',
    production: 'bg-success-muted text-success',
  };

  const VARIANT_COLORS: Record<string, string> = {
    smoke: 'bg-surface-2 text-text-secondary',
    debug: 'bg-accent/10 text-accent',
    release: 'bg-success-muted text-success',
    mfg: 'bg-warning-muted text-warning',
  };

  $effect(() => {
    loadFirmware();
  });
</script>

<div class="space-y-4">
  <!-- Header -->
  <div class="flex items-center justify-between">
    <h3 class="text-sm font-semibold text-text-primary">Firmware Sets</h3>
    {#if canManage}
      <button
        onclick={() => (showCreate = !showCreate)}
        class="inline-flex items-center gap-1.5 rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-accent-hover"
      >
        <Plus size={14} />
        New Firmware Set
      </button>
    {/if}
  </div>

  <!-- Create form -->
  {#if showCreate}
    <div class="rounded-lg border border-accent/30 bg-accent/5 p-4">
      <div class="grid gap-3 sm:grid-cols-3">
        <div>
          <label for="fw-version" class="mb-1 block text-2xs font-medium text-text-tertiary">Version</label>
          <input
            id="fw-version"
            type="text"
            bind:value={newVersion}
            placeholder="0.5.2"
            class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm font-mono text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
          />
        </div>
        <div>
          <label for="fw-variant" class="mb-1 block text-2xs font-medium text-text-tertiary">Variant</label>
          <select
            id="fw-variant"
            bind:value={newVariant}
            class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none"
          >
            <option value="smoke">Smoke</option>
            <option value="debug">Debug</option>
            <option value="release">Release</option>
            <option value="mfg">Manufacturing</option>
          </select>
        </div>
        <div>
          <label for="fw-track" class="mb-1 block text-2xs font-medium text-text-tertiary">Release Track</label>
          <select
            id="fw-track"
            bind:value={newTrack}
            class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none"
          >
            <option value="bench">Bench</option>
            <option value="engineering">Engineering</option>
            <option value="production">Production</option>
          </select>
        </div>
      </div>
      <div class="mt-3 flex gap-2">
        <button
          onclick={createSet}
          disabled={creating || !newVersion.trim()}
          class="rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-accent-hover disabled:opacity-50"
        >
          {creating ? 'Creating...' : 'Create'}
        </button>
        <button
          onclick={() => (showCreate = false)}
          class="rounded-lg px-3 py-1.5 text-xs font-medium text-text-secondary hover:bg-surface-2"
        >
          Cancel
        </button>
      </div>
    </div>
  {/if}

  <!-- Error -->
  {#if error}
    <div class="rounded-lg border border-error/30 bg-error-muted px-4 py-3 text-sm text-error">{error}</div>
  {/if}

  <!-- Loading -->
  {#if loading}
    <div class="flex items-center gap-2 py-8 text-sm text-text-tertiary">
      <Loader2 size={16} class="animate-spin" /> Loading firmware...
    </div>
  {:else if firmwareSets.length === 0}
    <!-- Empty state -->
    <div class="py-8 text-center">
      <Package size={32} class="mx-auto mb-3 text-text-tertiary opacity-40" />
      <p class="text-sm text-text-secondary">No firmware sets yet.</p>
      <p class="mt-1 text-2xs text-text-tertiary">
        Create a firmware set, then upload hex/cfw artifacts into it.
      </p>
    </div>
  {:else}
    <!-- Firmware set list -->
    <div class="space-y-2">
      {#each firmwareSets as fwSet (fwSet.id)}
        <div class="rounded-lg border border-border bg-surface-1">
          <!-- Set header -->
          <button
            onclick={() => (expandedSet = expandedSet === fwSet.id ? null : fwSet.id)}
            class="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-surface-2 transition-colors rounded-lg"
          >
            <ChevronDown
              size={14}
              class="shrink-0 transition-transform {expandedSet === fwSet.id ? '' : '-rotate-90'} text-text-tertiary"
            />
            <span class="font-mono text-sm font-semibold text-text-primary">v{fwSet.version}</span>
            <span class="rounded px-1.5 py-0.5 text-2xs font-medium {VARIANT_COLORS[fwSet.variant ?? ''] ?? 'bg-surface-2 text-text-secondary'}">
              {fwSet.variant ?? ''}
            </span>
            <span class="rounded px-1.5 py-0.5 text-2xs font-medium {TRACK_COLORS[fwSet.releaseTrack] ?? 'bg-surface-2 text-text-secondary'}">
              {fwSet.releaseTrack}
            </span>
            {#if fwSet.isManufacturing}
              <span class="rounded bg-warning-muted px-1.5 py-0.5 text-2xs font-medium text-warning">mfg</span>
            {/if}
            {#if fwSet.boardRevision}
              <span class="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-2xs text-text-tertiary">
                {fwSet.boardRevision.ckBoardsName}
              </span>
            {/if}
            <span class="ml-auto text-2xs text-text-tertiary">
              {fwSet.builds?.length ?? 0} builds · {fwSet.source}
            </span>
          </button>

          <!-- Expanded content -->
          {#if expandedSet === fwSet.id}
            <div class="border-t border-border px-4 py-3">
              {#if fwSet.builds && fwSet.builds.length > 0}
                <div class="space-y-2">
                  {#each fwSet.builds as build (build.id)}
                    <div class="flex items-center gap-3 rounded border border-border-subtle bg-surface-0 px-3 py-2">
                      {#if build.target}
                        <div class="flex items-center gap-1.5">
                          <Cpu size={12} class="text-accent" />
                          <span class="text-xs font-medium capitalize text-text-primary">{build.target.role}</span>
                          <span class="font-mono text-2xs text-text-tertiary">{build.target.soc}</span>
                          <span class="font-mono text-2xs text-accent">#{build.target.appId}</span>
                        </div>
                      {/if}
                      {#if build.versionString}
                        <span class="font-mono text-2xs text-text-secondary">{build.versionString}</span>
                      {/if}
                      <span class="text-2xs text-text-tertiary">{build.filename}</span>
                      <div class="ml-auto flex items-center gap-1">
                        {#if build.hexStorageKey}
                          <span class="rounded bg-surface-2 px-1 py-0.5 text-2xs text-text-tertiary">hex</span>
                        {/if}
                        {#if build.cfwStorageKey}
                          <span class="rounded bg-surface-2 px-1 py-0.5 text-2xs text-text-tertiary">cfw</span>
                        {/if}
                      </div>
                    </div>
                  {/each}
                </div>
              {:else}
                <p class="text-2xs text-text-tertiary">No builds uploaded yet. Upload hex/cfw artifacts into this set.</p>
              {/if}

              {#if canManage}
                <div class="mt-3 flex items-center gap-2 border-t border-border-subtle pt-3">
                  <button
                    onclick={() => deleteSet(fwSet.id)}
                    class="inline-flex items-center gap-1 rounded px-2 py-1 text-2xs text-error hover:bg-error-muted"
                  >
                    <Trash2 size={12} />
                    Delete Set
                  </button>
                </div>
              {/if}
            </div>
          {/if}
        </div>
      {/each}
    </div>
  {/if}
</div>
