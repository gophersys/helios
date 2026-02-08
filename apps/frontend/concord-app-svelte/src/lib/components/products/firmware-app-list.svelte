<script lang="ts">
  import { Plus, Check, ChevronDown, ChevronRight, Trash2 } from 'lucide-svelte';
  import { api } from '$lib/api';
  import Select from '$lib/components/ui/select.svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import ConfirmDeleteDialog from '$lib/components/ui/confirm-delete-dialog.svelte';
  import FirmwareBuildList from './firmware-build-list.svelte';
  import type { FirmwareApp, FirmwareBuild, BoardRevision, ChipsetConfig, ChipsetEntry } from '$lib/types/models';

  interface Props {
    productId: string;
    apps: FirmwareApp[];
    builds: FirmwareBuild[];
    boardRevisions: BoardRevision[];
    chipsetConfig: ChipsetConfig | null;
    canManage: boolean;
    onRefresh: () => void;
  }

  let { productId, apps, builds, boardRevisions, chipsetConfig, canManage, onRefresh }: Props = $props();

  let error = $state<string | null>(null);
  let showForm = $state(false);
  let submitting = $state(false);
  let expandedApps = $state(new Set<string>());
  let deleteTarget = $state<{ id: string; name: string } | null>(null);

  let formAppId = $state(0);
  let formName = $state('');
  let formChipset = $state('');
  let formTargetMcu = $state('');
  let formCloudDeviceType = $state('');
  let formCloudVariant = $state('');
  let formNotes = $state('');

  // Group apps by chipset
  interface GroupedApps {
    chipset: string;
    apps: FirmwareApp[];
  }

  const groupedApps = $derived.by(() => {
    const groups: Record<string, FirmwareApp[]> = {};
    for (const app of apps) {
      const chip = app.chipset || 'Other';
      if (!groups[chip]) groups[chip] = [];
      groups[chip].push(app);
    }
    return Object.entries(groups)
      .map(([chipset, appList]) => ({ chipset, apps: appList }))
      .sort((a, b) => a.chipset.localeCompare(b.chipset));
  });

  const chipsets = $derived(chipsetConfig?.chipsets || []);
  const selectedChipsetConfig = $derived(chipsets.find((c: ChipsetEntry) => c.name === formChipset));
  const targetMcuOptions = $derived(selectedChipsetConfig?.targetMcus || []);

  function toggleExpanded(appId: string) {
    const next = new Set(expandedApps);
    if (next.has(appId)) {
      next.delete(appId);
    } else {
      next.add(appId);
    }
    expandedApps = next;
  }

  function getBuildsForApp(appId: string): FirmwareBuild[] {
    return builds.filter((b) => b.applicationId === appId);
  }

  function resetForm() {
    formAppId = 0;
    formName = '';
    formChipset = '';
    formTargetMcu = '';
    formCloudDeviceType = '';
    formCloudVariant = '';
    formNotes = '';
    showForm = false;
  }

  async function handleSubmit(e: Event) {
    e.preventDefault();
    error = null;
    submitting = true;

    const body = {
      applicationId: formAppId,
      name: formName,
      chipset: formChipset || null,
      targetMcu: formTargetMcu || null,
      coreCloudDeviceType: formCloudDeviceType || null,
      coreCloudVariant: formCloudVariant || null,
      notes: formNotes || null,
    };

    try {
      await api.post(`/v2/products/${productId}/firmware-apps`, body);
      resetForm();
      onRefresh();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to create firmware app';
    } finally {
      submitting = false;
    }
  }

  function promptDelete(appId: string) {
    const app = apps.find((a) => a.id === appId);
    deleteTarget = { id: appId, name: app?.name || '' };
  }

  async function handleDelete(appId: string) {
    error = null;
    try {
      await api.delete(`/v2/products/${productId}/firmware-apps/${appId}`);
      onRefresh();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to delete firmware app';
    }
  }
</script>

<div>
  <ErrorAlert message={error} />

  <div class="mb-3 flex items-center justify-between">
    <h3 class="text-sm font-semibold text-text-primary">Firmware Applications</h3>
    {#if canManage && !showForm}
      <button
        onclick={() => { resetForm(); showForm = true; }}
        class="flex items-center gap-1.5 rounded-lg bg-accent px-2.5 py-1.5 text-2xs font-medium text-white hover:bg-accent-hover"
      >
        <Plus size={16} />
        Add application
      </button>
    {/if}
  </div>

  {#if showForm}
    <form
      onsubmit={handleSubmit}
      class="mb-4 rounded-lg border border-border bg-surface-0 p-3"
    >
      <div class="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <label>
          <span class="mb-1 block text-2xs font-medium text-text-tertiary">Application ID</span>
          <input
            type="number"
            required
            min="0"
            bind:value={formAppId}
            placeholder="e.g. 1"
            class="w-full rounded-lg border border-border bg-surface-1 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
          />
        </label>
        <label>
          <span class="mb-1 block text-2xs font-medium text-text-tertiary">Name</span>
          <input
            type="text"
            required
            bind:value={formName}
            placeholder="e.g. Main App"
            class="w-full rounded-lg border border-border bg-surface-1 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
          />
        </label>
        <Select
          bind:value={formChipset}
          label="Chipset"
          placeholder="Select..."
          options={chipsets.map(chip => ({ value: chip.name, label: chip.name }))}
        />
      </div>
      <div class="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Select
          bind:value={formTargetMcu}
          disabled={!formChipset}
          label="Target MCU"
          placeholder="Select..."
          options={targetMcuOptions.map(mcu => ({ value: mcu, label: mcu }))}
        />
        <label>
          <span class="mb-1 block text-2xs font-medium text-text-tertiary">Cloud Device Type</span>
          <input
            type="text"
            bind:value={formCloudDeviceType}
            placeholder="Optional"
            class="w-full rounded-lg border border-border bg-surface-1 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
          />
        </label>
        <label>
          <span class="mb-1 block text-2xs font-medium text-text-tertiary">Cloud Variant</span>
          <input
            type="text"
            bind:value={formCloudVariant}
            placeholder="Optional"
            class="w-full rounded-lg border border-border bg-surface-1 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
          />
        </label>
        <label>
          <span class="mb-1 block text-2xs font-medium text-text-tertiary">Notes</span>
          <input
            type="text"
            bind:value={formNotes}
            placeholder="Optional"
            class="w-full rounded-lg border border-border bg-surface-1 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
          />
        </label>
      </div>
      <div class="mt-3 flex gap-2">
        <button
          type="submit"
          disabled={submitting}
          class="flex items-center gap-1.5 rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-accent-hover disabled:opacity-50"
        >
          <Check size={16} />
          {submitting ? 'Creating...' : 'Create'}
        </button>
        <button
          type="button"
          onclick={resetForm}
          class="rounded-lg px-3 py-1.5 text-xs font-medium text-text-secondary hover:bg-surface-2"
        >
          Cancel
        </button>
      </div>
    </form>
  {/if}

  {#if groupedApps.length > 0}
    <div class="space-y-2">
      {#each groupedApps as group}
        <div class="rounded-lg border border-border bg-surface-0">
          <div class="border-b border-border-subtle bg-surface-1 px-3 py-2 text-xs font-semibold text-text-secondary">
            {group.chipset}
            <span class="ml-1 font-normal text-text-tertiary">({group.apps.length})</span>
          </div>
          {#each group.apps as app (app.id)}
            {@const isExpanded = expandedApps.has(app.id)}
            {@const appBuilds = getBuildsForApp(app.id)}
            <div class="border-b border-border-subtle last:border-0">
              <div
                role="button"
                tabindex="0"
                onclick={() => toggleExpanded(app.id)}
                onkeydown={(e) => e.key === 'Enter' && toggleExpanded(app.id)}
                class="flex cursor-pointer items-center gap-3 px-3 py-2 hover:bg-surface-1"
              >
                {#if isExpanded}
                  <ChevronDown size={16} class="shrink-0 text-text-tertiary" />
                {:else}
                  <ChevronRight size={16} class="shrink-0 text-text-tertiary" />
                {/if}
                <span class="font-medium text-text-primary text-sm">{app.name}</span>
                <span class="text-2xs text-text-tertiary">ID: {app.applicationId}</span>
                {#if app.targetMcu}
                  <span class="rounded-full bg-surface-2 px-2 py-0.5 text-2xs text-text-secondary">{app.targetMcu}</span>
                {/if}
                <span class="ml-auto text-2xs text-text-tertiary">
                  {appBuilds.length} build{appBuilds.length !== 1 ? 's' : ''}
                </span>
                {#if canManage}
                  <button
                    onclick={(e) => { e.stopPropagation(); promptDelete(app.id); }}
                    class="rounded p-1 text-text-tertiary hover:bg-error-muted hover:text-error"
                    title="Delete app"
                    aria-label="Delete app"
                  >
                    <Trash2 size={16} />
                  </button>
                {/if}
              </div>
              {#if isExpanded}
                <div class="border-t border-border-subtle bg-surface-0 px-4 py-3">
                  {#if app.notes}
                    <p class="mb-3 text-sm text-text-secondary">{app.notes}</p>
                  {/if}
                  <FirmwareBuildList
                    {productId}
                    applicationId={app.id}
                    builds={appBuilds}
                    {boardRevisions}
                    {canManage}
                    {onRefresh}
                  />
                </div>
              {/if}
            </div>
          {/each}
        </div>
      {/each}
    </div>
  {:else}
    <div class="py-6 text-center text-sm text-text-tertiary">
      No firmware applications yet
    </div>
  {/if}

  <ConfirmDeleteDialog
    open={!!deleteTarget}
    entityType="firmware application"
    entityName={deleteTarget?.name || ''}
    onConfirm={() => { handleDelete(deleteTarget!.id); deleteTarget = null; }}
    onCancel={() => (deleteTarget = null)}
  />
</div>
