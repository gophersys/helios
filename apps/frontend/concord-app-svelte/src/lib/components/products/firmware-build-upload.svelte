<script lang="ts">
  import { Upload, Check, X } from 'lucide-svelte';
  import { apiUpload } from '$lib/api';
  import Select from '$lib/components/ui/select.svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import type { BoardRevision } from '$lib/types/models';

  interface Props {
    productId: string;
    applicationId: string;
    boardRevisions: BoardRevision[];
    onSuccess: () => void;
    onCancel: () => void;
  }

  let { productId, applicationId, boardRevisions, onSuccess, onCancel }: Props = $props();

  let error = $state<string | null>(null);
  let dragOver = $state(false);
  let uploading = $state(false);
  let selectedFile = $state<File | null>(null);

  let formVersion = $state('');
  let formMajor = $state(0);
  let formMinor = $state(0);
  let formBuild = $state(0);
  let formBoardRevisionId = $state('');
  let formBootloaderId = $state('');
  let formIsManufacturing = $state(false);
  let formStatus = $state('ACTIVE');
  let formNotes = $state('');

  function handleDrop(e: DragEvent) {
    e.preventDefault();
    dragOver = false;
    const file = e.dataTransfer?.files[0];
    if (file) selectedFile = file;
  }

  function handleFileChange(e: Event) {
    const input = e.target as HTMLInputElement;
    const file = input.files?.[0];
    if (file) selectedFile = file;
    input.value = '';
  }

  async function handleSubmit(e: Event) {
    e.preventDefault();
    if (!selectedFile) {
      error = 'Please select a file to upload';
      return;
    }

    error = null;
    uploading = true;

    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('version', formVersion);
    formData.append('majorVersion', String(formMajor));
    formData.append('minorVersion', String(formMinor));
    formData.append('buildNumber', String(formBuild));
    formData.append('applicationId', applicationId);
    if (formBoardRevisionId) formData.append('boardRevisionId', formBoardRevisionId);
    if (formBootloaderId) formData.append('bootloaderId', formBootloaderId);
    formData.append('isManufacturing', String(formIsManufacturing));
    formData.append('status', formStatus);
    if (formNotes) formData.append('notes', formNotes);

    try {
      await apiUpload(`/v2/products/${productId}/firmware-builds`, formData);
      onSuccess();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to upload build';
    } finally {
      uploading = false;
    }
  }
</script>

<div class="rounded-lg border border-border bg-surface-0 p-3">
  <ErrorAlert message={error} />

  <form onsubmit={handleSubmit}>
    <!-- File drop zone -->
    <div
      role="button"
      tabindex="0"
      ondragover={(e) => { e.preventDefault(); dragOver = true; }}
      ondragleave={() => (dragOver = false)}
      ondrop={handleDrop}
      class={[
        'mb-3 flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-4 transition-colors',
        dragOver ? 'border-accent bg-accent-muted' : 'border-border bg-surface-1 hover:border-text-tertiary'
      ].join(' ')}
    >
      <label class="flex cursor-pointer flex-col items-center gap-2">
        <input
          type="file"
          onchange={handleFileChange}
          class="hidden"
        />
        <Upload size={20} class="text-text-tertiary" strokeWidth={1.5} />
        {#if selectedFile}
          <span class="text-xs font-medium text-text-primary">{selectedFile.name}</span>
        {:else}
          <span class="text-2xs text-text-tertiary">Drop firmware file or click to select</span>
        {/if}
      </label>
    </div>

    <div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <label>
        <span class="mb-1 block text-2xs font-medium text-text-tertiary">Version</span>
        <input
          type="text"
          required
          bind:value={formVersion}
          placeholder="e.g. 1.0.0"
          class="w-full rounded-lg border border-border bg-surface-1 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
        />
      </label>
      <div class="grid grid-cols-3 gap-1">
        <label>
          <span class="mb-1 block text-2xs font-medium text-text-tertiary">Major</span>
          <input
            type="number"
            min="0"
            bind:value={formMajor}
            class="w-full rounded-lg border border-border bg-surface-1 px-2 py-2 text-sm text-text-primary focus:border-accent focus:outline-none"
          />
        </label>
        <label>
          <span class="mb-1 block text-2xs font-medium text-text-tertiary">Minor</span>
          <input
            type="number"
            min="0"
            bind:value={formMinor}
            class="w-full rounded-lg border border-border bg-surface-1 px-2 py-2 text-sm text-text-primary focus:border-accent focus:outline-none"
          />
        </label>
        <label>
          <span class="mb-1 block text-2xs font-medium text-text-tertiary">Build</span>
          <input
            type="number"
            min="0"
            bind:value={formBuild}
            class="w-full rounded-lg border border-border bg-surface-1 px-2 py-2 text-sm text-text-primary focus:border-accent focus:outline-none"
          />
        </label>
      </div>
      <Select
        bind:value={formBoardRevisionId}
        label="Board Revision"
        placeholder="None"
        options={boardRevisions.map(rev => ({ value: rev.id, label: rev.version }))}
      />
      <Select
        bind:value={formStatus}
        label="Status"
        options={[
          { value: 'ACTIVE', label: 'Active' },
          { value: 'DEPRECATED', label: 'Deprecated' },
          { value: 'EOL', label: 'End of Life' },
        ]}
      />
    </div>

    <div class="mt-3 grid grid-cols-2 gap-3">
      <label>
        <span class="mb-1 block text-2xs font-medium text-text-tertiary">Bootloader ID (optional)</span>
        <input
          type="text"
          bind:value={formBootloaderId}
          placeholder="e.g. BL_1.0"
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

    <div class="mt-3">
      <label class="flex items-center gap-2 text-sm text-text-primary">
        <input
          type="checkbox"
          bind:checked={formIsManufacturing}
          class="rounded border-border"
        />
        Manufacturing build
      </label>
    </div>

    <div class="mt-4 flex gap-2">
      <button
        type="submit"
        disabled={uploading || !selectedFile}
        class="flex items-center gap-1.5 rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-accent-hover disabled:opacity-50"
      >
        <Check size={16} />
        {uploading ? 'Uploading...' : 'Upload'}
      </button>
      <button
        type="button"
        onclick={onCancel}
        class="flex items-center gap-1 rounded-lg px-3 py-1.5 text-xs font-medium text-text-secondary hover:bg-surface-2"
      >
        <X size={16} />
        Cancel
      </button>
    </div>
  </form>
</div>
