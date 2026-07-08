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
  const theme = $derived(
    themePreference.resolvedMode === 'dark' ? edenDarkTheme : edenLightTheme,
  );
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

  // The gateway-health chip surfaced on the shell header (once, per doc 17 §5). A distinct testid so
  // the Build view's rail chip (the e2e-asserted `gateway-health`) stays the single canonical one.
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
    <div class="shell__health">
      <span
        class="shell__chip shell__chip--{healthy === null ? 'muted' : healthy ? 'ok' : 'warn'}"
        data-testid="shell-gateway-health"
        title="Agent gateway"
      >
        {healthy === null ? '…' : healthy ? 'gateway up' : 'gateway down'}
      </span>
    </div>
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
  .shell {
    display: grid;
    grid-template-columns: 248px 1fr;
    height: 100vh;
    overflow: hidden;
    background: var(--eden-app-bg);
    color: var(--eden-app-fg);
  }
  .shell__nav {
    display: flex;
    flex-direction: column;
    border-inline-end: 1px solid var(--eden-app-line);
    background: var(--eden-app-rail-bg);
    overflow-y: auto;
  }
  /* The SideNav flexes to fill; the health chip pins at the foot of the rail. */
  .shell__nav :global(.nav) {
    flex: 1;
  }
  .shell__health {
    padding: var(--space-2, 8px) var(--space-4, 16px) var(--space-4, 16px);
  }
  .shell__chip {
    display: inline-flex;
    align-items: center;
    gap: 0.35em;
    font-family: var(--font-code);
    font-size: var(--font-size-caption, 12px);
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    border-radius: 999px;
    padding: 0.18rem 0.6rem;
    line-height: 1.4;
    white-space: nowrap;
    background: color-mix(in oklab, var(--color-on-surface) 8%, var(--color-surface));
    color: var(--eden-app-muted);
  }
  .shell__chip--ok {
    background: var(--color-primary);
    color: var(--color-on-primary);
  }
  .shell__chip--warn {
    background: color-mix(in oklab, var(--color-warning) 22%, var(--color-surface));
    color: var(--color-warning);
  }
  .shell__main {
    overflow-y: auto;
    min-inline-size: 0;
  }
</style>
