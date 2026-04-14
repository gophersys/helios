<script lang="ts">
  import { AlertCircle, Copy, Send, X, ChevronDown, ChevronRight, Check } from 'lucide-svelte';
  import { fade, fly } from 'svelte/transition';
  import { overlayIn, overlayOut, modalIn, modalOut } from '$lib/utils/transitions';
  import { getErrorReporter } from '$lib/stores/error-reporter.svelte';

  const reporter = getErrorReporter();
  let detailsOpen = $state(false);
  let copied = $state(false);

  const report = $derived(reporter.current);
  const open = $derived(!!report);

  const typeBadge = $derived.by(() => {
    if (!report) return { label: '', classes: '' };
    switch (report.type) {
      case 'api':
        return { label: 'API Error', classes: 'badge badge-error' };
      case 'js':
        return { label: 'JS Error', classes: 'badge badge-warning' };
      case 'unhandled':
        return { label: 'Unhandled', classes: 'badge badge-neutral' };
    }
  });

  function dismiss(): void {
    detailsOpen = false;
    copied = false;
    reporter.dismiss();
  }

  async function send(): Promise<void> {
    await reporter.sendReport();
  }

  async function copyDetails(): Promise<void> {
    if (!report) return;
    try {
      await navigator.clipboard.writeText(JSON.stringify(report, null, 2));
      copied = true;
      setTimeout(() => (copied = false), 2000);
    } catch {
      // Fallback: select and copy won't work in all contexts, but log it
      console.warn('[error-reporter] Clipboard write failed');
    }
  }

  function handleKeydown(e: KeyboardEvent): void {
    if (e.key === 'Escape') dismiss();
  }

  function formatTimestamp(iso: string): string {
    try {
      const d = new Date(iso);
      return d.toLocaleString();
    } catch {
      return iso;
    }
  }
</script>

<svelte:window onkeydown={open ? handleKeydown : undefined} />

{#if open && report}
  <!-- Backdrop -->
  <div
    class="fixed inset-0 z-modal-backdrop bg-overlay backdrop-blur-xs"
    in:fade={overlayIn}
    out:fade={overlayOut}
    onclick={dismiss}
    role="presentation"
  ></div>

  <!-- Modal -->
  <div
    class="fixed inset-0 z-modal flex items-center justify-center p-4 pointer-events-none"
    role="dialog"
    aria-modal="true"
    aria-labelledby="error-report-title"
  >
    <div
      class="pointer-events-auto w-full max-w-lg rounded-xl border border-error/30 bg-surface-1 shadow-2xl overflow-hidden"
      in:fly={modalIn}
      out:fly={modalOut}
      onclick={(e) => e.stopPropagation()}
      role="document"
    >
      <!-- Header -->
      <div class="flex items-center justify-between border-b border-error/20 bg-error-muted px-5 py-4">
        <div class="flex items-center gap-3">
          <div class="flex h-9 w-9 items-center justify-center rounded-lg bg-error/15">
            <AlertCircle size={20} class="text-error" strokeWidth={1.75} />
          </div>
          <div>
            <h2 id="error-report-title" class="text-sm font-semibold text-text-primary">
              Something went wrong
            </h2>
            <span class={typeBadge.classes + ' mt-0.5'}>{typeBadge.label}</span>
          </div>
        </div>
        <button
          onclick={dismiss}
          class="flex h-8 w-8 items-center justify-center rounded-lg text-text-tertiary hover:bg-surface-2 hover:text-text-primary transition-colors"
          aria-label="Dismiss error"
        >
          <X size={20} strokeWidth={1.75} />
        </button>
      </div>

      <!-- Body -->
      <div class="p-5 max-h-[70vh] overflow-y-auto space-y-4">
        <!-- Main message -->
        <p class="text-sm font-medium text-text-primary leading-relaxed">{report.message}</p>

        <!-- Status + endpoint (API errors) -->
        {#if report.type === 'api' && report.status}
          <div class="flex items-center gap-2 text-xs text-text-secondary">
            <span class="badge badge-error">{report.status}</span>
            <span class="font-mono text-2xs text-text-tertiary truncate">
              {report.method || 'GET'} {report.url}
            </span>
          </div>
        {/if}

        <!-- Collapsible details -->
        <button
          onclick={() => (detailsOpen = !detailsOpen)}
          class="flex items-center gap-1.5 text-xs font-medium text-text-secondary hover:text-text-primary transition-colors"
        >
          {#if detailsOpen}
            <ChevronDown size={14} />
          {:else}
            <ChevronRight size={14} />
          {/if}
          Details
        </button>

        {#if detailsOpen}
          <div class="space-y-3 text-xs">
            <!-- Stack trace -->
            {#if report.stack}
              <div>
                <div class="mb-1 text-2xs font-medium uppercase tracking-wider text-text-tertiary">Stack trace</div>
                <pre class="max-h-[200px] overflow-auto rounded-lg border border-border bg-surface-0 p-3 font-mono text-2xs text-text-secondary whitespace-pre-wrap">{report.stack}</pre>
              </div>
            {/if}

            <!-- Request body -->
            {#if report.requestBody}
              <div>
                <div class="mb-1 text-2xs font-medium uppercase tracking-wider text-text-tertiary">Request body</div>
                <pre class="max-h-[120px] overflow-auto rounded-lg border border-border bg-surface-0 p-3 font-mono text-2xs text-text-secondary whitespace-pre-wrap">{report.requestBody}</pre>
              </div>
            {/if}

            <!-- Response body -->
            {#if report.responseBody}
              <div>
                <div class="mb-1 text-2xs font-medium uppercase tracking-wider text-text-tertiary">Response body</div>
                <pre class="max-h-[120px] overflow-auto rounded-lg border border-border bg-surface-0 p-3 font-mono text-2xs text-text-secondary whitespace-pre-wrap">{report.responseBody}</pre>
              </div>
            {/if}

            <!-- Metadata -->
            <div class="grid grid-cols-2 gap-2 rounded-lg border border-border bg-surface-0 p-3">
              <div>
                <div class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">Timestamp</div>
                <div class="text-xs text-text-secondary">{formatTimestamp(report.timestamp)}</div>
              </div>
              <div>
                <div class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">Page</div>
                <div class="font-mono text-2xs text-text-secondary">{report.currentPath}</div>
              </div>
              <div class="col-span-2">
                <div class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">Report ID</div>
                <div class="font-mono text-2xs text-text-tertiary">{report.id}</div>
              </div>
            </div>
          </div>
        {/if}
      </div>

      <!-- Footer -->
      <div class="flex items-center justify-between border-t border-border px-5 py-4">
        <button onclick={copyDetails} class="btn btn-sm btn-ghost flex items-center gap-1.5">
          {#if copied}
            <Check size={14} />
            Copied
          {:else}
            <Copy size={14} />
            Copy Details
          {/if}
        </button>

        <div class="flex items-center gap-2">
          <button onclick={dismiss} class="btn btn-sm btn-ghost">Dismiss</button>
          {#if reporter.reportSent}
            <span class="flex items-center gap-1.5 text-xs font-medium text-success">
              <Check size={14} />
              Report sent
            </span>
          {:else}
            <button onclick={send} class="btn btn-sm btn-primary flex items-center gap-1.5">
              <Send size={14} />
              Send Report
            </button>
          {/if}
        </div>
      </div>
    </div>
  </div>
{/if}
