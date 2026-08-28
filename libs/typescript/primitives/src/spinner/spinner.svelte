<!--
  @eden/primitives — Spinner (ADR-0024 / doc 17 §4 atoms).

  The loading atom. A rotating conic arc over an idle track ring; the rotation PERIOD and EASING are
  the theme's motion tokens (never a hand-typed `1s`). `prefers-reduced-motion: reduce` suppresses
  the animation and holds the arc static — motion is opt-out by construction (doc 17 §5). The element
  carries `role="status"` + `aria-live="polite"` and a visually-hidden label so assistive tech
  announces "Loading" rather than a silent spinning box.

  The APPEARANCE is decided entirely by `deriveSpinnerTokens` (spinner/tokens.ts): every colour/size/
  duration is a CSS custom property whose value is DERIVED from an @eden/theme token. This template
  carries NO literal colour, NO literal px, and NO literal duration — it references
  `var(--eden-spinner-*)` only.
-->
<script lang="ts">
  import type { Theme } from '@eden/theme';
  import { defaultButtonTheme } from '../button/tokens.js';
  import { deriveSpinnerTokens, spinnerStyleVars, type SpinnerVariant } from './tokens.js';

  interface SpinnerProps {
    /** `accent` (the brand primary) or a status role — the arc colour. */
    variant?: SpinnerVariant;
    /** The generated theme to derive tokens from; defaults to the C21 reference brand theme. */
    theme?: Theme;
    /** The accessible label announced while loading (default "Loading"). */
    label?: string;
  }

  let { variant = 'accent', theme, label = 'Loading' }: SpinnerProps = $props();

  const resolvedTheme = $derived(theme ?? defaultButtonTheme());
  const tokens = $derived(deriveSpinnerTokens(variant, resolvedTheme));
  const styleVars = $derived(spinnerStyleVars(tokens));
</script>

<span
  class="eden-spinner"
  data-eden-spinner=""
  data-variant={variant}
  role="status"
  aria-live="polite"
  style={styleVars}
>
  <span class="eden-spinner-ring" aria-hidden="true"></span>
  <span class="eden-spinner-label">{label}</span>
</span>

<style>
  /*
    Every value below is a CSS custom property whose VALUE is a derived @eden/theme token (emitted by
    spinnerStyleVars). There is NO literal colour, px, or duration here.
  */
  .eden-spinner {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    inline-size: var(--eden-spinner-size);
    block-size: var(--eden-spinner-size);
  }

  .eden-spinner-ring {
    box-sizing: border-box;
    inline-size: var(--eden-spinner-size);
    block-size: var(--eden-spinner-size);
    border-radius: 50%;
    /* the idle track is the outline role; the active arc is one coloured edge of the same ring */
    border: var(--eden-spinner-stroke) solid var(--eden-spinner-track);
    border-block-start-color: var(--eden-spinner-arc);
    animation: eden-spinner-spin var(--eden-spinner-duration) var(--eden-spinner-easing) infinite;
  }

  @keyframes eden-spinner-spin {
    to {
      transform: rotate(360deg);
    }
  }

  /* Honor the user's reduced-motion preference: hold the arc static (no rotation). doc 17 §5. */
  @media (prefers-reduced-motion: reduce) {
    .eden-spinner-ring {
      animation: none;
    }
  }

  /* Visually-hidden label: read by assistive tech (role=status), invisible on screen. */
  .eden-spinner-label {
    position: absolute;
    inline-size: 1px;
    block-size: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip-path: inset(50%);
    white-space: nowrap;
    border: 0;
  }
</style>
