<script lang="ts">
  import { onMount } from 'svelte';
  import { browser } from '$app/environment';
  import Sidebar from './sidebar.svelte';
  import SettingsModal from './settings/settings-modal.svelte';

  let { children } = $props();

  // Sidebar collapse state (persisted)
  let collapsed = $state(false);
  let settingsOpen = $state(false);

  onMount(() => {
    if (browser) {
      const stored = localStorage.getItem('concord-sidebar-collapsed');
      collapsed = stored === 'true';
    }
  });

  function toggleSidebar(): void {
    collapsed = !collapsed;
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
    class="flex-1 transition-[margin] duration-200 ease-out"
    style:margin-left={sidebarWidth}
  >
    <!-- Content wrapper with consistent padding (24px = space-6) -->
    <div class="mx-auto max-w-7xl px-6 py-6">
      {@render children()}
    </div>
  </main>
</div>

{#if settingsOpen}
  <SettingsModal onClose={() => (settingsOpen = false)} />
{/if}
