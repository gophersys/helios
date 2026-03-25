<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { browser } from '$app/environment';
  import Sidebar from './sidebar.svelte';
  import SettingsModal from './settings/settings-modal.svelte';

  let { children } = $props();

  // Sidebar collapse state (persisted)
  let collapsed = $state(false);
  let autoCollapsed = $state(false);
  let settingsOpen = $state(false);

  const NARROW_BREAKPOINT = 768;

  function handleResize(): void {
    if (!browser) return;
    const narrow = window.innerWidth < NARROW_BREAKPOINT;
    if (narrow && !autoCollapsed) {
      autoCollapsed = true;
      collapsed = true;
    } else if (!narrow && autoCollapsed) {
      autoCollapsed = false;
      const stored = localStorage.getItem('concord-sidebar-collapsed');
      collapsed = stored === 'true';
    }
  }

  onMount(() => {
    if (browser) {
      const stored = localStorage.getItem('concord-sidebar-collapsed');
      collapsed = stored === 'true';
      handleResize();
      window.addEventListener('resize', handleResize);
    }
  });

  onDestroy(() => {
    if (browser) {
      window.removeEventListener('resize', handleResize);
    }
  });

  function toggleSidebar(): void {
    collapsed = !collapsed;
    autoCollapsed = false;
    if (browser) {
      localStorage.setItem('concord-sidebar-collapsed', String(collapsed));
    }
  }

  const sidebarWidth = $derived(collapsed ? 'var(--sidebar-collapsed-width)' : 'var(--sidebar-width)');
</script>

<div class="flex min-h-screen bg-surface-0">
  <Sidebar
    {collapsed}
    onToggle={toggleSidebar}
    onSettingsClick={() => (settingsOpen = true)}
  />

  <main
    id="main-content"
    class="flex-1 transition-[margin] duration-200 ease-out"
    style:margin-left={sidebarWidth}
  >
    <!-- Content wrapper with responsive padding -->
    <div class="mx-auto max-w-7xl px-3 sm:px-6 py-6">
      {@render children()}
    </div>
  </main>
</div>

{#if settingsOpen}
  <SettingsModal onClose={() => (settingsOpen = false)} />
{/if}
