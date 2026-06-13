<script lang="ts">
  // The workspace left sidebar (doc 12 §5): documents grouped by tier (Product /
  // Architecture / Implementation, doc 11 §2), each entry showing its title, a
  // status chip (with version), and selectable into the main panel. The active
  // document is highlighted; selection is a query param (?doc=) so a view is
  // linkable and the back button works.
  import StatusChip from './StatusChip.svelte';
  import { documentTitle, TIERS } from '$lib/documentModel';
  import type { ProjectedDocument } from '$lib/server/validatorClient';

  let {
    tiers,
    slug,
    activeId,
  }: {
    tiers: Array<{ key: string; documents: ProjectedDocument[] }>;
    slug: string;
    activeId: string;
  } = $props();

  function tierLabel(key: string): string {
    return TIERS.find((tier) => tier.key === key)?.label ?? key;
  }
</script>

<nav class="sidebar" aria-label="Document set by tier">
  <a class="sidebar__home" href="/">← Projects</a>
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
</nav>

<style>
  .sidebar {
    display: flex;
    flex-direction: column;
    gap: 1.3rem;
    padding: 1.4rem 1rem 3rem;
  }
  .sidebar__home {
    font-size: 0.84rem;
    font-weight: 600;
    color: var(--muted);
    text-decoration: none;
  }
  .sidebar__home:hover {
    color: var(--accent);
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
    gap: 0.15rem;
  }
  .doc-link {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
    padding: 0.4rem 0.5rem;
    border-radius: 6px;
    text-decoration: none;
    color: var(--fg);
    font-size: 0.9rem;
  }
  .doc-link:hover {
    background: var(--chipbg);
  }
  .doc-link.active {
    background: var(--chip-info-bg);
    color: var(--chip-info-fg);
    font-weight: 600;
  }
  .doc-link__title {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
</style>
