<script lang="ts">
  // The main workspace panel for one document (doc 12 §5). Top to bottom:
  //   · a validation bar (corpus totals, expandable, active-doc diagnostics marked);
  //   · the title + status;
  //   · the meta card (id/type/version/status/authors/dates/links as chips);
  //   · the data block(s) — arrays of objects as tables (with item anchors and
  //     derived backlinks), nested objects as definition lists, via DataValue;
  //   · the narrative sections as rendered markdown.
  // It computes the active document's id set (its own id + every item id in its
  // data) so the validation bar can flag the diagnostics that pertain to it.
  import MetaCard from './MetaCard.svelte';
  import DataValue from './DataValue.svelte';
  import MarkdownSection from './MarkdownSection.svelte';
  import ValidationBar from './ValidationBar.svelte';
  import StatusChip from './StatusChip.svelte';
  import { documentTitle, isItemId } from '$lib/documentModel';
  import type { Diagnostic, ProjectedDocument } from '$lib/server/validatorClient';
  import type { Backlink } from '../../routes/p/[slug]/+page.server';

  let {
    document,
    backlinks,
    validation,
  }: {
    document: ProjectedDocument;
    backlinks: Record<string, Backlink[]>;
    validation: {
      violations: Diagnostic[];
      coverage: Diagnostic[];
      ok: boolean;
      violationsExit: boolean;
    };
  } = $props();

  const dataEntries = $derived(Object.entries(document.data ?? {}));
  const sectionEntries = $derived(Object.entries(document.sections ?? {}));

  function blockLabel(key: string): string {
    const spaced = key.replace(/[_-]/g, ' ');
    return spaced.charAt(0).toUpperCase() + spaced.slice(1);
  }

  // Every item id reachable in a value (the id field of any object, at any depth),
  // used to scope the validation bar to this document's items.
  function collectItemIds(value: unknown, found: Set<string>): void {
    if (Array.isArray(value)) {
      for (const entry of value) collectItemIds(entry, found);
      return;
    }
    if (typeof value === 'object' && value !== null) {
      const record = value as Record<string, unknown>;
      if (typeof record.id === 'string' && isItemId(record.id)) found.add(record.id);
      for (const entry of Object.values(record)) collectItemIds(entry, found);
    }
  }

  const activeIds = $derived.by(() => {
    const ids = new Set<string>([document.meta.id]);
    collectItemIds(document.data, ids);
    return [...ids];
  });

  const title = $derived(documentTitle(document.meta));
</script>

<article class="document-panel">
  <ValidationBar
    violations={validation.violations}
    coverage={validation.coverage}
    ok={validation.ok}
    violationsExit={validation.violationsExit}
    {activeIds}
  />

  <header class="document-panel__head">
    <p class="document-panel__type">{document.meta.type}</p>
    <h2 class="document-panel__title">
      {title}
      <StatusChip status={document.meta.status} version={document.meta.version} />
    </h2>
  </header>

  <MetaCard meta={document.meta} />

  {#if dataEntries.length > 0}
    <section class="document-panel__data">
      {#each dataEntries as [key, value] (key)}
        <div class="data-block">
          <h3 class="data-block__heading">{blockLabel(key)}</h3>
          <DataValue {value} {backlinks} />
        </div>
      {/each}
    </section>
  {/if}

  {#if sectionEntries.length > 0}
    <section class="document-panel__sections">
      {#each sectionEntries as [key, markdown] (key)}
        <MarkdownSection title={key} {markdown} />
      {/each}
    </section>
  {/if}
</article>

<style>
  .document-panel {
    max-width: 60rem;
  }
  .document-panel__head {
    margin-bottom: 1rem;
  }
  .document-panel__type {
    font-size: 0.74rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: var(--muted);
    margin: 0 0 0.3rem;
  }
  .document-panel__title {
    font-size: 1.5rem;
    letter-spacing: -0.015em;
    margin: 0;
    display: flex;
    align-items: center;
    gap: 0.7rem;
    flex-wrap: wrap;
  }
  .document-panel__data {
    margin: 1.4rem 0;
    display: flex;
    flex-direction: column;
    gap: 1.4rem;
  }
  .data-block__heading {
    font-size: 1.02rem;
    letter-spacing: -0.005em;
    margin: 0 0 0.6rem;
  }
  .document-panel__sections {
    margin-top: 1.6rem;
  }
</style>
