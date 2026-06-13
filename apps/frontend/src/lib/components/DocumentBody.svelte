<script lang="ts">
  // The Notion-grade markdown body renderer (doc 12 §5, REQ-0028). It consumes the
  // document projection's `sections` (markdown strings keyed by section id, the
  // frozen seam of ADR-0011 — it renders the projection, never re-reads files) and
  // renders each section as rich blocks via the token-tree dispatcher (BlockList).
  //
  // Two products come out of one lex pass per section: the rendered blocks, and a
  // document outline (the table-of-contents, REQ-0028 acceptance) built from the
  // headings — each outline entry deep-links to the heading's stable slug id, and
  // a shared slugger guarantees the ids the outline points at are exactly the ids
  // the headings render with. The reading column is held to a comfortable measure
  // (~70ch) with generous line-height (doc 12 §5).
  import type { Tokens } from 'marked';
  import { lexMarkdown, HeadingSlugger, headingPlainText, type Token } from '$lib/markdown/tokens';
  import { Scrollspy } from '$lib/scrollspy.svelte';
  import BlockList from './blocks/BlockList.svelte';

  let { sections }: { sections: Record<string, string> } = $props();

  interface RenderedSection {
    readonly key: string;
    readonly label: string;
    readonly tokens: Token[];
    readonly slugger: HeadingSlugger;
  }

  interface OutlineEntry {
    readonly id: string;
    readonly label: string;
    readonly depth: number;
  }

  // Humanize a section key (kebab heading id → title-case label), matching the
  // prior MarkdownSection behavior so section labels are unchanged.
  function sectionLabel(key: string): string {
    const spaced = key.replace(/[-_]/g, ' ');
    return spaced.charAt(0).toUpperCase() + spaced.slice(1);
  }

  // Lex every section once. Each section gets its own slugger so heading ids are
  // unique within a section and stable across renders; the same slugger instance
  // is handed to that section's BlockList so the rendered ids match the outline.
  const rendered = $derived.by<RenderedSection[]>(() =>
    Object.entries(sections ?? {}).map(([key, markdown]) => ({
      key,
      label: sectionLabel(key),
      tokens: lexMarkdown(markdown),
      slugger: new HeadingSlugger(),
    })),
  );

  // The outline: each section is a top-level entry (depth 0); its headings nest
  // beneath at their own depth. The slug is computed with a parallel slugger seeded
  // identically to the render's, so ids agree. Section ids are `section-<key>`
  // (unchanged from MarkdownSection) so existing in-page anchors still resolve.
  const outline = $derived.by<OutlineEntry[]>(() => {
    const entries: OutlineEntry[] = [];
    for (const section of rendered) {
      entries.push({ id: `section-${section.key}`, label: section.label, depth: 0 });
      const sl = new HeadingSlugger();
      for (const token of section.tokens) {
        if (token.type === 'heading') {
          const heading = token as Tokens.Heading;
          const label = headingPlainText(heading);
          entries.push({ id: sl.slug(label), label, depth: heading.depth });
        }
      }
    }
    return entries;
  });

  const hasOutline = $derived(outline.length > 1);

  // Scrollspy: highlight the outline entry whose section the reader is looking at
  // (REQ-0028 outline acceptance; doc 12 §5 reading mechanic). The spy observes the
  // in-page anchor elements by id; an $effect (re)registers them whenever the
  // outline changes — switching documents re-keys the whole body, so this also
  // tears down the previous document's observer. Server-side render has no DOM, so
  // the spy is inert until it runs in the browser.
  const spy = new Scrollspy();
  $effect(() => {
    spy.observe(outline.map((entry) => entry.id));
    return () => spy.disconnect();
  });

  // Smooth-scroll jump: clicking an outline link scrolls to the target and writes
  // the hash without the browser's default hard jump, so the scroll-margin offset
  // is honored and the active highlight tracks naturally. Falls through to the
  // default anchor behavior if the element is missing (defensive; ids always match).
  function jumpTo(event: MouseEvent, id: string): void {
    if (typeof document === 'undefined') return;
    const target = document.getElementById(id);
    if (!target) return;
    event.preventDefault();
    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    history.replaceState(history.state, '', `#${id}`);
    spy.activeId = id;
  }
</script>

<div class="document-body">
  {#if hasOutline}
    <nav class="document-body__outline" aria-label="Document outline">
      <p class="document-body__outline-title">On this page</p>
      <ul class="document-body__outline-list">
        {#each outline as entry (entry.id + entry.label)}
          <li
            class="document-body__outline-item"
            data-depth={Math.min(entry.depth, 4)}
            class:is-section={entry.depth === 0}
            class:is-active={spy.activeId === entry.id}
          >
            <a
              href={`#${entry.id}`}
              aria-current={spy.activeId === entry.id ? 'location' : undefined}
              onclick={(event) => jumpTo(event, entry.id)}>{entry.label}</a
            >
          </li>
        {/each}
      </ul>
    </nav>
  {/if}

  <div class="document-body__reading">
    {#each rendered as section (section.key)}
      <section class="document-body__section" id={`section-${section.key}`}>
        <h3 class="document-body__section-heading">{section.label}</h3>
        <div class="markdown-body">
          <BlockList tokens={section.tokens} slugger={section.slugger} />
        </div>
      </section>
    {/each}
  </div>
</div>

<style>
  /* The body lays the reading column beside a sticky outline on wide screens; the
     outline drops above the prose on narrow ones. */
  .document-body {
    display: grid;
    grid-template-columns: 1fr minmax(0, 15rem);
    gap: 2.5rem;
    align-items: start;
  }
  .document-body__reading {
    order: 1;
    min-width: 0;
  }

  /* The reading measure: ~70ch column, generous line-height (doc 12 §5). Inline
     element styling that all blocks share lives here so each block component stays
     lean. */
  .markdown-body {
    max-width: 72ch;
    font-size: 1.05rem;
    line-height: 1.72;
    color: var(--fg);
  }
  .markdown-body :global(a) {
    color: var(--accent);
    text-decoration: underline;
    text-underline-offset: 0.15em;
    text-decoration-thickness: 1px;
  }
  .markdown-body :global(a:hover) {
    text-decoration-thickness: 2px;
  }
  /* Inline code (not block code): a Sage-tinted chip in JetBrains Mono. */
  .markdown-body :global(code) {
    font-family: var(--font-code);
    font-size: 0.85em;
    background: var(--codebg);
    border-radius: 4px;
    padding: 0.12em 0.36em;
  }
  .markdown-body :global(strong) {
    font-weight: 700;
  }
  .markdown-body :global(em) {
    font-style: italic;
  }
  .markdown-body :global(del) {
    color: var(--muted);
  }

  .document-body__section {
    scroll-margin-top: 5rem;
    margin-bottom: 2.2rem;
  }
  .document-body__section:last-child {
    margin-bottom: 0;
  }
  /* The section label (the projection's section key) — a quiet Fraunces eyebrow
     above the section's own markdown headings, separated by a hairline. */
  .document-body__section-heading {
    font-family: var(--font-display);
    font-size: 1.5rem;
    font-weight: 600;
    letter-spacing: -0.012em;
    margin: 0 0 1rem;
    padding-bottom: 0.4rem;
    border-bottom: 1px solid var(--line);
    scroll-margin-top: 5rem;
  }

  /* The outline: sticky on the right, a quiet typed list of the document's
     structure. Indented by heading depth; the section rows read strongest. */
  .document-body__outline {
    order: 2;
    position: sticky;
    top: 1.4rem;
    align-self: start;
    font-size: 0.82rem;
    border-left: 1px solid var(--line);
    padding-left: 1rem;
    max-height: calc(100vh - 3rem);
    overflow-y: auto;
  }
  .document-body__outline-title {
    font-family: var(--font-text);
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--muted);
    margin: 0 0 0.6rem;
  }
  .document-body__outline-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.12rem;
  }
  .document-body__outline-item a {
    display: block;
    position: relative;
    color: var(--muted);
    text-decoration: none;
    padding: 0.18rem 0.4rem;
    border-radius: 5px;
    line-height: 1.35;
    transition:
      color 0.12s ease,
      background 0.12s ease;
  }
  .document-body__outline-item a:hover {
    color: var(--accent);
    background: color-mix(in srgb, var(--color-sage) 14%, transparent);
  }
  .document-body__outline-item.is-section a {
    color: var(--fg);
    font-weight: 600;
    margin-top: 0.35rem;
  }
  .document-body__outline-item.is-section:first-child a {
    margin-top: 0;
  }

  /* The active entry (scrollspy) — the section the reader is looking at. A Moss
     accent bar in the left rail's gutter plus a stronger label, so the eye finds
     its place in the outline without the row shouting (doc 12 §5 calm reading). */
  .document-body__outline-item.is-active a {
    color: var(--accent);
    font-weight: 600;
    background: color-mix(in srgb, var(--color-moss) 12%, transparent);
  }
  .document-body__outline-item.is-active a::before {
    content: '';
    position: absolute;
    left: calc(-1rem - 1px);
    top: 0.2rem;
    bottom: 0.2rem;
    width: 2px;
    border-radius: 2px;
    background: var(--accent);
  }
  .document-body__outline-item[data-depth='2'] a {
    padding-left: 1rem;
  }
  .document-body__outline-item[data-depth='3'] a {
    padding-left: 1.6rem;
  }
  .document-body__outline-item[data-depth='4'] a {
    padding-left: 2.2rem;
    font-size: 0.95em;
  }

  /* Narrow: single column, outline collapses to a quiet box above the prose. */
  @media (max-width: 1080px) {
    .document-body {
      grid-template-columns: 1fr;
      gap: 1.2rem;
    }
    .document-body__outline {
      order: 0;
      position: static;
      max-height: none;
      border-left: none;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      padding: 0.8rem 1rem;
      background: var(--navbg);
    }
    /* The left accent bar hangs in the rail gutter that the narrow box has no room
       for; the active row keeps its highlight without it. */
    .document-body__outline-item.is-active a::before {
      display: none;
    }
  }
</style>
