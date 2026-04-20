<script lang="ts">
  import { X, Loader2 } from 'lucide-svelte';
  import type { Snippet } from 'svelte';

  interface Action {
    label: string;
    icon?: typeof X;
    variant?: 'primary' | 'danger' | 'ghost';
    disabled?: boolean;
    loading?: boolean;
    onclick: () => void;
  }

  let {
    selectedCount,
    totalCount,
    onSelectAll,
    onClearSelection,
    actions = [],
  }: {
    selectedCount: number;
    totalCount: number;
    onSelectAll: () => void;
    onClearSelection: () => void;
    actions: Action[];
  } = $props();

  const allSelected = $derived(selectedCount > 0 && selectedCount === totalCount);
  const someSelected = $derived(selectedCount > 0 && selectedCount < totalCount);
</script>

{#if selectedCount > 0}
  <div class="sticky top-0 z-10 flex items-center gap-3 rounded-lg border border-accent/30 bg-accent-muted px-4 py-2.5 mb-3">
    <!-- Select all / clear -->
    <label class="flex items-center gap-2 cursor-pointer">
      <input
        type="checkbox"
        checked={allSelected}
        indeterminate={someSelected}
        onchange={() => allSelected ? onClearSelection() : onSelectAll()}
        class="h-4 w-4 rounded border-border text-accent focus:ring-accent"
      />
    </label>

    <span class="text-sm font-medium text-text-primary">
      {selectedCount} selected
    </span>

    <button
      onclick={onClearSelection}
      class="text-2xs text-text-tertiary hover:text-text-secondary"
    >
      Clear
    </button>

    <div class="ml-auto flex items-center gap-2">
      {#each actions as action}
        {@const variant = action.variant ?? 'ghost'}
        {@const ActionIcon = action.icon}
        <button
          onclick={action.onclick}
          disabled={action.disabled || action.loading}
          class="btn btn-sm {variant === 'danger' ? 'btn-danger' : variant === 'primary' ? 'btn-primary' : 'btn-ghost'}"
        >
          {#if action.loading}
            <Loader2 size={14} class="animate-spin" />
          {:else if ActionIcon}
            <ActionIcon size={14} />
          {/if}
          {action.label}
        </button>
      {/each}
    </div>
  </div>
{/if}
