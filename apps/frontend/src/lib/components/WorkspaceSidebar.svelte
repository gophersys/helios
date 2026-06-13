<script lang="ts">
  // The workspace left rail — per-project document navigation (doc 12 §4/§5).
  // Documents grouped by tier (Product / Architecture / Implementation, doc 11 §2),
  // each a quiet row carrying its title plus a status chip with version; the active
  // document is highlighted (Notion-sidebar calm, not dense). A header shows the
  // project name and a collapse toggle that shrinks the rail to a slim strip,
  // handing the width back to the reading column. Selection is a query param
  // (?doc=) so a view is linkable and the back button works.
  import StatusChip from './StatusChip.svelte';
  import { documentTitle, TIERS } from '$lib/documentModel';
  import type { ProjectedDocument } from '$lib/server/validatorClient';

  let {
    tiers,
    slug,
    title,
    activeId,
    collapsed = false,
    onToggle,
  }: {
    tiers: Array<{ key: string; documents: ProjectedDocument[] }>;
    slug: string;
    title: string;
    activeId: string;
    collapsed?: boolean;
    onToggle?: () => void;
  } = $props();

  function tierLabel(key: string): string {
    return TIERS.find((tier) => tier.key === key)?.label ?? key;
  }
</script>

<nav class="sidebar" class:sidebar--collapsed={collapsed} aria-label="Project documents">
  <div class="sidebar__header">
    {#if !collapsed}
      <div class="sidebar__project">
        <a class="sidebar__home" href="/">← Projects</a>
        <p class="sidebar__title">{title}</p>
      </div>
    {/if}
    <button
      class="sidebar__toggle"
      type="button"
      onclick={() => onToggle?.()}
      aria-pressed={collapsed}
      aria-label={collapsed ? 'Expand document navigation' : 'Collapse document navigation'}
      title={collapsed ? 'Expand' : 'Collapse'}
    >
      <span class="sidebar__toggle-glyph" aria-hidden="true">{collapsed ? '»' : '«'}</span>
    </button>
  </div>

  {#if !collapsed}
    <div class="sidebar__body">
      {#each tiers as tier (tier.key)}
        {#if tier.documents.length > 0}
          <section class="tier tier--{tier.key}">
            <h2 class="tier__label">{tierLabel(tier.key)}</h2>
            <ul class="tier__docs">
              {#each tier.documents as document (document.meta.id)}
                <li>
                  <a
                    class="doc-link"
                    class:active={document.meta.id === activeId}
                    href={`/p/${slug}?doc=${encodeURIComponent(document.meta.id)}`}
                    aria-current={document.meta.id === activeId ? 'page' : undefined}
                  >
                    <span class="doc-link__title">{documentTitle(document.meta)}</span>
                    <StatusChip status={document.meta.status} version={document.meta.version} />
                  </a>
                </li>
              {/each}
            </ul>
          </section>
        {/if}
      {/each}
    </div>
  {/if}
</nav>

<style>
  .sidebar {
    display: flex;
    flex-direction: column;
    min-height: 100%;
  }

  .sidebar__header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 0.5rem;
    padding: 1.2rem 0.8rem 0.9rem;
    border-bottom: 1px solid var(--line);
    position: sticky;
    top: 0;
    background: var(--navbg);
    z-index: 1;
  }
  .sidebar--collapsed .sidebar__header {
    justify-content: center;
    padding: 1.2rem 0.4rem 0.9rem;
  }
  .sidebar__project {
    min-width: 0;
  }
  .sidebar__home {
    display: inline-block;
    font-size: 0.78rem;
    font-weight: 600;
    color: var(--muted);
    text-decoration: none;
    margin-bottom: 0.25rem;
  }
  .sidebar__home:hover {
    color: var(--accent);
  }
  .sidebar__title {
    font-family: var(--font-display);
    font-size: 1.02rem;
    font-weight: 600;
    letter-spacing: -0.01em;
    color: var(--fg);
    margin: 0;
    line-height: 1.2;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  /* The collapse toggle — a small quiet square; the only chrome the collapsed rail
     keeps. */
  .sidebar__toggle {
    flex: none;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 1.7rem;
    height: 1.7rem;
    border: 1px solid var(--line);
    border-radius: 6px;
    background: var(--bg);
    color: var(--muted);
    cursor: pointer;
    font-size: 0.9rem;
    line-height: 1;
    transition:
      color 0.12s ease,
      border-color 0.12s ease;
  }
  .sidebar__toggle:hover {
    color: var(--accent);
    border-color: var(--accent);
  }
  .sidebar__toggle-glyph {
    display: block;
  }

  .sidebar__body {
    display: flex;
    flex-direction: column;
    gap: 1.3rem;
    padding: 1.1rem 0.8rem 3rem;
  }

  .tier__label {
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--muted);
    margin: 0 0 0.5rem;
    padding-bottom: 0.3rem;
    border-bottom: 1px solid var(--line);
  }
  .tier--product .tier__label {
    color: var(--tier-product, var(--accent));
  }
  .tier--architecture .tier__label {
    color: var(--tier-architecture, var(--accent));
  }
  .tier--implementation .tier__label {
    color: var(--tier-implementation, var(--accent));
  }

  .tier__docs {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.1rem;
  }
  /* A quiet row: title left, status chip right; calm until hovered/active. */
  .doc-link {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
    padding: 0.42rem 0.55rem;
    border-radius: 6px;
    text-decoration: none;
    color: var(--fg);
    font-size: 0.88rem;
    line-height: 1.3;
    transition:
      background 0.12s ease,
      color 0.12s ease;
  }
  .doc-link:hover {
    background: color-mix(in srgb, var(--color-sage) 16%, transparent);
  }
  .doc-link.active {
    background: color-mix(in srgb, var(--color-moss) 16%, transparent);
    color: var(--fg);
    font-weight: 600;
    box-shadow: inset 2px 0 0 var(--accent);
  }
  .doc-link__title {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
</style>
