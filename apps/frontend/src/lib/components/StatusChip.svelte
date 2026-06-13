<script lang="ts">
  // A document status chip (doc 12 §5): the lifecycle status (draft · review ·
  // approved · superseded) rendered in the palette shared with
  // render-documents.mjs, optionally followed by the document version. Tone is
  // derived from the status so the colour is always consistent with the word.
  import { statusTone } from '$lib/documentModel';

  let { status, version = null }: { status: string; version?: number | null } = $props();

  const tone = $derived(statusTone(status));
</script>

<span class="status-chip chip chip--{tone}">
  <span class="status-chip__label">{status}</span>
  {#if version !== null}
    <span class="status-chip__version">v{version}</span>
  {/if}
</span>

<style>
  /* The status word inherits the .chip micro-label treatment (JetBrains Mono,
     letterspaced, uppercase — tokens.json typography.micro). */
  .status-chip__version {
    opacity: 0.7;
    font-variant-numeric: tabular-nums;
  }
</style>
