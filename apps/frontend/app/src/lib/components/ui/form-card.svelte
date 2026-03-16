<script lang="ts">
  import { X } from 'lucide-svelte';
  import type { Snippet } from 'svelte';

  interface Props {
    title: string;
    onClose: () => void;
    children: Snippet;
  }

  let { title, onClose, children }: Props = $props();
</script>

<div class="mb-6 card card-md">
  <div class="mb-4 flex items-center justify-between">
    <h3 class="text-sm font-semibold text-text-primary">
      {title}
    </h3>
    <button
      onclick={onClose}
      class="rounded-lg p-1 text-text-tertiary hover:bg-surface-2 hover:text-text-primary"
    >
      <X size={16} />
    </button>
  </div>
  {@render children()}
</div>
