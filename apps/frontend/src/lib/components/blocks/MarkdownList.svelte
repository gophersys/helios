<script lang="ts">
  // An ordered or unordered list with clean spacing (doc 12 §5: "lists (clean
  // spacing)"). Each item may be a simple inline string or hold nested block
  // content (loose lists, sub-lists, multi-paragraph items); the renderer recurses
  // through the block dispatcher in that case. GFM task-list checkboxes render as
  // disabled inputs. The `start` attribute is honored so an ordered list that does
  // not begin at 1 numbers correctly.
  import type { Tokens } from 'marked';
  import RichText from './RichText.svelte';
  import BlockList from './BlockList.svelte';

  let { token }: { token: Tokens.List } = $props();

  const start = $derived(
    typeof token.start === 'number' && token.start !== 1 ? token.start : undefined,
  );
</script>

{#if token.ordered}
  <ol class="md-list" {start}>
    {#each token.items as item, index (index)}
      <li class="md-list__item" class:has-blocks={item.tokens.some((t) => t.type !== 'text')}>
        {#if item.task}
          <input type="checkbox" checked={item.checked} disabled class="md-list__check" />
        {/if}
        {#if item.tokens.every((t) => t.type === 'text')}
          <RichText text={item.text} />
        {:else}
          <BlockList tokens={item.tokens} />
        {/if}
      </li>
    {/each}
  </ol>
{:else}
  <ul class="md-list" class:is-task={token.items.some((item) => item.task)}>
    {#each token.items as item, index (index)}
      <li class="md-list__item" class:is-task-item={item.task}>
        {#if item.task}
          <input type="checkbox" checked={item.checked} disabled class="md-list__check" />
        {/if}
        {#if item.tokens.every((t) => t.type === 'text')}
          <RichText text={item.text} />
        {:else}
          <BlockList tokens={item.tokens} />
        {/if}
      </li>
    {/each}
  </ul>
{/if}

<style>
  .md-list {
    margin: 0.9rem 0;
    padding-left: 1.5rem;
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
  }
  .md-list__item {
    line-height: 1.65;
    padding-left: 0.15rem;
  }
  .md-list__item::marker {
    color: var(--accent);
  }
  /* An item that carries nested blocks tightens those blocks' outer margins so the
     list stays visually a list, not a stack of full-bleed blocks. */
  .md-list__item.has-blocks :global(> :first-child) {
    margin-top: 0;
  }
  .md-list__item.has-blocks :global(> :last-child) {
    margin-bottom: 0;
  }
  .md-list__item.has-blocks :global(p) {
    margin: 0 0 0.4rem;
  }

  /* GFM task lists: no bullet, a checkbox hung at the left. */
  .md-list.is-task {
    list-style: none;
    padding-left: 0.2rem;
  }
  .md-list__item.is-task-item {
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
  }
  .md-list__check {
    accent-color: var(--accent);
    transform: translateY(1px);
  }
</style>
