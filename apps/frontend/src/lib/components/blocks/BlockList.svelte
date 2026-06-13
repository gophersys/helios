<script lang="ts">
  // The block dispatcher: render an ordered array of marked block tokens, each as
  // its own Svelte block component (doc 12 §5). This is the heart of the
  // token-tree-to-components approach — no opaque {@html} of a whole document, so
  // every block (heading, code, callout, table, list, mermaid) is a real,
  // individually-styled component. The dispatcher is recursive: callouts and list
  // items hold nested block tokens and render them back through here.
  //
  // Headings need stable slug ids shared with the outline. A slugger is threaded
  // from the top-level section render (DocumentBody) so the ids match the outline;
  // nested contexts (a heading inside a callout) get a fresh local slugger so they
  // still receive ids without polluting the document outline.
  import type { Token, Tokens } from 'marked';
  import { HeadingSlugger, readCallout, headingPlainText } from '$lib/markdown/tokens';
  import Heading from './Heading.svelte';
  import Paragraph from './Paragraph.svelte';
  import CodeBlock from './CodeBlock.svelte';
  import MermaidDiagram from './MermaidDiagram.svelte';
  import Callout from './Callout.svelte';
  import MarkdownList from './MarkdownList.svelte';
  import MarkdownTable from './MarkdownTable.svelte';
  import RichText from './RichText.svelte';

  let { tokens, slugger }: { tokens: Token[]; slugger?: HeadingSlugger } = $props();

  // The slugger actually used: the threaded one (outline-shared) or a local fallback
  // so nested headings still get ids. Created once per component instance.
  const localSlugger = new HeadingSlugger();
  const activeSlugger = $derived(slugger ?? localSlugger);

  // Pre-resolve heading ids in document order so each Heading renders with the same
  // id the outline computed. Keyed by the heading token's raw text + position.
  const headingIds = $derived.by(() => {
    const sl = activeSlugger;
    const ids = new Map<Token, string>();
    for (const token of tokens) {
      if (token.type === 'heading') {
        ids.set(token, sl.slug(headingPlainText(token as Tokens.Heading)));
      }
    }
    return ids;
  });

  function isMermaid(token: Tokens.Code): boolean {
    return (token.lang ?? '').trim().toLowerCase() === 'mermaid';
  }
</script>

{#each tokens as token, index (index)}
  {#if token.type === 'heading'}
    {@const heading = token as Tokens.Heading}
    <Heading depth={heading.depth} text={heading.text} id={headingIds.get(token) ?? ''} />
  {:else if token.type === 'paragraph'}
    <Paragraph text={(token as Tokens.Paragraph).text} />
  {:else if token.type === 'code'}
    {@const code = token as Tokens.Code}
    {#if isMermaid(code)}
      <MermaidDiagram code={code.text} />
    {:else}
      <CodeBlock code={code.text} lang={code.lang ?? ''} />
    {/if}
  {:else if token.type === 'blockquote'}
    {@const quote = token as Tokens.Blockquote}
    {@const callout = readCallout(quote)}
    <Callout kind={callout.kind} title={callout.title} tokens={quote.tokens} />
  {:else if token.type === 'list'}
    <MarkdownList token={token as Tokens.List} />
  {:else if token.type === 'table'}
    <MarkdownTable token={token as Tokens.Table} />
  {:else if token.type === 'hr'}
    <hr class="md-rule" />
  {:else if token.type === 'html'}
    <!-- eslint-disable-next-line svelte/no-at-html-tags — trusted first-party corpus (doc 11) -->
    {@html (token as Tokens.HTML).text}
  {:else if token.type === 'text'}
    <!-- A loose text token (e.g. inside a list item handled here): render inline. -->
    <RichText text={(token as Tokens.Text).text} />
  {/if}
  <!-- 'space' and unknown tokens render nothing; spacing is handled by block margins. -->
{/each}

<style>
  .md-rule {
    border: none;
    border-top: 1px solid var(--line);
    margin: 2rem 0;
  }
</style>
