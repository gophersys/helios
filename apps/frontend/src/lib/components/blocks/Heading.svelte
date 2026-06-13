<script lang="ts">
  // A section heading (h1–h4) in Fraunces with a stable id and a §-anchor that
  // appears on hover (doc 12 §5: "anchor links on hover, stable ids"). The id is
  // the slug computed once per section by the renderer (tokens.ts HeadingSlugger),
  // so the outline and the on-hover anchor link to the same target. depth maps
  // 1→h2, 2→h3, … so a document's section markdown nests *under* the panel's own
  // h2 title without competing with it for the h1/h2 visual rank.
  import RichText from './RichText.svelte';

  let { depth, text, id }: { depth: number; text: string; id: string } = $props();

  // Clamp to h2–h5 (depth 1–4 in source → one level down) so document headings sit
  // beneath the panel title; anything deeper renders as the smallest heading.
  const level = $derived(Math.min(Math.max(depth + 1, 2), 5));
  const href = $derived(`#${id}`);
</script>

<svelte:element this={`h${level}`} {id} class="md-heading" data-level={level}>
  <a class="md-heading__anchor" {href} aria-label="Link to this section" tabindex="-1">§</a>
  <span class="md-heading__text"><RichText {text} /></span>
</svelte:element>

<style>
  .md-heading {
    position: relative;
    font-family: var(--font-display);
    line-height: 1.2;
    letter-spacing: -0.012em;
    scroll-margin-top: 5rem;
    margin: 2rem 0 0.7rem;
  }
  .md-heading:first-child {
    margin-top: 0;
  }
  /* The display type scale, one level down from the page title (doc 12 §5,
     tokens.json typography). h2 leads a section; h5 is the smallest sub-heading. */
  .md-heading[data-level='2'] {
    font-size: 1.7rem;
    font-weight: 600;
  }
  .md-heading[data-level='3'] {
    font-size: 1.32rem;
    font-weight: 600;
  }
  .md-heading[data-level='4'] {
    font-size: 1.1rem;
    font-weight: 600;
  }
  .md-heading[data-level='5'] {
    font-size: 0.98rem;
    font-weight: 600;
    color: var(--muted);
  }

  /* The §-anchor: hidden until the heading is hovered/focused, hung in the left
     margin so it never reflows the heading text. Moss accent. */
  .md-heading__anchor {
    position: absolute;
    left: -1.1em;
    top: 0;
    color: var(--accent);
    text-decoration: none;
    font-weight: 400;
    opacity: 0;
    transition: opacity 0.12s ease;
    padding-right: 0.3em;
  }
  .md-heading:hover .md-heading__anchor,
  .md-heading:focus-within .md-heading__anchor,
  .md-heading__anchor:focus {
    opacity: 1;
  }
  .md-heading__anchor:hover {
    text-decoration: underline;
  }

  @media (max-width: 760px) {
    /* No left margin to hang the anchor in on narrow screens; show it inline-left. */
    .md-heading__anchor {
      position: static;
      opacity: 0.5;
      margin-right: 0.25em;
    }
  }
</style>
