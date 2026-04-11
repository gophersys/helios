<script lang="ts">
  import type { AuditEntry } from '$lib/types/models';
  import { formatTimeAgo } from '$lib/utils/formatting';
  import { Loader2 } from 'lucide-svelte';

  let { entries, loading }: { entries: AuditEntry[]; loading: boolean } = $props();

  function getVerbPastTense(verb: string): string {
    const map: Record<string, string> = {
      create: 'created',
      update: 'updated',
      delete: 'deleted',
      deactivate: 'deactivated',
      register: 'registered',
      unregister: 'unregistered',
      upload: 'uploaded',
      trigger: 'triggered',
      cancel: 'cancelled',
      complete: 'completed',
      assign: 'assigned',
      unassign: 'unassigned',
      deploy: 'deployed',
      undeploy: 'undeployed',
      lock: 'locked',
      unlock: 'unlocked',
      login: 'logged in',
      promote: 'promoted',
      schedule: 'scheduled',
      sync: 'synced',
      start: 'started',
      end: 'ended',
      rerun: 'reran',
      retrigger: 'retriggered',
      reset: 'reset',
      cleanup: 'cleaned up',
    };
    return map[verb] || verb;
  }

  function formatAction(action: string): { verb: string; entity: string } {
    const parts = action.split('.');
    if (parts.length >= 2) {
      const verb = parts[parts.length - 1];
      const entity = parts.slice(0, -1).join(' ');
      return { verb: getVerbPastTense(verb), entity };
    }
    return { verb: action, entity: '' };
  }

  function getActionColor(action: string): string {
    if (action.includes('create') || action.includes('register')) return 'text-success';
    if (action.includes('delete') || action.includes('deactivate') || action.includes('cleanup')) return 'text-error';
    if (action.includes('login')) return 'text-accent';
    return 'text-text-primary';
  }
</script>

<div>
  <h2 class="text-sm font-semibold text-text-primary mb-3">Recent Activity</h2>

  <div class="rounded-lg border border-border bg-surface-1">
    {#if loading}
      <div class="flex items-center justify-center px-4 py-6">
        <Loader2 size={18} class="animate-spin text-text-tertiary" />
      </div>
    {:else if entries.length === 0}
      <div class="px-4 py-6 text-center">
        <p class="text-sm text-text-tertiary">No recent activity</p>
      </div>
    {:else}
      {#each entries as entry (entry.id)}
        {@const { verb, entity } = formatAction(entry.action)}
        <div class="px-4 py-2.5 border-b border-border-subtle last:border-0 flex items-center gap-3">
          <span class="text-sm text-text-secondary truncate">
            {entry.user?.name ?? 'System'}
          </span>
          <span class="text-sm {getActionColor(entry.action)}">{verb}</span>
          {#if entity}
            <span class="badge badge-neutral">{entity}</span>
          {/if}
          <span class="ml-auto shrink-0 text-2xs text-text-tertiary">
            {formatTimeAgo(entry.createdAt)}
          </span>
        </div>
      {/each}
      <a
        href="/history"
        class="block px-4 py-2.5 text-center text-2xs text-accent hover:text-accent-hover border-t border-border-subtle"
      >
        View all activity →
      </a>
    {/if}
  </div>
</div>
