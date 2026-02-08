<script lang="ts">
  import { untrack } from 'svelte';
  import { Check } from 'lucide-svelte';
  import Select from '$lib/components/ui/select.svelte';

  interface Props {
    initial?: {
      version: string;
      status: string;
      releaseNotes: string | null;
      tagName: string | null;
    };
    onSubmit: (data: {
      version: string;
      status: string;
      releaseNotes: string | null;
      tagName: string | null;
    }) => Promise<void>;
    onCancel: () => void;
  }

  let { initial, onSubmit, onCancel }: Props = $props();

  let version = $state(untrack(() => initial?.version || ''));
  let status = $state(untrack(() => initial?.status || 'DRAFT'));
  let releaseNotes = $state(untrack(() => initial?.releaseNotes || ''));
  let tagName = $state(untrack(() => initial?.tagName || ''));
  let submitting = $state(false);

  async function handleSubmit(e: Event) {
    e.preventDefault();
    submitting = true;
    try {
      await onSubmit({
        version,
        status,
        releaseNotes: releaseNotes || null,
        tagName: tagName || null,
      });
    } finally {
      submitting = false;
    }
  }
</script>

<form
  onsubmit={handleSubmit}
  class="rounded-lg border border-border bg-surface-0 p-3"
>
  <div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
    <label>
      <span class="mb-1 block text-2xs font-medium text-text-tertiary">Version</span>
      <input
        type="text"
        required
        bind:value={version}
        placeholder="e.g. 1.0.0"
        class="w-full rounded-lg border border-border bg-surface-1 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
      />
    </label>
    <Select
      bind:value={status}
      label="Status"
      options={[
        { value: 'DRAFT', label: 'Draft' },
        { value: 'RELEASED', label: 'Released' },
        { value: 'DEPRECATED', label: 'Deprecated' },
      ]}
    />
    <label>
      <span class="mb-1 block text-2xs font-medium text-text-tertiary">Tag Name</span>
      <input
        type="text"
        bind:value={tagName}
        placeholder="e.g. v1.0.0"
        class="w-full rounded-lg border border-border bg-surface-1 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
      />
    </label>
    <label>
      <span class="mb-1 block text-2xs font-medium text-text-tertiary">Release Notes</span>
      <input
        type="text"
        bind:value={releaseNotes}
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
      {initial ? 'Save' : 'Create'}
    </button>
    <button
      type="button"
      onclick={onCancel}
      class="rounded-lg px-3 py-1.5 text-xs font-medium text-text-secondary hover:bg-surface-2"
    >
      Cancel
    </button>
  </div>
</form>
