<script lang="ts">
  import { Inbox } from 'lucide-svelte';

  let { message = 'No items found' }: { message?: string } = $props();
</script>

<div class="card flex flex-col items-center justify-center py-12">
  <Inbox size={32} class="text-text-tertiary" strokeWidth={1.5} />
  <p class="mt-3 text-sm text-text-tertiary">{message}</p>
</div>
