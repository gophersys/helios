<script lang="ts">
  // A blockquote rendered as a Notion-style callout card (doc 12 §5: "render
  // blockquotes, and `> [!NOTE]`/`> [!WARNING]`-style admonitions, into
  // Notion-style callout cards using Sage/Moss accents"). The kind is detected by
  // tokens.ts readCallout: a markerless blockquote is a 'quote'; an admonition
  // (note/tip/important/warning/caution) carries a titled header with an icon. The
  // body is the blockquote's inner block tokens, rendered through the same block
  // dispatcher (so a callout may itself hold lists, code, nested quotes). A small
  // glyph set keeps the card iconographic without a dependency.
  import type { CalloutKind } from '$lib/markdown/tokens';
  import type { Token } from 'marked';
  import BlockList from './BlockList.svelte';

  let { kind, title, tokens }: { kind: CalloutKind; title: string | null; tokens: Token[] } =
    $props();

  // A minimal inline glyph per kind (no icon dependency). quote uses a typographic
  // quotation mark; the admonitions use unambiguous symbols.
  const GLYPH: Record<CalloutKind, string> = {
    note: 'ℹ',
    tip: '✦',
    important: '◆',
    warning: '▲',
    caution: '⚠',
    quote: '“',
  };
</script>

<aside class="callout" data-kind={kind}>
  <span class="callout__glyph" aria-hidden="true">{GLYPH[kind]}</span>
  <div class="callout__body">
    {#if title}
      <p class="callout__title">{title}</p>
    {/if}
    <div class="callout__content" class:is-quote={kind === 'quote'}>
      <BlockList {tokens} />
    </div>
  </div>
</aside>

<style>
  .callout {
    display: flex;
    gap: 0.7rem;
    margin: 1.3rem 0;
    padding: 0.85rem 1.05rem;
    border-radius: var(--radius);
    border: 1px solid var(--callout-line);
    border-left: 3px solid var(--callout-accent);
    background: var(--callout-bg);
  }
  .callout__glyph {
    flex: none;
    font-size: 1rem;
    line-height: 1.6;
    color: var(--callout-accent);
  }
  .callout__body {
    min-width: 0;
    flex: 1;
  }
  .callout__title {
    margin: 0 0 0.25rem;
    font-family: var(--font-text);
    font-size: 0.74rem;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--callout-accent);
  }
  /* The callout body reuses the prose flow but tightens trailing margins so the
     card hugs its content. */
  .callout__content :global(> :last-child) {
    margin-bottom: 0;
  }
  .callout__content :global(p) {
    margin: 0 0 0.6rem;
  }
  .callout__content.is-quote :global(p) {
    font-style: italic;
    color: var(--callout-quote-fg);
  }

  /* Kind → accent, all from the locked five (Sage/Moss axis). Notes/tips/quotes
     read as soft support (Sage→Moss); warnings/caution carry the strongest accent
     (Deep Forest edge on a Sage-warm ground) — no off-palette red, honoring the
     identity (the strongest "alert" Eden has is depth of Moss, not a new hue). */
  .callout[data-kind='quote'] {
    --callout-accent: var(--color-sage);
    --callout-bg: var(--quote);
    --callout-line: var(--line);
    --callout-quote-fg: var(--muted);
  }
  .callout[data-kind='note'] {
    --callout-accent: var(--color-moss);
    --callout-bg: color-mix(in srgb, var(--color-sage) 14%, var(--bg));
    --callout-line: color-mix(in srgb, var(--color-moss) 22%, var(--bg));
  }
  .callout[data-kind='tip'] {
    --callout-accent: var(--color-moss);
    --callout-bg: color-mix(in srgb, var(--color-moss) 12%, var(--bg));
    --callout-line: color-mix(in srgb, var(--color-moss) 26%, var(--bg));
  }
  .callout[data-kind='important'] {
    --callout-accent: var(--color-deep-forest);
    --callout-bg: color-mix(in srgb, var(--color-sage) 20%, var(--bg));
    --callout-line: color-mix(in srgb, var(--color-deep-forest) 24%, var(--bg));
  }
  .callout[data-kind='warning'],
  .callout[data-kind='caution'] {
    --callout-accent: var(--color-deep-forest);
    --callout-bg: color-mix(in srgb, var(--color-sage) 30%, var(--bg));
    --callout-line: color-mix(in srgb, var(--color-deep-forest) 32%, var(--bg));
  }
  @media (prefers-color-scheme: dark) {
    .callout[data-kind='important'],
    .callout[data-kind='warning'],
    .callout[data-kind='caution'] {
      --callout-accent: var(--color-sage);
    }
  }
</style>
