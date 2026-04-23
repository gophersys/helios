<script lang="ts">
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import type { TestPackageSummary } from '$lib/types/models';

  interface Props {
    status: TestPackageSummary | null;
    type: 'VALIDATION' | 'MANUFACTURING';
  }

  let { status, type }: Props = $props();

  const label = $derived(type === 'MANUFACTURING' ? 'Manufacturing' : 'Validation');

  const timeAgo = $derived.by(() => {
    if (!status?.updatedAt) return '';
    const diff = Date.now() - new Date(status.updatedAt).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
  });
</script>

{#if !status}
  <!-- No package uploaded -->
  <div class="mb-4 rounded-lg border border-dashed border-warning bg-warning-muted/30 p-4">
    <div class="flex items-start gap-3">
      <div class="mt-0.5 text-warning">
        <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
        </svg>
      </div>
      <div>
        <p class="text-sm font-medium text-text-primary">No {label.toLowerCase()} test app uploaded</p>
        <p class="mt-1 text-2xs text-text-secondary">
          Upload a test package from your development machine:
          <code class="ml-1 rounded bg-surface-2 px-1.5 py-0.5 font-mono text-2xs text-text-primary">corectl test upload</code>
        </p>
      </div>
    </div>
  </div>
{:else}
  <!-- Package exists -->
  <div class="mb-4 rounded-lg border border-border bg-surface-1 p-4">
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-3">
        <div class="mt-0.5 {status.status === 'RELEASED' ? 'text-success' : 'text-warning'}">
          <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            {#if status.status === 'RELEASED'}
              <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            {:else}
              <path stroke-linecap="round" stroke-linejoin="round" d="M20.25 7.5l-.625 10.632a2.25 2.25 0 01-2.247 2.118H6.622a2.25 2.25 0 01-2.247-2.118L3.75 7.5m8.25 3v6.75m0 0l-3-3m3 3l3-3M3.375 7.5h17.25c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125z" />
            {/if}
          </svg>
        </div>
        <div>
          <div class="flex items-center gap-2">
            <span class="text-sm font-medium text-text-primary">{label} Test App</span>
            <code class="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-2xs text-text-primary">{status.version}</code>
            <StatusBadge status={status.status} />
          </div>
          <p class="mt-0.5 text-2xs text-text-tertiary">
            {status.testCount} test{status.testCount !== 1 ? 's' : ''}
            {#if status.gitSha}
              &middot; <code class="font-mono">{status.gitSha}{status.gitDirty ? '*' : ''}</code>
            {/if}
            {#if timeAgo}
              &middot; {timeAgo}
            {/if}
          </p>
          {#if status.message}
            <p class="mt-0.5 text-2xs text-text-secondary italic">{status.message}</p>
          {/if}
        </div>
      </div>
    </div>
  </div>
{/if}
