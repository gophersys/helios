<script lang="ts">
  // Render one document section's markdown (doc 11 §5: narrative documents carry
  // markdown sections with stable heading ids; doc 12 §5 renders them). marked
  // parses to HTML synchronously here (no async extensions), and the result is
  // scoped under .markdown so the token styles apply without leaking. The corpus
  // is first-party (Eden's own documents and the worked example), so the parsed
  // HTML is trusted; if this surface ever renders third-party document text, a
  // sanitizer belongs at this seam.
  import { marked } from 'marked';

  let { title, markdown }: { title: string; markdown: string } = $props();

  // Humanize the section key (kebab heading id → title-case label).
  const heading = $derived(
    title.replace(/[-_]/g, ' ').replace(/^\w/, (character) => character.toUpperCase()),
  );

  const html = $derived(
    marked.parse(markdown ?? '', { async: false, gfm: true, breaks: false }) as string,
  );
</script>

<section class="markdown-section">
  <h3 id={`section-${title}`} class="markdown-section__heading">{heading}</h3>
  <!-- eslint-disable-next-line svelte/no-at-html-tags — trusted first-party corpus -->
  <div class="markdown">{@html html}</div>
</section>

<style>
  .markdown-section {
    margin-bottom: 1.6rem;
  }
  .markdown-section__heading {
    font-size: 1.02rem;
    letter-spacing: -0.005em;
    margin: 0 0 0.5rem;
    padding-bottom: 0.3rem;
    border-bottom: 1px solid var(--line);
    scroll-margin-top: 5rem;
  }
  .markdown :global(p) {
    margin: 0 0 0.8rem;
  }
  .markdown :global(p:last-child) {
    margin-bottom: 0;
  }
  .markdown :global(ul),
  .markdown :global(ol) {
    margin: 0 0 0.8rem;
    padding-left: 1.4rem;
  }
  .markdown :global(li) {
    margin: 0.15rem 0;
  }
  .markdown :global(h1),
  .markdown :global(h2),
  .markdown :global(h3),
  .markdown :global(h4) {
    font-size: 0.98rem;
    margin: 1rem 0 0.4rem;
  }
  .markdown :global(blockquote) {
    margin: 0 0 0.8rem;
    padding: 0.4rem 0.9rem;
    border-left: 3px solid var(--line);
    background: var(--quote);
    color: var(--muted);
    border-radius: 0 var(--radius) var(--radius) 0;
  }
  .markdown :global(pre) {
    background: var(--codebg);
    border: 1px solid var(--line);
    border-radius: var(--radius);
    padding: 0.8rem 1rem;
    overflow-x: auto;
    font-size: 0.82rem;
  }
  .markdown :global(pre code) {
    background: none;
    padding: 0;
  }
  .markdown :global(table) {
    border-collapse: collapse;
    width: 100%;
    font-size: 0.86rem;
    margin: 0 0 0.8rem;
  }
  .markdown :global(th),
  .markdown :global(td) {
    border: 1px solid var(--line);
    padding: 0.4rem 0.6rem;
    text-align: left;
  }
  .markdown :global(th) {
    background: var(--th);
  }
</style>
