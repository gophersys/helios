<script lang="ts">
  // A fenced code block (doc 12 §5, REQ-0028: "fenced code with syntax
  // highlighting … code in JetBrains Mono on a Deep-Forest-tinted surface, with a
  // copy-button"). Highlighting is synchronous via highlight.js (lib/markdown/
  // highlight.ts), which emits semantic .hljs-* classes styled below from the Eden
  // tokens — no imported third-party color theme. The header carries the resolved
  // language label and the copy button; the button uses the Clipboard API with a
  // brief "Copied" confirmation, degrading silently where clipboard access is
  // denied.
  import { highlightCode } from '$lib/markdown/highlight';

  let { code, lang = '' }: { code: string; lang?: string } = $props();

  const highlighted = $derived(highlightCode(code, lang));

  let copied = $state(false);
  let resetTimer: ReturnType<typeof setTimeout> | undefined;

  async function copy(): Promise<void> {
    try {
      await navigator.clipboard.writeText(code);
      copied = true;
      clearTimeout(resetTimer);
      resetTimer = setTimeout(() => {
        copied = false;
      }, 1600);
    } catch {
      // Clipboard denied (insecure context, permission) — leave the button idle
      // rather than surfacing an error for a non-essential affordance.
    }
  }
</script>

<figure class="code-block">
  <figcaption class="code-block__bar">
    <span class="code-block__lang">{highlighted.label ?? 'text'}</span>
    <button
      type="button"
      class="code-block__copy"
      class:is-copied={copied}
      onclick={copy}
      aria-label="Copy code to clipboard"
    >
      {copied ? 'Copied' : 'Copy'}
    </button>
  </figcaption>
  <pre class="code-block__pre"><code class="code-block__code" data-language={highlighted.language}
      ><!-- eslint-disable-next-line svelte/no-at-html-tags — highlight.js escapes its source (highlight.ts) -->{@html highlighted.html}</code
    ></pre>
</figure>

<style>
  .code-block {
    margin: 1.4rem 0;
    border: 1px solid var(--code-border);
    border-radius: var(--radius);
    overflow: hidden;
    background: var(--code-surface);
  }
  .code-block__bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.4rem 0.7rem 0.4rem 0.9rem;
    background: var(--code-surface-bar);
    border-bottom: 1px solid var(--code-border);
  }
  .code-block__lang {
    font-family: var(--font-code);
    font-size: 0.68rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--code-bar-fg);
  }
  .code-block__copy {
    font-family: var(--font-code);
    font-size: 0.68rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    color: var(--code-bar-fg);
    background: transparent;
    border: 1px solid var(--code-border);
    border-radius: 6px;
    padding: 0.18rem 0.55rem;
    cursor: pointer;
    transition:
      background 0.12s ease,
      color 0.12s ease,
      border-color 0.12s ease;
  }
  .code-block__copy:hover {
    background: color-mix(in srgb, var(--color-moss) 30%, transparent);
    color: var(--color-bone);
    border-color: var(--color-moss);
  }
  .code-block__copy.is-copied {
    color: var(--color-bone);
    border-color: var(--color-moss);
    background: var(--color-moss);
  }
  .code-block__pre {
    margin: 0;
    padding: 0.95rem 1.1rem;
    overflow-x: auto;
  }
  .code-block__code {
    font-family: var(--font-code);
    font-size: 0.86rem;
    line-height: 1.6;
    /* The base code text color on the dark surface (Bone-tinted) — hljs spans
       override it per token below. The inline-code chip styling from +layout does
       not apply here (that targets bare <code>); this is block code. */
    color: var(--code-fg);
    background: none;
    padding: 0;
    border-radius: 0;
    display: block;
    white-space: pre;
    tab-size: 2;
  }

  /* highlight.js theme, Eden-token-driven (doc 12: "everything theme-token-driven").
     Deep-Forest surface; tokens painted in Sage/Moss/Bone derivatives so the code
     reads in the locked identity rather than an off-palette highlighter theme.
     :global because the spans are injected HTML, scoped under .code-block__code. */
  .code-block__code :global(.hljs-comment),
  .code-block__code :global(.hljs-quote) {
    color: var(--code-comment);
    font-style: italic;
  }
  .code-block__code :global(.hljs-keyword),
  .code-block__code :global(.hljs-selector-tag),
  .code-block__code :global(.hljs-literal),
  .code-block__code :global(.hljs-section),
  .code-block__code :global(.hljs-doctag),
  .code-block__code :global(.hljs-type),
  .code-block__code :global(.hljs-name),
  .code-block__code :global(.hljs-strong) {
    color: var(--code-keyword);
    font-weight: 600;
  }
  .code-block__code :global(.hljs-string),
  .code-block__code :global(.hljs-attr),
  .code-block__code :global(.hljs-attribute),
  .code-block__code :global(.hljs-meta-string),
  .code-block__code :global(.hljs-addition) {
    color: var(--code-string);
  }
  .code-block__code :global(.hljs-number),
  .code-block__code :global(.hljs-symbol),
  .code-block__code :global(.hljs-bullet),
  .code-block__code :global(.hljs-link),
  .code-block__code :global(.hljs-deletion) {
    color: var(--code-number);
  }
  .code-block__code :global(.hljs-title),
  .code-block__code :global(.hljs-title.function_),
  .code-block__code :global(.hljs-built_in),
  .code-block__code :global(.hljs-class .hljs-title) {
    color: var(--code-function);
  }
  .code-block__code :global(.hljs-variable),
  .code-block__code :global(.hljs-template-variable),
  .code-block__code :global(.hljs-property),
  .code-block__code :global(.hljs-params),
  .code-block__code :global(.hljs-meta) {
    color: var(--code-variable);
  }
  .code-block__code :global(.hljs-emphasis) {
    font-style: italic;
  }
</style>
