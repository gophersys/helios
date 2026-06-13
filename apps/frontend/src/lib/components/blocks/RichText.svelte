<script lang="ts">
  // Render an inline markdown string (emphasis, strong, inline code, links,
  // strikethrough) to HTML. Headings, table cells, and list-item text all carry
  // their inline content as a raw string; marked.parseInline emits the inline HTML
  // synchronously. Inline scope is small and first-party (doc 11 corpus), so the
  // output is trusted; sanitization would belong here if this surface ever
  // rendered untrusted text. Inline element styling (code, links, em/strong) is
  // inherited from the .markdown-body scope in DocumentBody.svelte.
  import { marked } from 'marked';

  let { text }: { text: string } = $props();

  const html = $derived(marked.parseInline(text ?? '', { async: false, gfm: true }));
</script>

<!-- eslint-disable-next-line svelte/no-at-html-tags — trusted first-party corpus (doc 11) -->
{@html html}
