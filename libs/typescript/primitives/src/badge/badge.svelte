<!--
  @eden/primitives — Badge (ADR-0024 / doc 17 §4 atoms).

  A status/count label — the health badge the Clusters north star reads (healthy/updating/degraded/
  down/unknown), plus the neutral/accent chrome variants. It renders a `<span>` carrying a WORD or a
  count, tinted from the theme's semantic role for the status. Colour is never the only channel: the
  Badge always shows text, so the status survives grayscale (doc 17 §1 triple-encoding). When it
  conveys status (not mere chrome), it carries `role="status"` so assistive tech announces the state.

  The APPEARANCE is decided entirely by `deriveBadgeTokens` (badge/tokens.ts): every colour/size/
  space is a CSS custom property whose value is DERIVED from an @eden/theme token via the shared
  surface-tokens/chat-surface vocabulary. This template carries NO literal colour and NO literal px —
  it references `var(--eden-badge-*)` only, so the design-correctness gate (contrast + scale
  provenance) is mechanical and the no-hand-set-hex provenance lint is green by construction.
-->
<script lang="ts">
  import type { Snippet } from 'svelte';
  import type { Theme } from '@eden/theme';
  import { defaultButtonTheme } from '../button/tokens.js';
  import { deriveBadgeTokens, badgeStyleVars, type BadgeVariant } from './tokens.js';

  interface BadgeProps {
    /** The status/chrome variant — a SELECTION of a theme semantic role (the Clusters vocabulary). */
    variant?: BadgeVariant;
    /** The generated theme to derive tokens from; defaults to the C21 reference brand theme. */
    theme?: Theme;
    /**
     * Whether this Badge conveys a live STATUS (adds `role="status"` so assistive tech announces the
     * state). Chrome badges (a plain count/label) leave it off so they are not over-announced.
     */
    status?: boolean;
    /** The label content — a status word or a count (always present: colour is never the only channel). */
    children: Snippet;
  }

  let { variant = 'neutral', theme, status = false, children }: BadgeProps = $props();

  const resolvedTheme = $derived(theme ?? defaultButtonTheme());
  const tokens = $derived(deriveBadgeTokens(variant, resolvedTheme));
  const styleVars = $derived(badgeStyleVars(tokens));
</script>

<span
  class="eden-badge"
  data-eden-badge=""
  data-variant={variant}
  role={status ? 'status' : undefined}
  style={styleVars}
>
  {@render children()}
</span>

<style>
  /*
    Every value below is a CSS custom property whose VALUE is a derived @eden/theme token (emitted by
    badgeStyleVars). There is NO literal colour and NO literal px here — the provenance lint and the
    design-correctness gate both rely on that.
  */
  .eden-badge {
    display: inline-flex;
    align-items: center;
    gap: var(--eden-badge-gap);

    box-sizing: border-box;
    padding-inline: var(--eden-badge-padding-inline);
    padding-block: var(--eden-badge-padding-block);

    color: var(--eden-badge-fg);
    background: var(--eden-badge-bg);
    border: 1px solid var(--eden-badge-border);
    border-radius: var(--eden-badge-radius);

    font-family: var(--eden-badge-font-family);
    font-size: var(--eden-badge-font-size);
    line-height: var(--eden-badge-line-height);
    font-weight: 600;
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
  }
</style>
