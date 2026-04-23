<script lang="ts">
  import { Ban, Loader2 } from 'lucide-svelte';
  import { getRunExecutionContext } from './run-execution-context.svelte';

  const ctx = getRunExecutionContext();
</script>

{#if ctx.confirmCancel}
  <div class="fixed inset-0 z-50 bg-black/50 animate-fade-in" onclick={() => { ctx.confirmCancel = false; }} role="presentation" tabindex="-1"></div>
  <div class="fixed inset-0 z-50 flex items-center justify-center p-4">
    <div class="w-full max-w-sm rounded-xl border border-border bg-surface-1 shadow-xl animate-fade-in">
      <div class="flex items-center gap-3 border-b border-border px-5 py-4">
        <div class="flex h-9 w-9 items-center justify-center rounded-lg bg-error-muted">
          <Ban size={20} class="text-error" />
        </div>
        <h2 class="text-sm font-semibold text-text-primary">Cancel Run</h2>
      </div>
      <div class="px-5 py-4">
        <p class="text-sm text-text-secondary">
          This will stop the running tests, terminate the runner, and mark remaining tests as skipped.
        </p>
        <p class="mt-3 mb-1 text-2xs font-medium text-text-tertiary">
          Type <span class="font-mono text-text-primary">{ctx.runId}</span> to confirm
        </p>
        <input
          type="text"
          bind:value={ctx.cancelConfirmText}
          placeholder={ctx.runId}
          class="input input-md font-mono"
        />
      </div>
      <div class="flex justify-end gap-2 border-t border-border px-5 py-4">
        <button onclick={() => { ctx.confirmCancel = false; ctx.cancelConfirmText = ''; }} class="btn btn-sm btn-ghost">
          Keep Running
        </button>
        <button
          onclick={() => { ctx.confirmCancel = false; ctx.cancelConfirmText = ''; ctx.cancelRun(); }}
          disabled={ctx.cancelling || ctx.cancelConfirmText !== ctx.runId}
          class="btn btn-sm btn-danger"
        >
          {#if ctx.cancelling}
            <Loader2 size={14} class="animate-spin" />
          {/if}
          Cancel Run
        </button>
      </div>
    </div>
  </div>
{/if}
