<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { browser } from '$app/environment';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { getAuth } from '$lib/stores/auth.svelte';
  import Sidebar from './sidebar.svelte';
  import SettingsModal from './settings/settings-modal.svelte';
  import NotificationBell from './ui/notification-bell.svelte';

  let { children } = $props();

  const auth = getAuth();

  // Sidebar collapse state (persisted)
  let collapsed = $state(false);
  let autoCollapsed = $state(false);
  let settingsOpen = $state(false);

  // Deep-link: corectl's device-code flow sends users to /?code=XXXX-XXXX.
  //
  //   • Authed: auto-open the Settings → Sessions dialog so the approval
  //     is one click from wherever the user was, with no re-login.
  //   • Not authed: bounce through /login?next=... preserving the code
  //     so after they log in they land right back here and the modal
  //     opens automatically.
  let pendingSessionCode = $state<string | null>(null);
  let settingsInitialSection = $state<string | null>(null);

  $effect(() => {
    if (!browser) return;
    const code = $page.url.searchParams.get('code');
    if (!code) return;

    // Wait for the auth check to settle — a race against auth.init()
    // would otherwise redirect to /login while the user's cookie is
    // still being validated.
    if (auth.isLoading) return;

    if (!auth.isAuthenticated) {
      // Preserve the full URL (including the code param) through login.
      const next = encodeURIComponent($page.url.pathname + $page.url.search);
      goto(`/login?next=${next}`, { replaceState: true });
      return;
    }

    if (settingsOpen) return;

    pendingSessionCode = code.toUpperCase();
    settingsInitialSection = 'sessions';
    settingsOpen = true;
    // Scrub the param so refresh / back-button doesn't re-trigger after
    // approval. Preserve any other query params the page was using.
    const url = new URL($page.url);
    url.searchParams.delete('code');
    goto(url.pathname + url.search + url.hash, { replaceState: true, noScroll: true, keepFocus: true });
  });

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
    <!-- Global notification bell — fixed top-right -->
    <div class="fixed top-3 right-3 z-fixed">
      <NotificationBell position="topbar" />
    </div>

    <!-- Content wrapper with responsive padding -->
    <div class="mx-auto max-w-7xl px-3 sm:px-6 py-6">
      {@render children()}
    </div>
  </main>
</div>

{#if settingsOpen}
  <SettingsModal
    onClose={() => {
      settingsOpen = false;
      pendingSessionCode = null;
      settingsInitialSection = null;
    }}
    initialSection={settingsInitialSection ?? undefined}
    initialCode={pendingSessionCode ?? undefined}
  />
{/if}
