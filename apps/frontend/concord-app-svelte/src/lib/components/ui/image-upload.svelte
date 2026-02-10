<script lang="ts">
  import { Upload } from 'lucide-svelte';

  interface Props {
    currentUrl?: string | null;
    onUpload: (file: File) => Promise<void>;
    disabled?: boolean;
  }

  let { currentUrl = null, onUpload, disabled = false }: Props = $props();

  let dragOver = $state(false);
  let uploading = $state(false);
  let preview = $state<string | null>(null);
  let fileInput = $state<HTMLInputElement | null>(null);

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      fileInput?.click();
    }
  }

  const displayUrl = $derived(preview || currentUrl);

  async function handleFile(file: File) {
    const ext = file.name.split('.').pop()?.toLowerCase();
    if (!ext || !['png', 'jpg', 'jpeg', 'webp'].includes(ext)) {
      return;
    }
    if (preview) URL.revokeObjectURL(preview);
    preview = URL.createObjectURL(file);
    uploading = true;
    try {
      await onUpload(file);
    } finally {
      uploading = false;
    }
  }

  function handleDrop(e: DragEvent) {
    e.preventDefault();
    dragOver = false;
    const file = e.dataTransfer?.files[0];
    if (file) handleFile(file);
  }

  function handleChange(e: Event) {
    const input = e.target as HTMLInputElement;
    const file = input.files?.[0];
    if (file) handleFile(file);
    input.value = '';
  }
</script>

<div
  role="button"
  tabindex="0"
  ondragover={(e) => { e.preventDefault(); dragOver = true; }}
  ondragleave={() => (dragOver = false)}
  ondrop={handleDrop}
  onkeydown={handleKeydown}
  class={[
    'relative flex flex-col items-center justify-center rounded-lg border-2 border-dashed transition-colors',
    dragOver
      ? 'border-accent bg-accent-muted'
      : 'border-border bg-surface-0 hover:border-text-tertiary',
    disabled ? 'pointer-events-none opacity-50' : 'cursor-pointer',
    displayUrl ? 'h-40' : 'h-32'
  ].join(' ')}
>
  {#if displayUrl}
    <img
      src={displayUrl}
      alt="Hero"
      class="h-full w-full rounded-lg object-contain"
    />
    {#if !disabled}
      <label class="absolute inset-0 flex cursor-pointer items-center justify-center rounded-lg bg-overlay opacity-0 transition-opacity hover:opacity-100">
        <input
          bind:this={fileInput}
          type="file"
          accept=".png,.jpg,.jpeg,.webp"
          onchange={handleChange}
          class="hidden"
          aria-label="Upload image"
        />
        <span class="text-xs font-medium text-white">
          {uploading ? 'Uploading...' : 'Replace image'}
        </span>
      </label>
    {/if}
  {:else}
    <label class="flex cursor-pointer flex-col items-center gap-2 p-4">
      <input
        bind:this={fileInput}
        type="file"
        accept=".png,.jpg,.jpeg,.webp"
        onchange={handleChange}
        class="hidden"
        aria-label="Upload image"
      />
      <Upload
        size={20}
        class="text-text-tertiary"
        strokeWidth={1.5}
      />
      <span class="text-2xs text-text-tertiary">
        {uploading ? 'Uploading...' : 'Drop image or click to upload'}
      </span>
    </label>
  {/if}
</div>
