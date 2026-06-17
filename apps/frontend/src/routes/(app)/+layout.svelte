<script lang="ts">
  // The authenticated APP SHELL — Eden's common cloud-SaaS layout: a persistent left sidebar (brand
  // · primary nav · the signed-in user) beside a scrollable content area the routed page fills. Every
  // management page (/projects, /sessions, …) renders inside it, so navigation is one click and the
  // chrome (nav + user + Settings) is shared. The login screen and the full-screen chat workspace sit
  // OUTSIDE this group (they own their whole viewport). Token-driven from @eden/theme.
  import SideNav, { type NavItem } from '$lib/shell/SideNav.svelte';
  import SettingsModal from '$lib/dashboard/SettingsModal.svelte';
  import { GatewayClient } from '$lib/gateway/client';
  import { resolveGatewayUrl } from '$lib/gateway/configuration';
  import { edenTheme } from '$lib/theme/edenTheme';
  import { currentUser } from '$lib/platform/currentUser.svelte';

  let { children } = $props();

  const client = new GatewayClient(resolveGatewayUrl());
  const theme = edenTheme;
  let settingsOpen = $state(false);

  // The signed-in identity drives the sidebar user; load it lazily if a deep-link skipped login (a
  // failure leaves the neutral "You" fallback — the shell never blocks on the platform API).
  $effect(() => {
    if (!currentUser.user && !currentUser.loading) void currentUser.load();
  });

  // The primary navigation — the SaaS app's sections. The chat workspace is reached FROM a project or
  // session (a full-screen detail view), so it is not a top-level nav item.
  const NAV: readonly NavItem[] = [
    { label: 'Projects', href: '/projects', glyph: '▤' },
    { label: 'Sessions', href: '/sessions', glyph: '◇' },
  ];
</script>

<div class="shell" data-testid="app-shell">
  <aside class="shell__nav">
    <SideNav user={currentUser.user} nav={NAV} onSettings={() => (settingsOpen = true)} {theme} />
  </aside>
  <main class="shell__main">
    {@render children()}
  </main>
</div>

<SettingsModal
  bind:open={settingsOpen}
  {theme}
  loadConfigs={() => client.listAgentConfigs()}
  saveConfig={(agentType, body) => client.saveAgentConfig(agentType, body)}
/>

<style>
  .shell {
    display: grid;
    grid-template-columns: 248px 1fr;
    height: 100vh;
    overflow: hidden;
    background: var(--eden-app-bg);
    color: var(--eden-app-fg);
  }
  .shell__nav {
    border-inline-end: 1px solid var(--eden-app-line);
    background: var(--eden-app-rail-bg);
    overflow-y: auto;
  }
  .shell__main {
    overflow-y: auto;
    min-inline-size: 0;
  }
</style>
