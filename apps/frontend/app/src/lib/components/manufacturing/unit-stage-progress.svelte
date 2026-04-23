<script lang="ts">
  import { CheckCircle2, XCircle, Loader2 } from 'lucide-svelte';
  import type { TestExecution } from '$lib/types/models';

  let { executions }: { executions: TestExecution[] } = $props();

  /** Extract a short display label from an execution name. */
  function displayLabel(name: string): string {
    // Strip common prefixes like "test_", "step_", module paths
    const short = name.replace(/^(test_|step_)/, '').split('::').pop() || name;
    // Title-case and truncate
    return short.length > 16 ? short.slice(0, 14) + '\u2026' : short;
  }
</script>

{#if executions.length === 0}
  <div class="flex items-center gap-1">
    <div class="flex items-center gap-1 rounded px-1.5 py-0.5 text-2xs font-medium bg-surface-2 text-text-tertiary">
      Waiting...
    </div>
  </div>
{:else}
  <div class="flex items-center gap-1 flex-wrap">
    {#each executions as exec, i (exec.id)}
      {#if i > 0}
        <div class="w-3 h-px {exec.status === 'PENDING' ? 'bg-border' : exec.status === 'PASSED' ? 'bg-success' : exec.status === 'FAILED' || exec.status === 'ERROR' ? 'bg-error' : 'bg-accent'}"></div>
      {/if}
      <div
        class="flex items-center gap-1 rounded px-1.5 py-0.5 text-2xs font-medium
          {exec.status === 'PASSED' ? 'bg-success-muted text-success' :
           exec.status === 'FAILED' || exec.status === 'ERROR' ? 'bg-error-muted text-error' :
           exec.status === 'RUNNING' ? 'bg-accent-muted text-accent' :
           'bg-surface-2 text-text-tertiary'}"
        title={exec.errorMessage || exec.name}
      >
        {#if exec.status === 'RUNNING'}
          <Loader2 size={10} class="animate-spin" />
        {:else if exec.status === 'PASSED'}
          <CheckCircle2 size={10} />
        {:else if exec.status === 'FAILED' || exec.status === 'ERROR'}
          <XCircle size={10} />
        {/if}
        {displayLabel(exec.name)}
      </div>
    {/each}
  </div>
{/if}
