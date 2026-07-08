<script lang="ts">
  // SideNav — the persistent left sidebar of Eden's app shell (the common cloud-SaaS layout): the
  // brand, the primary navigation (with an active-route indicator), and the signed-in user pinned at
  // the bottom (clicking it opens Settings). Token-driven from @eden/theme; REUSABLE — the shell
  // layout composes it, pages do not. The user + nav are injected, so it stays presentation-only.
  import { page } from '$app/stores';
  import type { Theme } from '@eden/theme';
  import type { PlatformUser } from '$lib/platform/client';

  export interface NavItem {
    label: string;
    href: string;
    glyph: string;
  }

  // theme is accepted for parity with the other chrome; every visual is token-driven (the
  // underscore-alias convention the chat components use), so it is intentionally unused here.
  let {
    user,
    nav,
    onSettings,
    theme: _theme,
  }: {
    user: PlatformUser | null;
    nav: readonly NavItem[];
    onSettings: () => void;
    theme?: Theme;
  } = $props();

  const initials = $derived(
    (user?.name ?? 'You')
      .split(/\s+/)
      .map((word) => word.charAt(0))
      .slice(0, 2)
      .join('')
      .toUpperCase(),
  );

  function isActive(href: string): boolean {
    const path = $page.url.pathname;
    return path === href || path.startsWith(`${href}/`);
  }
</script>

<nav class="nav" data-testid="app-nav" aria-label="Primary">
  <a class="nav__brand" href="/projects" data-testid="nav-brand">
    <span class="nav__mark" aria-hidden="true">◆</span>
    <span class="nav__name">Eden</span>
  </a>

  {#if user?.organization}
    <!-- The current tenant (org switcher placeholder — the IOTEA org/space switch lands here later). -->
    <div class="nav__org" data-testid="nav-org" title="Organization">
      <span class="nav__org-glyph" aria-hidden="true">⬡</span>
      <span class="nav__org-name">{user.organization.name}</span>
    </div>
  {/if}

  <ul class="nav__list" role="list">
    {#each nav as item (item.href)}
      <li>
        <a
          class="nav__link"
          class:nav__link--active={isActive(item.href)}
          href={item.href}
          data-testid={`nav-${item.label.toLowerCase()}`}
          aria-current={isActive(item.href) ? 'page' : undefined}
        >
          <span class="nav__glyph" aria-hidden="true">{item.glyph}</span>
          <span class="nav__label">{item.label}</span>
        </a>
      </li>
    {/each}
  </ul>

  <div class="nav__spacer"></div>

  <button class="nav__user" data-testid="user-settings-open" onclick={onSettings} title="Settings">
    <span class="nav__avatar" aria-hidden="true">{initials}</span>
    <span class="nav__identity">
      <span class="nav__username" data-testid="user-name">{user?.name ?? 'You'}</span>
      {#if user?.role}
        <span class="nav__role" data-testid="user-role" data-role={user.role}>{user.role}</span>
      {:else if user?.email}
        <span class="nav__email">{user.email}</span>
      {/if}
    </span>
    <span class="nav__gear" aria-hidden="true">⚙</span>
  </button>
</nav>

<style>
  .nav {
    display: flex;
    flex-direction: column;
    height: 100%;
    padding: var(--space-4, 16px) var(--space-3, 12px);
    gap: var(--space-4, 16px);
  }
  .nav__brand {
    display: flex;
    align-items: center;
    gap: var(--space-2, 8px);
    padding: var(--space-1, 4px) var(--space-2, 8px);
    text-decoration: none;
    color: var(--eden-app-fg);
  }
  .nav__mark {
    color: var(--eden-app-accent);
    font-size: 1.2rem;
  }
  .nav__name {
    font-weight: 700;
    font-size: 1.15rem;
    letter-spacing: 0.01em;
  }
  .nav__org {
    display: flex;
    align-items: center;
    gap: var(--space-2, 8px);
    padding: var(--space-2, 8px) var(--space-3, 12px);
    border: 1px solid var(--eden-app-line);
    border-radius: var(--eden-app-radius, 8px);
    color: var(--eden-app-fg);
    font-size: 0.88rem;
    font-weight: 600;
  }
  .nav__org-glyph {
    color: var(--eden-app-accent);
  }
  .nav__org-name {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .nav__list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .nav__role {
    align-self: flex-start;
    margin-block-start: 1px;
    padding: 0 var(--space-2, 8px);
    border-radius: 999px;
    font-size: 0.66rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    background: color-mix(in oklab, var(--eden-app-accent) 22%, transparent);
    color: var(--eden-app-fg);
  }
  .nav__role[data-role='admin'] {
    background: color-mix(in oklab, var(--color-info, var(--eden-app-accent)) 28%, transparent);
  }
  .nav__link {
    display: flex;
    align-items: center;
    gap: var(--space-3, 12px);
    padding: var(--space-2, 8px) var(--space-3, 12px);
    border-radius: var(--eden-app-radius, 8px);
    text-decoration: none;
    color: var(--eden-app-muted);
    font-size: var(--font-size-body, 15px);
    /* W5: nav-link hover rides the theme motion tokens (nearest ladder step + standard easing). */
    transition:
      background var(--duration-short-2, 120ms) var(--ease-standard, ease),
      color var(--duration-short-2, 120ms) var(--ease-standard, ease);
  }
  .nav__link:hover {
    background: color-mix(in oklab, var(--eden-app-fg) 6%, transparent);
    color: var(--eden-app-fg);
  }
  .nav__link--active {
    background: color-mix(in oklab, var(--eden-app-accent) 16%, transparent);
    color: var(--eden-app-fg);
    font-weight: 600;
  }
  .nav__glyph {
    color: var(--eden-app-accent);
    inline-size: 1.2em;
    text-align: center;
  }
  .nav__spacer {
    flex: 1;
  }
  .nav__user {
    display: flex;
    align-items: center;
    gap: var(--space-2, 8px);
    inline-size: 100%;
    padding: var(--space-2, 8px);
    border: 1px solid var(--eden-app-line);
    border-radius: var(--eden-app-radius, 8px);
    background: none;
    color: inherit;
    cursor: pointer;
    text-align: start;
    transition: border-color var(--duration-short-2, 120ms) var(--ease-standard, ease);
  }
  .nav__user:hover {
    border-color: var(--eden-app-accent);
  }
  .nav__avatar {
    display: grid;
    place-items: center;
    inline-size: 32px;
    block-size: 32px;
    border-radius: 999px;
    background: color-mix(in oklab, var(--eden-app-accent) 24%, var(--eden-app-panel-bg));
    color: var(--eden-app-fg);
    font-size: 0.78rem;
    font-weight: 600;
    flex-shrink: 0;
  }
  .nav__identity {
    display: flex;
    flex-direction: column;
    line-height: 1.2;
    min-inline-size: 0;
    flex: 1;
  }
  .nav__username {
    font-weight: 600;
    font-size: 0.9rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .nav__email {
    font-size: 0.74rem;
    color: var(--eden-app-muted);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .nav__gear {
    color: var(--eden-app-muted);
    flex-shrink: 0;
  }
</style>
