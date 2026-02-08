<script lang="ts">
  import { Upload } from 'lucide-svelte';

  interface Props {
    onUpload: (file: File) => Promise<void>;
    disabled?: boolean;
  }

  let { onUpload, disabled = false }: Props = $props();

  let dragOver = $state(false);
  let uploading = $state(false);

  async function handleFile(file: File) {
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
  class={[
    'flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-4 transition-colors',
    dragOver
      ? 'border-accent bg-accent-muted'
      : 'border-border bg-surface-0 hover:border-text-tertiary',
    disabled ? 'pointer-events-none opacity-50' : 'cursor-pointer'
  ].join(' ')}
>
  <label class="flex cursor-pointer flex-col items-center gap-2">
    <input
      type="file"
      onchange={handleChange}
      class="hidden"
      disabled={disabled || uploading}
    />
    <Upload
      size={20}
      class="text-text-tertiary"
      strokeWidth={1.5}
    />
    <span class="text-2xs text-text-tertiary">
      {uploading ? 'Uploading...' : 'Drop file or click to upload'}
    </span>
  </label>
</div>
