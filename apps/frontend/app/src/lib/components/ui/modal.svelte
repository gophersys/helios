<script lang="ts">
  import { X } from 'lucide-svelte';
  import { fade, fly } from 'svelte/transition';
  import { overlayIn, overlayOut, modalIn, modalOut } from '$lib/utils/transitions';
  import type { Snippet } from 'svelte';

  interface Props {
    open: boolean;
    title?: string;
    onclose?: () => void;
    size?: 'sm' | 'md' | 'lg' | 'xl' | 'full';
    closeOnBackdrop?: boolean;
    closeOnEscape?: boolean;
    showCloseButton?: boolean;
    header?: Snippet;
    footer?: Snippet;
    children: Snippet;
  }

  let {
    open,
    title = '',
    onclose,
    size = 'md',
    closeOnBackdrop = true,
    closeOnEscape = true,
    showCloseButton = true,
    header,
    footer,
    children
  }: Props = $props();

  function handleBackdropClick() {
    if (closeOnBackdrop && onclose) {
      onclose();
    }
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape' && closeOnEscape && onclose) {
      onclose();
    }
  }

  const sizeClasses = {
    sm: 'max-w-sm',
    md: 'max-w-md',
    lg: 'max-w-lg',
    xl: 'max-w-2xl',
    full: 'max-w-[90vw] max-h-[90vh]'
  };
</script>

<svelte:window onkeydown={handleKeydown} />

{#if open}
  <!-- Backdrop -->
  <div
    class="fixed inset-0 z-modal-backdrop bg-overlay backdrop-blur-sm"
    in:fade={overlayIn}
    out:fade={overlayOut}
    onclick={handleBackdropClick}
    role="presentation"
  ></div>

  <!-- Modal Container -->
  <div
    class="fixed inset-0 z-modal flex items-center justify-center p-4 pointer-events-none"
    role="dialog"
    aria-modal="true"
    aria-labelledby={title ? 'modal-title' : undefined}
  >
    <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <div
      class="pointer-events-auto w-full {sizeClasses[size]} rounded-xl border border-border bg-surface-1 shadow-2xl overflow-hidden"
      in:fly={modalIn}
      out:fly={modalOut}
      onclick={(e) => e.stopPropagation()}
      role="document"
    >
      <!-- Header -->
      {#if title || header || showCloseButton}
        <div class="flex items-center justify-between border-b border-border px-5 py-4">
          {#if header}
            {@render header()}
          {:else if title}
            <h2 id="modal-title" class="text-base font-semibold text-text-primary">{title}</h2>
          {:else}
            <div></div>
          {/if}

          {#if showCloseButton && onclose}
            <button
              type="button"
              onclick={onclose}
              class="flex h-8 w-8 items-center justify-center rounded-lg text-text-tertiary transition-colors hover:bg-surface-2 hover:text-text-primary"
              aria-label="Close modal"
            >
              <X size={20} />
            </button>
          {/if}
        </div>
      {/if}

      <!-- Body -->
      <div class="p-5 max-h-[70vh] overflow-y-auto">
        {@render children()}
      </div>

      <!-- Footer -->
      {#if footer}
        <div class="flex items-center justify-end gap-3 border-t border-border px-5 py-4">
          {@render footer()}
        </div>
      {/if}
    </div>
  </div>
{/if}
