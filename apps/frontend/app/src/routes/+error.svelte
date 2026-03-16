<script lang="ts">
  import { page } from '$app/stores';
  import { AlertTriangle, RefreshCw } from 'lucide-svelte';

  function handleRetry(): void {
    window.location.reload();
  }
</script>

<div class="flex min-h-screen items-center justify-center bg-surface-0 px-4">
  <div class="w-full max-w-md text-center">
    <div class="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-error-muted">
      <AlertTriangle size={32} class="text-error" strokeWidth={1.5} />
    </div>

    <h1 class="mb-2 text-xl font-semibold text-text-primary">Something went wrong</h1>

    <p class="mb-6 text-sm text-text-secondary">
      {$page.error?.message || 'An unexpected error occurred.'}
    </p>

    <button
      onclick={handleRetry}
      class="inline-flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover"
    >
      <RefreshCw size={16} strokeWidth={1.75} />
      Try again
    </button>
  </div>
</div>
