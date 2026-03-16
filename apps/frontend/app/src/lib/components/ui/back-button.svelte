<script lang="ts">
  import { ArrowLeft } from 'lucide-svelte';

  let {
    label = 'Back',
    onclick
  }: {
    label?: string;
    onclick: () => void;
  } = $props();
</script>

<button
  {onclick}
  class="mb-4 flex items-center gap-2 text-sm font-medium text-text-secondary transition-colors hover:text-text-primary"
>
  <ArrowLeft size={16} strokeWidth={1.75} />
  {label}
</button>
