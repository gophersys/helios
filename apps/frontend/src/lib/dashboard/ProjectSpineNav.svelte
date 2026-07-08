<script lang="ts">
  // ProjectSpineNav — the project spine's tab navigation (doc 17 §5: the [project] owns Overview ·
  // Build · Workspace · Insight). A horizontal row of ROUTE LINKS (these are separate SvelteKit
  // surfaces, not in-page tabs, so anchors are the honest control — deep-linkable, back-button-safe),
  // with the active tab derived from the current pathname. Token-driven from the app's --eden-app-* /
  // --color-* vocabulary; no hand-set hex/px on a painted role. Reusable: the Overview/Build/Workspace/
  // Insight routes all mount this so the spine reads as one navigable object.
  import { page } from '$app/state';

  let { projectId }: { projectId: string } = $props();

  interface SpineTab {
    label: string;
    // the sub-path under /projects/[id] ('' = the Overview root)
    sub: string;
    testid: string;
  }
  const TABS: readonly SpineTab[] = [
    { label: 'Overview', sub: '', testid: 'spine-overview' },
    { label: 'Build', sub: '/build', testid: 'spine-build' },
    { label: 'Workspace', sub: '/workspace', testid: 'spine-workspace' },
    { label: 'Insight', sub: '/insight', testid: 'spine-insight' },
  ];

  const base = $derived(`/projects/${encodeURIComponent(projectId)}`);
  // The active tab is the LONGEST matching sub-path (so /build wins over the '' Overview root). The
  // Overview root matches only the exact base path.
  const activeSub = $derived.by(() => {
    const path = page.url.pathname;
    const withSub = TABS.filter((t) => t.sub !== '' && path === `${base}${t.sub}`);
    if (withSub.length > 0) return withSub[0].sub;
    return '';
  });
</script>

<nav class="spine" aria-label="Project sections" data-testid="project-spine-nav">
  {#each TABS as tab (tab.sub)}
    <a
      class="spine__tab"
      href={`${base}${tab.sub}`}
      data-testid={tab.testid}
      data-active={activeSub === tab.sub}
      aria-current={activeSub === tab.sub ? 'page' : undefined}
    >
      {tab.label}
    </a>
  {/each}
</nav>

<style>
  .spine {
    display: flex;
    gap: var(--space-1, 4px);
    border-block-end: 1px solid var(--eden-app-line, var(--color-outline));
    padding-inline: var(--space-6, 24px);
  }
  .spine__tab {
    display: inline-flex;
    align-items: center;
    min-block-size: 44px;
    padding: var(--space-2, 8px) var(--space-3, 12px);
    color: var(--eden-app-muted, var(--color-outline));
    text-decoration: none;
    font-size: var(--font-size-label, 14px);
    font-weight: 500;
    border-block-end: 2px solid transparent;
    margin-block-end: -1px;
    /* W5: the tab underline/colour move rides the theme motion tokens (nearest ladder step +
       the standard on-screen easing), not a hand-set duration/curve. */
    transition:
      color var(--duration-short-2, 120ms) var(--ease-standard, ease),
      border-block-end-color var(--duration-short-2, 120ms) var(--ease-standard, ease);
  }
  .spine__tab:hover {
    color: var(--eden-app-fg, var(--color-on-surface));
  }
  .spine__tab[data-active='true'] {
    color: var(--color-primary);
    border-block-end-color: var(--color-primary);
  }
  .spine__tab:focus-visible {
    outline: 2px solid var(--color-primary);
    outline-offset: 2px;
  }
  @media (prefers-reduced-motion: reduce) {
    .spine__tab {
      transition: none;
    }
  }
</style>
