<script lang="ts">
  import { AlertCircle } from 'lucide-svelte';

  let { message }: { message: string | null } = $props();
</script>

{#if message}
  <div role="alert" class="mb-4 flex items-start gap-3 rounded-lg bg-error-muted px-4 py-3">
    <AlertCircle size={20} class="mt-0.5 shrink-0 text-error" strokeWidth={1.75} />
    <p class="text-sm text-error">{message}</p>
  </div>
{/if}
