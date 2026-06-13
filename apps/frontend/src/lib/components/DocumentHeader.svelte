<script lang="ts">
  // The document header block (doc 12 §2 "where am I" view altitudes; REQ-0028
  // typographic hierarchy). Three parts, top to bottom:
  //   · breadcrumbs — Project / Tier / Document — the unbroken trail of doc 12 §2,
  //     so a reader always knows their altitude (founder calm, engineer precise);
  //   · the title — Fraunces, display-large — the document's human name;
  //   · a single meta line — type · version · status chip · updated · authors —
  //     the at-a-glance provenance (doc 11 §4), folded into one quiet row rather
  //     than a separate card, so the page opens on the prose, not on metadata.
  // The richer link graph (typed edges + derived backlinks) stays in MetaCard below
  // the prose; this header carries only the always-wanted identity line.
  import StatusChip from './StatusChip.svelte';
  import { documentTitle, tierOf, TIERS } from '$lib/documentModel';
  import type { DocumentMeta } from '$lib/server/validatorClient';

  let {
    meta,
    projectSlug,
    projectTitle,
  }: {
    meta: DocumentMeta;
    projectSlug: string;
    projectTitle: string;
  } = $props();

  const title = $derived(documentTitle(meta));

  // The tier this document belongs to (Product / Architecture / Implementation,
  // doc 11 §2) for the middle breadcrumb segment.
  const tierKey = $derived(tierOf(meta.type));
  const tierLabel = $derived(TIERS.find((tier) => tier.key === tierKey)?.label ?? tierKey);

  // Author display strings: {run: …} → "run …", {human: …} → the name (doc 11 §4
  // provenance). Kept to a short inline list in the meta line.
  const authors = $derived(
    (meta.authors ?? []).map((author) => {
      if (typeof author.human === 'string') return author.human;
      if (typeof author.run === 'string') return `run ${author.run}`;
      return Object.values(author).map(String).join(' ');
    }),
  );
  const authorLine = $derived(authors.join(', '));
</script>

<header class="document-header">
  <nav class="document-header__crumbs" aria-label="Breadcrumb">
    <a href="/">Projects</a>
    <span class="document-header__sep" aria-hidden="true">/</span>
    <a href={`/p/${projectSlug}`}>{projectTitle}</a>
    <span class="document-header__sep" aria-hidden="true">/</span>
    <span class="document-header__crumb-tier document-header__crumb-tier--{tierKey}">
      {tierLabel}
    </span>
    <span class="document-header__sep" aria-hidden="true">/</span>
    <span class="document-header__crumb-current" aria-current="page">{title}</span>
  </nav>

  <h1 class="document-header__title">{title}</h1>

  <div class="document-header__meta">
    <code class="document-header__type">{meta.type}</code>
    <span class="document-header__dot" aria-hidden="true">·</span>
    <StatusChip status={meta.status} version={meta.version} />
    {#if meta.updated}
      <span class="document-header__dot" aria-hidden="true">·</span>
      <span class="document-header__updated">updated {meta.updated}</span>
    {/if}
    {#if authors.length > 0}
      <span class="document-header__dot" aria-hidden="true">·</span>
      <span class="document-header__authors">{authorLine}</span>
    {/if}
  </div>
</header>

<style>
  .document-header {
    margin-bottom: 1.6rem;
  }

  /* Breadcrumb — the always-present "where am I" trail (doc 12 §2). Quiet by
     default; the tier segment carries its tier accent; the current document is the
     only emphasized segment. */
  .document-header__crumbs {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.4rem;
    font-size: 0.82rem;
    color: var(--muted);
    margin-bottom: 1rem;
  }
  .document-header__crumbs a {
    color: var(--muted);
    text-decoration: none;
    transition: color 0.12s ease;
  }
  .document-header__crumbs a:hover {
    color: var(--accent);
  }
  .document-header__sep {
    opacity: 0.45;
  }
  .document-header__crumb-tier {
    font-weight: 600;
  }
  .document-header__crumb-tier--product {
    color: var(--tier-product);
  }
  .document-header__crumb-tier--architecture {
    color: var(--tier-architecture);
  }
  .document-header__crumb-tier--implementation {
    color: var(--tier-implementation);
  }
  .document-header__crumb-current {
    color: var(--fg);
    font-weight: 600;
  }

  /* Title — Fraunces display, large (tokens.json typography.heading-1). */
  .document-header__title {
    font-family: var(--font-display);
    font-size: clamp(2rem, 4.5vw, 2.75rem);
    font-weight: 600;
    line-height: 1.1;
    letter-spacing: -0.018em;
    margin: 0 0 0.7rem;
    color: var(--fg);
  }

  /* Meta line — one quiet row of provenance (doc 11 §4). The dots are hairline
     separators; the status chip is the only color. */
  .document-header__meta {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.86rem;
    color: var(--muted);
  }
  .document-header__type {
    font-family: var(--font-code);
    font-size: 0.8rem;
    color: var(--muted);
    background: var(--codebg);
    border-radius: 5px;
    padding: 0.1em 0.45em;
  }
  .document-header__dot {
    opacity: 0.5;
  }
  .document-header__updated {
    font-variant-numeric: tabular-nums;
  }
  .document-header__authors {
    color: var(--fg);
  }
</style>
