<script lang="ts">
  import { GitBranch, Pencil, Trash2, ExternalLink } from 'lucide-svelte';
  import StatusBadge from '$lib/components/ui/status-badge.svelte';
  import { isSafeUrl } from '$lib/utils/url';
  import type { Codebase } from '$lib/types/models';

  interface Props {
    codebase: Codebase;
    canManage: boolean;
    onEdit: (c: Codebase) => void;
    onDelete: (id: string) => void;
    onSelect: (c: Codebase) => void;
  }

  let { codebase, canManage, onEdit, onDelete, onSelect }: Props = $props();
</script>

<div
  role="button"
  tabindex="0"
  onclick={() => onSelect(codebase)}
  onkeydown={(e) => e.key === 'Enter' && onSelect(codebase)}
  class="card card-interactive group relative flex flex-col overflow-hidden"
>
  <!-- Hero image -->
  <div class="flex h-36 items-center justify-center bg-surface-2">
    {#if codebase.imageUrl}
      <img
        src={codebase.imageUrl}
        alt={codebase.name}
        class="h-full w-full object-contain p-3"
      />
    {:else}
      <GitBranch size={32} strokeWidth={1} class="text-text-tertiary opacity-40" />
    {/if}
  </div>

  <!-- Body -->
  <div class="flex flex-1 flex-col p-3.5">
    <div class="mb-1 flex items-center gap-2">
      <h3 class="truncate text-sm font-semibold text-text-primary">
        {codebase.name}
      </h3>
    </div>
    {#if codebase.description}
      <p class="mb-2 text-2xs text-text-tertiary line-clamp-2">
        {codebase.description}
      </p>
    {/if}

    {#if codebase.repoUrl && isSafeUrl(codebase.repoUrl)}
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <div class="mb-2" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()}>
        <a
          href={codebase.repoUrl}
          target="_blank"
          rel="noopener noreferrer"
          class="inline-flex items-center gap-1 text-2xs text-accent hover:underline"
        >
          <ExternalLink size={12} />
          Repository
        </a>
      </div>
    {/if}

    <!-- Latest release badge -->
    <div class="mt-auto">
      {#if codebase.latestRelease}
        <div class="flex items-center gap-2">
          <span class="text-2xs font-medium text-text-secondary">
            {codebase.latestRelease.version}
          </span>
          <StatusBadge status={codebase.latestRelease.status} />
        </div>
      {:else}
        <div class="text-2xs text-text-tertiary">
          {codebase.releaseCount > 0
            ? `${codebase.releaseCount} release${codebase.releaseCount > 1 ? 's' : ''}`
            : 'No releases'}
        </div>
      {/if}
    </div>
  </div>

  <!-- Edit/delete -->
  {#if canManage}
    <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
    <div
      role="group"
      class="absolute right-2 top-2 flex gap-1 opacity-0 transition-opacity group-hover:opacity-100"
      onclick={(e) => e.stopPropagation()}
      onkeydown={(e) => e.stopPropagation()}
    >
      <button
        onclick={() => onEdit(codebase)}
        class="rounded-lg bg-surface-1/90 p-1.5 text-text-tertiary shadow-sm backdrop-blur hover:text-text-primary"
        title="Edit"
        aria-label="Edit"
      >
        <Pencil size={16} />
      </button>
      <button
        onclick={() => onDelete(codebase.id)}
        class="rounded-lg bg-surface-1/90 p-1.5 text-text-tertiary shadow-sm backdrop-blur hover:text-error"
        title="Delete"
        aria-label="Delete"
      >
        <Trash2 size={16} />
      </button>
    </div>
  {/if}
</div>
