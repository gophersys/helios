<script lang="ts">
  // The authenticated APP SHELL — Eden's ONE chrome (doc 17 §5, the one-shell ruling). A persistent
  // left sidebar (brand · primary nav · the signed-in user) beside the routed content, hosting EVERY
  // surface: the management pages (/projects, /sessions, /clusters) AND the Build view (the former
  // parallel /chat workspace, now mounted INSIDE this shell at /chat, /projects/[id]/build, and
  // /sessions/[id]). Two capabilities that used to live only in the /chat shell lift here so they
  // work from anywhere: the ⌘K command palette (mounted ONCE, carrying the app-navigation commands
  // plus whatever the active Build view contributes via the palette bus) and the gateway-health chip
  // in the shell header. Only the login screen sits OUTSIDE this group. Token-driven from @eden/theme.
  import { onDestroy } from 'svelte';
  import { goto } from '$app/navigation';
  import { CommandPalette, type CommandPaletteGroup } from '@eden/primitives';
  import SideNav, { type NavItem } from '$lib/shell/SideNav.svelte';
  import SettingsSurface from '$lib/settings/SettingsSurface.svelte';
  import { GatewayClient } from '$lib/gateway/client';
  import { resolveGatewayUrl } from '$lib/gateway/configuration';
  import { edenLightTheme, edenDarkTheme } from '$lib/theme/edenTheme';
  import { themePreference } from '$lib/theme/themePreference.svelte';
  import { currentUser } from '$lib/platform/currentUser.svelte';
  import { PaletteBus, provizePaletteBus } from '$lib/buildview/paletteBus.svelte';

  let { children } = $props();

  const client = new GatewayClient(resolveGatewayUrl());
  const gatewayUrl = resolveGatewayUrl();
  // The Theme OBJECT handed to @eden/primitives tracks the RESOLVED colour mode, so a component whose
  // chrome is derived from the Theme (the Settings sheet, the ⌘K palette — not just the CSS cascade)
  // flips WITH the app when Appearance switches light/dark/system (doc 17 §3, "must actually retheme").
  const theme = $derived(themePreference.resolvedMode === 'dark' ? edenDarkTheme : edenLightTheme);
  // The ONE Settings surface (doc 17 §7). `settingsSection` deep-links which section opens: the
  // sidebar user affordance (`user-settings-open`) lands on Agents; ⌘K's Settings lands on Agents too
  // (the platform-preference default). The Build view's top-bar `settings-open` lands on Appearance.
  let settingsOpen = $state(false);
  let settingsSection = $state<string>('agents');

  /** Open the Settings surface at a given section (the deep-link entry points). */
  function openSettings(section: string): void {
    settingsSection = section;
    settingsOpen = true;
  }

  // ── the shared ⌘K palette bus (doc 17 §5) ──────────────────────────────────────.
  // The bus is provided to the whole subtree so the Build view can REGISTER its session commands;
  // the ONE palette element (below) reads them + the always-on app-navigation group. ⌘K/Ctrl-K
  // toggles it from any route in the shell (the global key handler on this layout).
  const palette = new PaletteBus();
  provizePaletteBus(palette);

  // W5 (doc 17 §2 dedup): gateway health had THREE homes — this shell rail chip, the Build rail's
  // e2e-asserted `gateway-health` chip, and the Settings→Connections status. The shell chip and the
  // Build-rail chip said the same thing in the same place (both foot of a left rail), so the shell
  // chip is removed; the canonical live indicator is the Build rail's `gateway-health` ('gateway up'),
  // and Settings→Connections is the deliberate read-only detail surface (§7). The Settings surface
  // still needs the live health, so we keep the probe here and feed it in below.
  let healthy = $state<boolean | null>(null);
  $effect(() => {
    void (async () => {
      healthy = await client.health();
    })();
  });

  // The signed-in identity drives the sidebar user; re-establish it from the stored token ONCE on
  // mount (a reload or a deep-link into the shell). A one-shot guard is essential: restore() leaves
  // `user` null when there is no token (signed out → the neutral "You" fallback), so re-running on the
  // user/loading state would loop. The shell never blocks on the platform API.
  let restoreAttempted = $state(false);
  $effect(() => {
    if (!restoreAttempted) {
      restoreAttempted = true;
      if (!currentUser.user) void currentUser.restore();
    }
  });

  // The primary navigation — the SaaS app's sections. The Build view is reached FROM a project or
  // session (a scoped detail view), so it is not a top-level nav item.
  const NAV: readonly NavItem[] = [
    { label: 'Projects', href: '/projects', glyph: '▤' },
    { label: 'Sessions', href: '/sessions', glyph: '◇' },
    { label: 'Clusters', href: '/clusters', glyph: '⎈' },
  ];

  // The always-on app-navigation commands the ⌘K palette carries on every route (doc 17 §5: the
  // palette's commands "gain the app-shell navigations alongside the session commands").
  const NAV_GROUP: CommandPaletteGroup = {
    value: 'navigate',
    heading: 'Go to',
    items: [
      { value: 'nav:/projects', label: 'Projects', keywords: ['home', 'dashboard'] },
      { value: 'nav:/sessions', label: 'Sessions', keywords: ['agents', 'runs'] },
      { value: 'nav:/clusters', label: 'Clusters', keywords: ['atlas', 'topology', 'k8s'] },
      { value: 'nav:/chat', label: 'Build (new chat)', keywords: ['chat', 'workspace'] },
      { value: 'settings', label: 'Settings', keywords: ['preferences', 'agents', 'profile'] },
    ],
  };

  // The palette groups: the Build view's contributed groups (if a build is open) FIRST, then the
  // app-navigation group — so ⌘K always offers navigation and, in a build, its controls too.
  const groups = $derived<CommandPaletteGroup[]>([...palette.providerGroups, NAV_GROUP]);

  /** Dispatch a selected ⌘K command: try the active Build provider first (it owns new-project /
   *  session / control commands), then fall through to the shell's app-navigation + settings. */
  function onSelect(value: string): void {
    palette.open = false;
    if (palette.runProvider(value)) return;
    if (value === 'settings') {
      openSettings('agents');
      return;
    }
    if (value.startsWith('nav:')) {
      void goto(value.slice('nav:'.length));
    }
  }

  function onGlobalKey(event: KeyboardEvent): void {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      palette.toggle();
    }
  }

  onDestroy(() => {
    palette.open = false;
  });
</script>

<svelte:window onkeydown={onGlobalKey} />

<div class="shell" data-testid="app-shell">
  <aside class="shell__nav">
    <SideNav user={currentUser.user} nav={NAV} onSettings={() => openSettings('agents')} {theme} />
  </aside>
  <main class="shell__main">
    {@render children()}
  </main>
</div>

<!-- ── the ONE ⌘K command palette for the whole shell (doc 17 §5) ─────────────── -->
<CommandPalette
  {groups}
  bind:open={palette.open}
  {onSelect}
  {theme}
  label="Eden command palette"
  placeholder="Type a command, search sessions, or jump to a page…"
/>

<SettingsSurface
  bind:open={settingsOpen}
  bind:section={settingsSection}
  {theme}
  loadConfigs={() => client.listAgentConfigs()}
  saveConfig={(agentType, body) => client.saveAgentConfig(agentType, body)}
  gatewayHealthy={healthy}
  platformSignedIn={currentUser.signedIn}
  gatewayLabel={gatewayUrl}
  platformLabel="/platform"
/>

<style>
  /* Design spike (spike/shadcn-theme): the shell reads against the SHADCN SKIN MAPPING — a --muted
     sidebar tone against the --background canvas, a 1px --border divider (the shadcn app-shell). */
  .shell {
    display: grid;
    grid-template-columns: 248px 1fr;
    height: 100vh;
    overflow: hidden;
    background: var(--background, var(--eden-app-bg));
    color: var(--foreground, var(--eden-app-fg));
  }
  .shell__nav {
    display: flex;
    flex-direction: column;
    border-inline-end: 1px solid var(--border, var(--eden-app-line));
    background: var(--surface-muted, var(--eden-app-rail-bg));
    overflow-y: auto;
  }
  /* The SideNav flexes to fill the rail. */
  .shell__nav :global(.nav) {
    flex: 1;
  }
  .shell__main {
    overflow-y: auto;
    min-inline-size: 0;
  }
</style>
