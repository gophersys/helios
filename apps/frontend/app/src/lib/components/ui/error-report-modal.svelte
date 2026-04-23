<script lang="ts">
  import {
    AlertCircle, AlertTriangle, Info, ShieldAlert,
    Copy, Send, X, ChevronDown, ChevronRight, Check,
    Clock, Globe, Monitor, User, Activity, Wifi, WifiOff,
    MessageSquare,
  } from 'lucide-svelte';
  import { fade, fly } from 'svelte/transition';
  import { overlayIn, overlayOut, modalIn, modalOut } from '$lib/utils/transitions';
  import { getErrorReporter, type ErrorSeverity, type ErrorReport } from '$lib/stores/error-reporter.svelte';

  const reporter = getErrorReporter();
  let detailsOpen = $state(false);
  let breadcrumbsOpen = $state(false);
  let copied = $state(false);
  let userNotes = $state('');
  let dismissLocked = $state(false);
  let lockCountdown = $state(0);
  let lockTimer: ReturnType<typeof setInterval> | undefined;

  const report = $derived(reporter.current);
  const open = $derived(!!report);

  $effect(() => {
    if (open && report?.type !== 'user_report') {
      dismissLocked = true;
      lockCountdown = 5;
      lockTimer = setInterval(() => {
        lockCountdown--;
        if (lockCountdown <= 0) {
          dismissLocked = false;
          clearInterval(lockTimer);
        }
      }, 1000);
    }
    return () => { if (lockTimer) clearInterval(lockTimer); };
  });

  const severityConfig = $derived.by(() => {
    if (!report) return { icon: AlertCircle, label: '', classes: '', headerBg: '' };
    const map: Record<ErrorSeverity, { icon: typeof AlertCircle; label: string; classes: string; headerBg: string }> = {
      critical: { icon: ShieldAlert, label: 'Critical', classes: 'badge badge-error', headerBg: 'bg-error-muted border-error/20' },
      error: { icon: AlertCircle, label: 'Error', classes: 'badge badge-error', headerBg: 'bg-error-muted border-error/20' },
      warning: { icon: AlertTriangle, label: 'Warning', classes: 'badge badge-warning', headerBg: 'bg-warning-muted border-warning/20' },
      info: { icon: Info, label: 'Info', classes: 'badge badge-info', headerBg: 'bg-accent-muted border-accent/20' },
    };
    return map[report.severity] ?? map.error;
  });

  const typeBadge = $derived.by(() => {
    if (!report) return { label: '', classes: '' };
    const map: Record<string, { label: string; classes: string }> = {
      api: { label: 'API', classes: 'badge badge-error' },
      js: { label: 'JS', classes: 'badge badge-warning' },
      websocket: { label: 'WebSocket', classes: 'badge badge-accent' },
      validation: { label: 'Validation', classes: 'badge badge-warning' },
      unhandled: { label: 'Unhandled', classes: 'badge badge-neutral' },
      user_report: { label: 'Bug Report', classes: 'badge badge-info' },
    };
    return map[report.type] ?? { label: report.type, classes: 'badge badge-neutral' };
  });

  function dismiss(): void {
    if (dismissLocked) return;
    detailsOpen = false;
    breadcrumbsOpen = false;
    copied = false;
    userNotes = '';
    dismissLocked = false;
    if (lockTimer) clearInterval(lockTimer);
    reporter.dismiss();
  }

  async function send(): Promise<void> {
    if (userNotes.trim() && report) {
      report.userNotes = userNotes.trim();
    }
    await reporter.sendReport();
  }

  async function copyDetails(): Promise<void> {
    if (!report) return;
    try {
      await navigator.clipboard.writeText(JSON.stringify(report, null, 2));
      copied = true;
      setTimeout(() => (copied = false), 2000);
    } catch {
      console.warn('[error-reporter] Clipboard write failed');
    }
  }

  function handleKeydown(e: KeyboardEvent): void {
    if (e.key === 'Escape' && !dismissLocked) dismiss();
  }

  function formatTimestamp(iso: string): string {
    try {
      return new Date(iso).toLocaleString();
    } catch {
      return iso;
    }
  }

  function formatDuration(ms: number | undefined): string {
    if (ms === undefined) return '';
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
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
    <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
    <div
      class="pointer-events-auto w-full max-w-lg rounded-xl border bg-surface-1 shadow-2xl overflow-hidden {severityConfig.headerBg.includes('error') ? 'border-error/30' : severityConfig.headerBg.includes('warning') ? 'border-warning/30' : 'border-accent/30'}"
      in:fly={modalIn}
      out:fly={modalOut}
      onclick={(e) => e.stopPropagation()}
      onkeydown={(e) => { if (e.key === 'Escape') e.stopPropagation(); }}
      role="document"
    >
      <!-- Header -->
      <div class="flex items-center justify-between border-b {severityConfig.headerBg} px-5 py-4">
        <div class="flex items-center gap-3">
          <div class="flex h-9 w-9 items-center justify-center rounded-lg {report.severity === 'critical' || report.severity === 'error' ? 'bg-error/15' : report.severity === 'warning' ? 'bg-warning/15' : 'bg-accent/15'}">
            <severityConfig.icon size={20} class={report.severity === 'critical' || report.severity === 'error' ? 'text-error' : report.severity === 'warning' ? 'text-warning' : 'text-accent'} strokeWidth={1.75} />
          </div>
          <div>
            <h2 id="error-report-title" class="text-sm font-semibold text-text-primary">
              {report.type === 'user_report' ? 'Bug Report' : 'Something went wrong'}
            </h2>
            <div class="mt-0.5 flex items-center gap-1.5">
              <span class={severityConfig.classes}>{severityConfig.label}</span>
              <span class={typeBadge.classes}>{typeBadge.label}</span>
            </div>
          </div>
        </div>
        <button
          onclick={dismiss}
          disabled={dismissLocked}
          class="flex h-8 w-8 items-center justify-center rounded-lg transition-colors {dismissLocked ? 'text-text-tertiary/40 cursor-not-allowed' : 'text-text-tertiary hover:bg-surface-2 hover:text-text-primary'}"
          aria-label="Dismiss"
        >
          {#if dismissLocked}
            <span class="text-2xs font-bold tabular-nums">{lockCountdown}</span>
          {:else}
            <X size={20} strokeWidth={1.75} />
          {/if}
        </button>
      </div>

      <!-- Body -->
      <div class="p-5 max-h-[70vh] overflow-y-auto space-y-4">
        <!-- Main message -->
        <p class="text-sm font-medium text-text-primary leading-relaxed">{report.message}</p>

        {#if report.details && report.details !== report.message}
          <p class="text-xs text-text-secondary">{report.details}</p>
        {/if}

        <!-- API context -->
        {#if report.type === 'api' && report.status}
          <div class="flex items-center gap-2 text-xs text-text-secondary">
            <span class="badge {report.status >= 500 ? 'badge-error' : 'badge-warning'}">{report.status}</span>
            <span class="font-mono text-2xs text-text-tertiary truncate">
              {report.method || 'GET'} {report.url}
            </span>
            {#if report.requestDurationMs}
              <span class="ml-auto flex items-center gap-1 text-2xs text-text-tertiary">
                <Clock size={10} />
                {formatDuration(report.requestDurationMs)}
              </span>
            {/if}
          </div>
        {/if}

        <!-- WebSocket context -->
        {#if report.type === 'websocket'}
          <div class="flex items-center gap-2 text-xs text-text-secondary">
            {#if report.wsNamespace}
              <span class="font-mono text-2xs text-text-tertiary">ns: {report.wsNamespace}</span>
            {/if}
            {#if report.wsEvent}
              <span class="font-mono text-2xs text-text-tertiary">event: {report.wsEvent}</span>
            {/if}
          </div>
        {/if}

        <!-- Action context -->
        {#if report.action || report.entityType}
          <div class="rounded-lg border border-border bg-surface-0 p-3 space-y-1.5">
            {#if report.action}
              <div class="flex items-center gap-2">
                <Activity size={12} class="text-text-tertiary shrink-0" />
                <span class="text-xs text-text-secondary">Action: <span class="font-medium text-text-primary">{report.action}</span></span>
              </div>
            {/if}
            {#if report.entityType}
              <div class="text-xs text-text-secondary">
                Entity: <span class="font-medium">{report.entityType}</span>
                {#if report.entityId}
                  <span class="font-mono text-2xs text-text-tertiary ml-1">{report.entityId}</span>
                {/if}
              </div>
            {/if}
            {#if report.relatedEntities && Object.keys(report.relatedEntities).length > 0}
              <div class="flex flex-wrap gap-2">
                {#each Object.entries(report.relatedEntities) as [key, value]}
                  <span class="text-2xs text-text-tertiary">
                    {key}: <span class="font-mono">{value}</span>
                  </span>
                {/each}
              </div>
            {/if}
          </div>
        {/if}

        <!-- User notes input (for user_report or adding context) -->
        {#if report.type === 'user_report' || !reporter.reportSent}
          <div>
            <label for="error-user-notes" class="text-2xs font-medium uppercase tracking-wider text-text-tertiary mb-1 block">
              What were you trying to do?
            </label>
            <textarea
              id="error-user-notes"
              bind:value={userNotes}
              placeholder="Describe the steps that led to this..."
              rows="2"
              class="input input-sm w-full resize-none text-xs"
            ></textarea>
          </div>
        {/if}

        <!-- Collapsible: recent actions / breadcrumbs -->
        {#if report.recentActions && report.recentActions.length > 0}
          <button
            onclick={() => (breadcrumbsOpen = !breadcrumbsOpen)}
            class="flex items-center gap-1.5 text-xs font-medium text-text-secondary hover:text-text-primary transition-colors"
          >
            {#if breadcrumbsOpen}
              <ChevronDown size={14} />
            {:else}
              <ChevronRight size={14} />
            {/if}
            Recent Actions ({report.recentActions.length})
          </button>

          {#if breadcrumbsOpen}
            <div class="rounded-lg border border-border bg-surface-0 p-3 max-h-[140px] overflow-y-auto">
              {#each report.recentActions as action, i}
                <div class="flex items-start gap-2 py-0.5 {i > 0 ? 'border-t border-border-subtle' : ''}">
                  <span class="text-2xs text-text-tertiary font-mono whitespace-nowrap">{action.slice(0, 12)}</span>
                  <span class="text-2xs text-text-secondary">{action.slice(13)}</span>
                </div>
              {/each}
            </div>
          {/if}
        {/if}

        <!-- Collapsible: full technical details -->
        <button
          onclick={() => (detailsOpen = !detailsOpen)}
          class="flex items-center gap-1.5 text-xs font-medium text-text-secondary hover:text-text-primary transition-colors"
        >
          {#if detailsOpen}
            <ChevronDown size={14} />
          {:else}
            <ChevronRight size={14} />
          {/if}
          Technical Details
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

            <!-- Context grid -->
            <div class="grid grid-cols-2 gap-2 rounded-lg border border-border bg-surface-0 p-3">
              <div>
                <div class="flex items-center gap-1 text-2xs font-medium uppercase tracking-wider text-text-tertiary">
                  <Clock size={10} /> Timestamp
                </div>
                <div class="text-xs text-text-secondary">{formatTimestamp(report.timestamp)}</div>
              </div>
              <div>
                <div class="flex items-center gap-1 text-2xs font-medium uppercase tracking-wider text-text-tertiary">
                  <Globe size={10} /> Page
                </div>
                <div class="font-mono text-2xs text-text-secondary">{report.currentPath}</div>
              </div>
              {#if report.previousPath}
                <div>
                  <div class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">Previous Page</div>
                  <div class="font-mono text-2xs text-text-secondary">{report.previousPath}</div>
                </div>
              {/if}
              <div>
                <div class="flex items-center gap-1 text-2xs font-medium uppercase tracking-wider text-text-tertiary">
                  <Monitor size={10} /> Screen
                </div>
                <div class="text-2xs text-text-secondary">{report.screenSize || 'unknown'}</div>
              </div>
              {#if report.userEmail}
                <div>
                  <div class="flex items-center gap-1 text-2xs font-medium uppercase tracking-wider text-text-tertiary">
                    <User size={10} /> User
                  </div>
                  <div class="text-2xs text-text-secondary">{report.userEmail}</div>
                </div>
              {/if}
              {#if report.userRole}
                <div>
                  <div class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">Role</div>
                  <div class="text-2xs text-text-secondary">{report.userRole}</div>
                </div>
              {/if}
              <div>
                <div class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">Network</div>
                <div class="flex items-center gap-1 text-2xs text-text-secondary">
                  {#if report.networkOnline}
                    <Wifi size={10} class="text-success" /> Online
                  {:else}
                    <WifiOff size={10} class="text-error" /> Offline
                  {/if}
                </div>
              </div>
              <div>
                <div class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">Environment</div>
                <div class="text-2xs text-text-secondary">{report.environment}</div>
              </div>
              <div class="col-span-2">
                <div class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">Report ID</div>
                <div class="font-mono text-2xs text-text-tertiary">{report.id}</div>
              </div>
              <div class="col-span-2">
                <div class="text-2xs font-medium uppercase tracking-wider text-text-tertiary">Version</div>
                <div class="font-mono text-2xs text-text-tertiary">{report.appVersion}</div>
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
            Copy JSON
          {/if}
        </button>

        <div class="flex items-center gap-2">
          <button onclick={dismiss} disabled={dismissLocked} class="btn btn-sm btn-ghost {dismissLocked ? 'opacity-40 cursor-not-allowed' : ''}">
            {dismissLocked ? `Dismiss (${lockCountdown})` : 'Dismiss'}
          </button>
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
