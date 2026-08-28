<!--
  @eden/primitives — Kbd (ADR-0024 / doc 17 §4 atoms).

  A keyboard-key cap — the `⌘K` affordance. Renders the native `<kbd>` element (the correct semantic
  element for keyboard input, announced as such), so it carries platform semantics with no aria
  override. The APPEARANCE is decided entirely by `deriveKbdTokens` (kbd/tokens.ts): every colour/
  size/space is a CSS custom property whose value is DERIVED from an @eden/theme token. This template
  carries NO literal colour and NO literal px — it references `var(--eden-kbd-*)` only.
-->
<script lang="ts">
  import type { Snippet } from 'svelte';
  import type { Theme } from '@eden/theme';
  import { defaultButtonTheme } from '../button/tokens.js';
  import { deriveKbdTokens, kbdStyleVars } from './tokens.js';

  interface KbdProps {
    /** The generated theme to derive tokens from; defaults to the C21 reference brand theme. */
    theme?: Theme;
    /** The key label — the glyph/word on the cap (e.g. `⌘K`, `Esc`, `↵`). */
    children: Snippet;
  }

  let { theme, children }: KbdProps = $props();

  const resolvedTheme = $derived(theme ?? defaultButtonTheme());
  const tokens = $derived(deriveKbdTokens(resolvedTheme));
  const styleVars = $derived(kbdStyleVars(tokens));
</script>

<kbd class="eden-kbd" data-eden-kbd="" style={styleVars}>
  {@render children()}
</kbd>

<style>
  /*
    Every value below is a CSS custom property whose VALUE is a derived @eden/theme token (emitted by
    kbdStyleVars). There is NO literal colour and NO literal px here.
  */
  .eden-kbd {
    display: inline-flex;
    align-items: center;
    justify-content: center;

    box-sizing: border-box;
    padding-inline: var(--eden-kbd-padding-inline);
    padding-block: var(--eden-kbd-padding-block);

    color: var(--eden-kbd-fg);
    background: var(--eden-kbd-bg);
    border: 1px solid var(--eden-kbd-border);
    border-radius: var(--eden-kbd-radius);

    font-family: var(--eden-kbd-font-family);
    font-size: var(--eden-kbd-font-size);
    line-height: var(--eden-kbd-line-height);
    font-weight: 600;
    white-space: nowrap;
  }
</style>
