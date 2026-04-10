<script lang="ts">
  import { AlertTriangle, Loader2, X } from 'lucide-svelte';

  let {
    open,
    entityType = '',
    entityName = '',
    resourceType = '',
    resourceName = '',
    onConfirm,
    onCancel,
    loading = false,
  }: {
    open: boolean;
    /** @deprecated Use resourceType instead */
    entityType?: string;
    /** @deprecated Use resourceName instead */
    entityName?: string;
    resourceType?: string;
    resourceName?: string;
    onConfirm: () => void | Promise<void>;
    onCancel: () => void;
    loading?: boolean;
  } = $props();

  // Support both old (entityType/entityName) and new (resourceType/resourceName) prop names
  const type = $derived(resourceType || entityType);
  const name = $derived(resourceName || entityName);

  let confirmText = $state('');
  let inputEl = $state<HTMLInputElement | null>(null);

  const isMatch = $derived(confirmText === name);

  $effect(() => {
    if (!open) confirmText = '';
  });

  // Auto-focus input when dialog opens
  $effect(() => {
    if (open && inputEl) {
      inputEl.focus();
    }
  });

  function handleConfirm(): void {
    if (isMatch && !loading) {
      onConfirm();
    }
  }

  function handleCancel(): void {
    if (!loading) {
      confirmText = '';
      onCancel();
    }
  }

  function handleKeydown(e: KeyboardEvent): void {
    if (e.key === 'Escape') {
      handleCancel();
    } else if (e.key === 'Enter' && isMatch) {
      handleConfirm();
    }
  }

  function handleOverlayClick(): void {
    handleCancel();
  }
</script>

{#if open}
  <!-- Overlay -->
  <div
    class="fixed inset-0 z-modal-backdrop bg-overlay animate-overlay-in"
    onclick={handleOverlayClick}
    onkeydown={handleKeydown}
    role="presentation"
    tabindex="-1"
  ></div>

  <!-- Dialog -->
  <div class="fixed inset-0 z-modal flex items-center justify-center p-4">
    <div
      class="w-full max-w-md animate-modal-in rounded-xl border border-border bg-surface-1 shadow-xl"
      role="dialog"
      aria-modal="true"
      aria-labelledby="delete-dialog-title"
    >
      <!-- Header -->
      <div class="flex items-center justify-between border-b border-border px-5 py-4">
        <div class="flex items-center gap-3">
          <div class="flex h-9 w-9 items-center justify-center rounded-lg bg-error-muted">
            <AlertTriangle size={20} class="text-error" strokeWidth={1.75} />
          </div>
          <h2 id="delete-dialog-title" class="text-sm font-semibold text-text-primary">
            Delete {type}
          </h2>
        </div>
        <button
          onclick={handleCancel}
          disabled={loading}
          class="flex h-8 w-8 items-center justify-center rounded-lg text-text-tertiary hover:bg-surface-2 hover:text-text-primary disabled:opacity-50"
          title="Cancel"
          aria-label="Cancel deletion"
        >
          <X size={20} strokeWidth={1.75} />
        </button>
      </div>

      <!-- Body -->
      <div class="p-5">
        <p class="mb-4 text-sm text-text-secondary">
          This action cannot be undone. This will permanently delete the {type}
          <strong class="font-mono font-semibold text-text-primary">{name}</strong>
          and all associated data.
        </p>

        <label for="confirm-delete-input" class="mb-1 block text-2xs font-medium text-text-tertiary">
          Type <span class="font-mono text-text-primary">{name}</span> to confirm
        </label>
        <!-- svelte-ignore a11y_autofocus -->
        <input
          id="confirm-delete-input"
          type="text"
          bind:this={inputEl}
          bind:value={confirmText}
          onkeydown={handleKeydown}
          placeholder={name}
          disabled={loading}
          class="w-full rounded-lg border bg-surface-0 px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:outline-none disabled:opacity-50 {confirmText.length > 0 && !isMatch ? 'border-error focus:border-error' : 'border-border focus:border-accent'}"
          autofocus
        />
      </div>

      <!-- Footer -->
      <div class="flex justify-end gap-2 border-t border-border px-5 py-4">
        <button
          onclick={handleCancel}
          disabled={loading}
          class="rounded-lg px-4 py-2 text-sm font-medium text-text-secondary hover:bg-surface-2 disabled:opacity-50"
        >
          Cancel
        </button>
        <button
          onclick={handleConfirm}
          disabled={!isMatch || loading}
          class="flex items-center gap-1.5 rounded-lg bg-error px-4 py-2 text-sm font-medium text-white hover:bg-error-hover disabled:cursor-not-allowed disabled:opacity-50"
        >
          {#if loading}
            <Loader2 size={14} class="animate-spin" />
            Deleting...
          {:else}
            Delete
          {/if}
        </button>
      </div>
    </div>
  </div>
{/if}
