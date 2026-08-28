<!--
  @eden/primitives — ThinkingBlock (ADR-0024 / RD-16). The collapsible reasoning surface: the
  assistant's intermediate thinking behind a disclosure. The APPEARANCE is decided entirely by
  deriveThinkingBlockTokens (thinking-block/tokens.ts) — every colour/size/space is a CSS custom
  property whose value is DERIVED from an @eden/theme token; this template references
  var(--eden-thinking-block-*) only and carries NO literal colour and NO literal px.

  The disclosure BEHAVIOUR (open/close, aria-expanded, the content region wiring, keyboard) is
  delegated to the bits-ui Collapsible primitive — the RD-16/OD-1 ratified behaviour layer. The
  trigger carries the decoupled 44px AAA hit target so the toggle is always a real tap area, and the
  summary is a visible word ("Thinking") so the affordance is never icon/colour alone (WCAG 1.4.1).
-->
<script lang="ts">
  import { Collapsible } from 'bits-ui';
  import type { Snippet } from 'svelte';
  import type { Theme } from '@eden/theme';
  import { generateTheme, C21_SEED } from '@eden/theme';
  import { deriveThinkingBlockTokens, thinkingBlockStyleVars } from './tokens.js';

  interface ThinkingBlockProps {
    /** The disclosure summary word/phrase (defaults to "Thinking"). */
    summary?: string;
    /** Whether the block starts expanded (defaults to collapsed — thinking is an opt-in aside). */
    open?: boolean;
    /** The generated theme to derive tokens from; defaults to the C21 reference brand theme. */
    theme?: Theme;
    /** The reasoning content. */
    children: Snippet;
  }

  let { summary = 'Thinking', open = false, theme, children }: ThinkingBlockProps = $props();

  const resolvedTheme = $derived(theme ?? generateTheme(C21_SEED));
  const tokens = $derived(deriveThinkingBlockTokens(resolvedTheme));
  const styleVars = $derived(thinkingBlockStyleVars(tokens));
</script>

<Collapsible.Root {open}>
  <div class="eden-thinking-block" data-eden-thinking-block="" style={styleVars}>
    <Collapsible.Trigger class="eden-thinking-block-trigger">
      <span class="eden-thinking-block-summary">{summary}</span>
    </Collapsible.Trigger>
    <Collapsible.Content class="eden-thinking-block-content">
      <div class="eden-thinking-block-prose">
        {@render children()}
      </div>
    </Collapsible.Content>
  </div>
</Collapsible.Root>

<style>
  .eden-thinking-block {
    box-sizing: border-box;
    padding: var(--eden-thinking-block-padding);
    border-radius: var(--eden-thinking-block-radius);
    color: var(--eden-thinking-block-fg);
    background: var(--eden-thinking-block-bg);
    border: 1px solid var(--eden-thinking-block-border);
  }

  /* The trigger is rendered by the bits-ui Collapsible.Trigger (a real <button>); it lives inside the
     component so Svelte's scoped hash is not on it — :global is the deliberate, correct scope. */
  :global(.eden-thinking-block-trigger) {
    display: inline-flex;
    align-items: center;
    /* the hard a11y constraint: the toggle never falls below the theme's decoupled hit target. */
    min-block-size: var(--eden-thinking-block-hit-target);
    min-inline-size: var(--eden-thinking-block-hit-target);
    padding: 0;
    color: var(--eden-thinking-block-fg);
    background: transparent;
    border: none;
    font-size: var(--eden-thinking-block-summary-size);
    line-height: var(--eden-thinking-block-summary-line-height);
    font-family: var(--eden-thinking-block-summary-family);
    font-weight: 600;
    cursor: pointer;
  }

  :global(.eden-thinking-block-trigger:focus-visible) {
    outline: 2px solid var(--eden-thinking-block-fg);
    outline-offset: 2px;
  }

  .eden-thinking-block-prose {
    margin-block-start: var(--eden-thinking-block-gap);
    font-size: var(--eden-thinking-block-prose-size);
    line-height: var(--eden-thinking-block-prose-line-height);
    font-family: var(--eden-thinking-block-prose-family);
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }
</style>
