<script lang="ts">
  // A single link target rendered as a chip (doc 12 §5: links as navigable item
  // chips). An in-corpus item id (REQ-0001, CMP-0003, …) becomes an anchor to its
  // in-document item anchor; an external target (artifact://, path://) renders as
  // a plain, non-navigable chip. Navigation is same-page hash navigation — the
  // item anchors are emitted by every data item (doc 12 §5 item anchors).
  import { isItemId } from '$lib/documentModel';

  let { target }: { target: string } = $props();

  const navigable = $derived(isItemId(target));
</script>

{#if navigable}
  <a class="link-chip link-chip--item" href={`#item-${target}`} title={`Jump to ${target}`}>
    <code>{target}</code>
  </a>
{:else}
  <span class="link-chip link-chip--external" title="external reference (not an in-corpus item)">
    <code>{target}</code>
  </span>
{/if}

<style>
  .link-chip {
    display: inline-flex;
    align-items: center;
    text-decoration: none;
    border-radius: 6px;
  }
  .link-chip code {
    background: var(--chipbg);
    color: var(--accent);
    border-radius: 6px;
    padding: 0.1em 0.4em;
    font-size: 0.78em;
  }
  .link-chip--item:hover code {
    background: var(--accent);
    color: var(--color-text-on-surface);
  }
  .link-chip--external code {
    color: var(--muted);
    background: var(--codebg);
  }
</style>
