<script lang="ts">
  // A body paragraph (doc 12 §5: "paragraphs in Inter at comfortable body measure,
  // generous line-height"). The reading measure and line-height are set on the
  // .markdown-body column in DocumentBody.svelte; this component only carries the
  // inline content and the inter-paragraph rhythm.
  import RichText from './RichText.svelte';

  let { text }: { text: string } = $props();
</script>

<p class="md-paragraph"><RichText {text} /></p>

<style>
  .md-paragraph {
    margin: 0 0 1.05rem;
  }
</style>
