<script lang="ts">
  // Global shell for @eden/frontend — the Eden visual identity injected FROM THE MATH (ADR-0024).
  // The design tokens are no longer a hand-maintained palette: `generateTheme(C21_SEED)` expands
  // the five LOCKED C21 colors + three fonts (the SEEDS) into a complete, contrast-gated token set
  // (@eden/theme), emitted here as the `:root` custom-property substrate (`--color-*`, `--space-*`,
  // `--font-size-*`, `--duration-*`, `--ease-*`, `--z-*`). Every @eden/primitives component the
  // chat renders derives its color/size/space from these SAME tokens, so the app and its primitives
  // are one identity at one source of truth — MATH IS SOURCE OF TRUTH (C21).
  //
  // Three families, three roles, locked: Fraunces (display/headings), Inter (text/body),
  // JetBrains Mono (code/chips/micro-labels). Imported as variable fonts so the full weight axis is
  // available to the generated type scale.
  import '@fontsource-variable/fraunces';
  import '@fontsource-variable/inter';
  import '@fontsource-variable/jetbrains-mono';
  import { edenLightCss, edenDarkCss } from '$lib/theme/edenTheme';

  let { children } = $props();

  // The generated token substrate: the light `:root` block, then the dark block scoped under
  // prefers-color-scheme: dark (the SAME five seeds resolved for the dark surface, contrast-gated).
  // The font-family + the chrome aliases below are appended so the app shell reads off the math too.
  const themeCss = `${edenLightCss}
:root {
  --font-display: 'Fraunces Variable', Fraunces, Georgia, serif;
  --font-text: 'Inter Variable', Inter, -apple-system, 'Segoe UI', sans-serif;
  --font-code: 'JetBrains Mono Variable', 'JetBrains Mono', 'SF Mono', ui-monospace, monospace;

  /* App-chrome aliases — every value is one of the GENERATED role tokens (never a new hue). The
     chat shell (rails, chips, lines) reads these so the chrome and the primitives share one source. */
  --eden-app-bg: var(--color-surface);
  --eden-app-fg: var(--color-on-surface);
  --eden-app-muted: color-mix(in oklab, var(--color-on-surface) 58%, var(--color-surface));
  --eden-app-line: color-mix(in oklab, var(--color-on-surface) 14%, var(--color-surface));
  --eden-app-accent: var(--color-primary);
  --eden-app-rail-bg: color-mix(in oklab, var(--color-primary) 6%, var(--color-surface));
  --eden-app-panel-bg: var(--color-surface);
  --eden-app-panel-line: var(--color-outline);
  --eden-app-radius: var(--space-2);
}
@media (prefers-color-scheme: dark) {
${edenDarkCss}
}`;
</script>

<svelte:head>
  <!-- eslint-disable-next-line svelte/no-at-html-tags -->
  {@html `<style id="eden-theme">${themeCss}</style>`}
</svelte:head>

<div class="eden-app">
  {@render children()}
</div>

<style>
  :global(*) {
    box-sizing: border-box;
  }

  :global(html) {
    scroll-behavior: smooth;
  }

  :global(body) {
    margin: 0;
    background: var(--eden-app-bg);
    color: var(--eden-app-fg);
    font-family: var(--font-text);
    font-size: var(--font-size-body, 16px);
    line-height: var(--line-height-body, 1.56);
  }

  /* Headings in Fraunces (the display family seed); sizes come from the generated type scale. */
  :global(h1),
  :global(h2),
  :global(h3) {
    font-family: var(--font-display);
    font-weight: 600;
    line-height: 1.15;
    margin: 0;
  }
  :global(h1) {
    font-size: var(--font-size-headline, 28px);
    letter-spacing: -0.015em;
  }
  :global(h2) {
    font-size: var(--font-size-title, 23px);
    font-weight: 500;
  }
  :global(h3) {
    font-size: var(--font-size-body-large, 19px);
  }

  :global(a) {
    color: var(--color-primary);
  }

  .eden-app {
    min-height: 100vh;
  }
</style>
