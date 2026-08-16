<script lang="ts">
  import { AlertCircle, AlertTriangle, Ban } from 'lucide-svelte';
  import type { TestRun } from '$lib/types/models';
  import { deriveRunErrorBanner } from './run-error-banner';

  /**
   * P2.3 — top-of-run banner that surfaces the run's failure reason.
   *
   * Renders only when `deriveRunErrorBanner(run)` decides it should
   * (FAILED with errorMessage, FAILED with all-skipped pathology,
   * or CANCELLED with a note). All visibility / classification logic
   * lives in the pure-TS sibling so it is unit-testable; this file is
   * a thin renderer.
   *
   * Pinned by run-error-banner.test.ts (15 tests). Visual rendering
   * verified in dev via the local app.
   */

  let { run }: { run: TestRun | null | undefined } = $props();

  const banner = $derived(deriveRunErrorBanner(run));
</script>

{#if banner.visible}
  <div
    role="alert"
    class="mb-2 flex items-start gap-3 rounded-lg border px-4 py-3
           {banner.variant === 'all-skipped'
             ? 'border-warning/40 bg-warning-muted'
             : banner.variant === 'cancelled'
               ? 'border-text-tertiary/30 bg-surface-2'
               : 'border-error/40 bg-error-muted'}"
  >
    {#if banner.variant === 'all-skipped'}
      <AlertTriangle size={20} class="mt-0.5 shrink-0 text-warning" strokeWidth={1.75} />
    {:else if banner.variant === 'cancelled'}
      <Ban size={20} class="mt-0.5 shrink-0 text-text-tertiary" strokeWidth={1.75} />
    {:else}
      <AlertCircle size={20} class="mt-0.5 shrink-0 text-error" strokeWidth={1.75} />
    {/if}

    <div class="flex-1 min-w-0">
      <p
        class="text-sm font-semibold
               {banner.variant === 'all-skipped'
                 ? 'text-warning'
                 : banner.variant === 'cancelled'
                   ? 'text-text-secondary'
                   : 'text-error'}"
      >
        {banner.headline}
      </p>
      <p class="mt-1 text-sm text-text-secondary whitespace-pre-wrap break-words">
        {banner.detail}
      </p>
    </div>
  </div>
{/if}
