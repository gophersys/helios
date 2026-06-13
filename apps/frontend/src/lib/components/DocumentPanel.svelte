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
  import DocumentHeader from './DocumentHeader.svelte';
  import MetaCard from './MetaCard.svelte';
  import DataValue from './DataValue.svelte';
  import DocumentBody from './DocumentBody.svelte';
  import ValidationBar from './ValidationBar.svelte';
  import { isItemId } from '$lib/documentModel';
  import type { Diagnostic, ProjectedDocument } from '$lib/server/validatorClient';
  import type { Backlink } from '../../routes/p/[slug]/+page.server';

  let {
    document,
    backlinks,
    validation,
    projectSlug,
    projectTitle,
  }: {
    document: ProjectedDocument;
    backlinks: Record<string, Backlink[]>;
    validation: {
      violations: Diagnostic[];
      coverage: Diagnostic[];
      ok: boolean;
      violationsExit: boolean;
    };
    projectSlug: string;
    projectTitle: string;
  } = $props();

  const dataEntries = $derived(Object.entries(document.data ?? {}));
  const hasSections = $derived(Object.keys(document.sections ?? {}).length > 0);

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

  // The document carries typed links worth a labeled card (the link graph + its
  // derived backlinks, doc 11 §3); the always-wanted identity line lives in the
  // header instead. Show the MetaCard only when there are links to show, so a
  // link-less document opens straight on its prose.
  const hasLinks = $derived(
    Object.values(document.meta.links ?? {}).some((value) =>
      Array.isArray(value) ? value.length > 0 : typeof value === 'string' && value.length > 0,
    ),
  );
</script>

<article class="document-panel">
  <DocumentHeader meta={document.meta} {projectSlug} {projectTitle} />

  <ValidationBar
    violations={validation.violations}
    coverage={validation.coverage}
    ok={validation.ok}
    violationsExit={validation.violationsExit}
    {activeIds}
  />

  {#if hasLinks}
    <MetaCard meta={document.meta} />
  {/if}

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

  {#if hasSections}
    <section class="document-panel__sections">
      <DocumentBody sections={document.sections} />
    </section>
  {/if}
</article>

<style>
  .document-panel {
    /* Wide enough to seat the reading column (capped at 72ch inside DocumentBody)
       beside the sticky outline rail; the meta/data blocks above stay within a
       comfortable measure via their own max-widths. */
    max-width: 72rem;
  }
  /* The header, validation banner, meta card, and data blocks share a comfortable
     measure narrower than the full panel (which widens only to seat the reading
     column beside its outline rail). */
  .document-panel :global(.document-header),
  .document-panel :global(.validation-bar),
  .document-panel__data,
  .document-panel :global(.meta-card) {
    max-width: 60rem;
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
