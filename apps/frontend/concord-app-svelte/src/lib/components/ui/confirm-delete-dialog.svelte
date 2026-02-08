<script lang="ts">
  import { AlertTriangle, X } from 'lucide-svelte';

  let {
    open,
    entityType,
    entityName,
    onConfirm,
    onCancel
  }: {
    open: boolean;
    entityType: string;
    entityName: string;
    onConfirm: () => void;
    onCancel: () => void;
  } = $props();

  let confirmText = $state('');

  const canConfirm = $derived(confirmText === entityName);

  $effect(() => {
    if (!open) confirmText = '';
  });

  function handleConfirm(): void {
    if (canConfirm) {
      onConfirm();
      confirmText = '';
    }
  }

  function handleCancel(): void {
    confirmText = '';
    onCancel();
  }

  function handleKeydown(e: KeyboardEvent): void {
    if (e.key === 'Escape') {
      handleCancel();
    } else if (e.key === 'Enter' && canConfirm) {
      handleConfirm();
    }
  }
</script>

{#if open}
  <!-- Overlay -->
  <div
    class="fixed inset-0 z-50 bg-overlay animate-overlay-in"
    onclick={handleCancel}
    onkeydown={handleKeydown}
    role="button"
    tabindex="-1"
  ></div>

  <!-- Dialog -->
  <div class="fixed inset-0 z-50 flex items-center justify-center p-4">
    <div
      class="w-full max-w-md animate-modal-in rounded-xl border border-border bg-surface-1 shadow-xl"
      role="dialog"
      aria-modal="true"
      aria-labelledby="delete-dialog-title"
    >
      <div class="flex items-center justify-between border-b border-border px-5 py-4">
        <div class="flex items-center gap-3">
          <div class="flex h-9 w-9 items-center justify-center rounded-lg bg-error-muted">
            <AlertTriangle size={20} class="text-error" strokeWidth={1.75} />
          </div>
          <h2 id="delete-dialog-title" class="text-sm font-semibold text-text-primary">
            Delete {entityType}
          </h2>
        </div>
        <button
          onclick={handleCancel}
          class="flex h-8 w-8 items-center justify-center rounded-lg text-text-tertiary hover:bg-surface-2 hover:text-text-primary"
          title="Cancel"
          aria-label="Cancel deletion"
        >
          <X size={20} strokeWidth={1.75} />
        </button>
      </div>

      <div class="p-5">
        <p class="mb-4 text-sm text-text-secondary">
          This action cannot be undone. This will permanently delete the {entityType}
          <strong class="text-text-primary">{entityName}</strong> and all associated data.
        </p>

        <label for="confirm-delete-input" class="mb-1 block text-2xs font-medium text-text-tertiary">
          Type <span class="font-mono text-text-primary">{entityName}</span> to confirm
        </label>
        <!-- svelte-ignore a11y_autofocus -->
        <input
          id="confirm-delete-input"
          type="text"
          bind:value={confirmText}
          onkeydown={handleKeydown}
          placeholder={entityName}
          class="w-full rounded-lg border border-border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
          autofocus
        />
      </div>

      <div class="flex justify-end gap-2 border-t border-border px-5 py-4">
        <button
          onclick={handleCancel}
          class="rounded-lg px-4 py-2 text-sm font-medium text-text-secondary hover:bg-surface-2"
        >
          Cancel
        </button>
        <button
          onclick={handleConfirm}
          disabled={!canConfirm}
          class="rounded-lg bg-error px-4 py-2 text-sm font-medium text-white hover:bg-error-hover disabled:cursor-not-allowed disabled:opacity-50"
        >
          Delete
        </button>
      </div>
    </div>
  </div>
{/if}
