<script lang="ts">
  import { Ban, Loader2 } from 'lucide-svelte';
  import { getRunContext } from './run-context.svelte';

  const ctx = getRunContext();
</script>

{#if ctx.confirmCancel}
  <div class="fixed inset-0 z-50 bg-black/50 animate-fade-in" onclick={() => { ctx.confirmCancel = false; }} role="presentation" tabindex="-1"></div>
  <div class="fixed inset-0 z-50 flex items-center justify-center p-4">
    <div class="w-full max-w-sm rounded-xl border border-border bg-surface-1 shadow-xl animate-fade-in">
      <div class="flex items-center gap-3 border-b border-border px-5 py-4">
        <div class="flex h-9 w-9 items-center justify-center rounded-lg bg-error-muted">
          <Ban size={20} class="text-error" />
        </div>
        <h2 class="text-sm font-semibold text-text-primary">Cancel Validation Run</h2>
      </div>
      <div class="px-5 py-4">
        <p class="text-sm text-text-secondary">
          This will stop the running tests, kill the K8s job, and unlock the fixture. You can re-run from the builds page.
        </p>
        <p class="mt-3 mb-1 text-2xs font-medium text-text-tertiary">
          Type <span class="font-mono text-text-primary">{ctx.runId}</span> to confirm
        </p>
        <input
          type="text"
          bind:value={ctx.cancelConfirmText}
          placeholder={ctx.runId}
          class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none font-mono"
        />
      </div>
      <div class="flex justify-end gap-2 border-t border-border px-5 py-4">
        <button onclick={() => { ctx.confirmCancel = false; ctx.cancelConfirmText = ''; }} class="rounded-lg px-4 py-2 text-sm font-medium text-text-secondary hover:bg-surface-2">
          Keep Running
        </button>
        <button
          onclick={() => { ctx.confirmCancel = false; ctx.cancelConfirmText = ''; ctx.cancelRun(); }}
          disabled={ctx.cancelling || ctx.cancelConfirmText !== ctx.runId}
          class="rounded-lg bg-error px-4 py-2 text-sm font-medium text-white hover:bg-error/90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
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
