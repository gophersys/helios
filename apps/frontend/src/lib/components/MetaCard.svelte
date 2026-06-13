<script lang="ts">
  // The document meta card (doc 12 §5): id, type, version, status, authors, dates,
  // and the typed links rendered as navigable item chips. Authors are agent runs
  // and humans (doc 11 §4 provenance); links are the upstream-only typed edges
  // (realizes/refines/verifies/supersedes/informs).
  import StatusChip from './StatusChip.svelte';
  import LinkChip from './LinkChip.svelte';
  import type { DocumentMeta } from '$lib/server/validatorClient';

  let { meta }: { meta: DocumentMeta } = $props();

  // Flatten the authors block into display strings: {run: …} → "run …",
  // {human: …} → the name.
  const authors = $derived(
    (meta.authors ?? []).map((author) => {
      if (typeof author.human === 'string') return author.human;
      if (typeof author.run === 'string') return `run ${author.run}`;
      return Object.values(author).map(String).join(' ');
    }),
  );

  // The typed-link entries with at least one target. supersedes is a single id or
  // null; the others are arrays. Normalize to {type, targets[]}.
  const linkEntries = $derived.by(() => {
    const links = meta.links ?? {};
    const entries: Array<{ type: string; targets: string[] }> = [];
    for (const [type, raw] of Object.entries(links)) {
      const targets = Array.isArray(raw)
        ? raw.filter((value): value is string => typeof value === 'string')
        : typeof raw === 'string'
          ? [raw]
          : [];
      if (targets.length > 0) entries.push({ type, targets });
    }
    return entries;
  });
</script>

<div class="meta-card panel">
  <dl class="meta-grid">
    <dt>id</dt>
    <dd><code>{meta.id}</code></dd>

    <dt>type</dt>
    <dd><code>{meta.type}</code></dd>

    <dt>status</dt>
    <dd><StatusChip status={meta.status} version={meta.version} /></dd>

    {#if meta.created}
      <dt>created</dt>
      <dd>{meta.created}</dd>
    {/if}

    {#if meta.updated}
      <dt>updated</dt>
      <dd>{meta.updated}</dd>
    {/if}

    {#if authors.length > 0}
      <dt>authors</dt>
      <dd class="meta-authors">
        {#each authors as author (author)}
          <span class="chip chip--neutral">{author}</span>
        {/each}
      </dd>
    {/if}

    {#if linkEntries.length > 0}
      <dt>links</dt>
      <dd class="meta-links">
        {#each linkEntries as entry (entry.type)}
          <div class="meta-link-row">
            <span class="meta-link-type">{entry.type}</span>
            {#each entry.targets as target (target)}
              <LinkChip {target} />
            {/each}
          </div>
        {/each}
      </dd>
    {/if}
  </dl>
</div>

<style>
  .meta-card {
    padding: 1rem 1.2rem;
  }
  .meta-grid {
    margin: 0;
    display: grid;
    grid-template-columns: minmax(5rem, max-content) 1fr;
    gap: 0.4rem 1.2rem;
    align-items: baseline;
  }
  dt {
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.03em;
    text-transform: uppercase;
    color: var(--muted);
  }
  dd {
    margin: 0;
    min-width: 0;
  }
  .meta-authors {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
  }
  .meta-links {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
  }
  .meta-link-row {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 0.35rem;
  }
  .meta-link-type {
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--muted);
    font-weight: 700;
    min-width: 5rem;
  }

  @media (max-width: 560px) {
    .meta-grid {
      grid-template-columns: 1fr;
      gap: 0.15rem;
    }
    dd {
      margin-bottom: 0.45rem;
    }
  }
</style>
