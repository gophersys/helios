<script lang="ts">
  import { page } from '$app/stores';
  import { fade } from 'svelte/transition';
  import { Link2 } from 'lucide-svelte';
  import { contextMenuState } from '$lib/actions/actionable-store.svelte';
  import { buildDeepLink } from '$lib/actions/deep-link';
  import { toasts } from '$lib/stores/toast.svelte';

  const MENU_WIDTH = 200;
  const MENU_HEIGHT = 52;

  // Clamp menu position so it stays within the viewport.
  const position = $derived.by(() => {
    const req = contextMenuState.request;
    if (!req) return { left: 0, top: 0 };
    const maxX = (globalThis.innerWidth ?? 1024) - MENU_WIDTH - 8;
    const maxY = (globalThis.innerHeight ?? 768) - MENU_HEIGHT - 8;
    return {
      left: Math.min(req.x, Math.max(8, maxX)),
      top: Math.min(req.y, Math.max(8, maxY)),
    };
  });

  async function copyLink() {
    const req = contextMenuState.request;
    if (!req) return;
    try {
      const url = buildDeepLink(req.id, $page.url);
      await navigator.clipboard.writeText(url);
      toasts.success(`Link to "${req.label}" copied`);
    } catch (err) {
      toasts.error('Failed to copy link');
      console.error('Copy link failed:', err);
    } finally {
      contextMenuState.close();
    }
  }

  function onBackdropClick() {
    contextMenuState.close();
  }

  function onKeyDown(event: KeyboardEvent) {
    if (event.key === 'Escape') {
      contextMenuState.close();
    } else if (event.key === 'Enter') {
      event.preventDefault();
      void copyLink();
    }
  }

  // Auto-close on scroll/resize — the menu position would otherwise drift.
  $effect(() => {
    if (!contextMenuState.request) return;
    const close = () => contextMenuState.close();
    window.addEventListener('scroll', close, { passive: true, capture: true });
    window.addEventListener('resize', close);
    return () => {
      window.removeEventListener('scroll', close, { capture: true });
      window.removeEventListener('resize', close);
    };
  });
</script>

<svelte:window onkeydown={onKeyDown} />

{#if contextMenuState.request}
  <!-- Backdrop to catch outside clicks -->
  <button
    type="button"
    class="fixed inset-0 z-[90] cursor-default bg-transparent"
    aria-label="Close menu"
    onclick={onBackdropClick}
    oncontextmenu={(e) => {
      e.preventDefault();
      onBackdropClick();
    }}
    transition:fade={{ duration: 80 }}
  ></button>

  <!-- Menu -->
  <div
    role="menu"
    class="fixed z-[91] min-w-[200px] rounded-lg border border-border bg-surface-1 py-1 shadow-elevated animate-overlay-in"
    style:left="{position.left}px"
    style:top="{position.top}px"
  >
    <button
      type="button"
      role="menuitem"
      onclick={copyLink}
      class="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-text-primary hover:bg-surface-2 transition-colors"
    >
      <Link2 size={14} class="text-text-tertiary" />
      <span>Copy link to <span class="font-medium">"{contextMenuState.request.label}"</span></span>
    </button>
  </div>
{/if}
