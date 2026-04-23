<script lang="ts">
  import { fade, fly } from 'svelte/transition';
  import { Check, Info, X, AlertTriangle } from 'lucide-svelte';
  import { toasts } from '$lib/stores/toast.svelte';

  const ICON = {
    info: Info,
    success: Check,
    error: AlertTriangle,
  } as const;

  const COLOR = {
    info: 'bg-info-muted text-info border-info/30',
    success: 'bg-success-muted text-success border-success/30',
    error: 'bg-error-muted text-error border-error/30',
  } as const;
</script>

<div class="fixed top-4 right-4 z-[100] flex flex-col gap-2 pointer-events-none">
  {#each toasts.toasts as toast (toast.id)}
    {@const Icon = ICON[toast.kind]}
    <div
      in:fly={{ y: -8, duration: 150 }}
      out:fade={{ duration: 150 }}
      class="pointer-events-auto flex items-center gap-2 rounded-lg border px-3 py-2 shadow-elevated {COLOR[toast.kind]}"
    >
      <Icon size={14} />
      <span class="text-sm font-medium">{toast.message}</span>
      <button
        onclick={() => toasts.dismiss(toast.id)}
        class="ml-2 rounded p-0.5 hover:bg-surface-2/40"
        aria-label="Dismiss notification"
      >
        <X size={12} />
      </button>
    </div>
  {/each}
</div>
