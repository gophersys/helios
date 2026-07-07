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
  import { onMount } from 'svelte';
  import { edenLightCss, edenDarkCss } from '$lib/theme/edenTheme';
  import { themePreference } from '$lib/theme/themePreference.svelte';

  let { children } = $props();

  // The dark token BLOCK CONTENTS without the wrapping `:root { … }` — the generator emits a
  // `:root { … }` block; we re-scope its declarations under several selectors below so an explicit
  // choice (html[data-theme='dark']) and OS-driven 'system' (the media query) both resolve.
  const darkBody = edenDarkCss.replace(/^:root\s*\{/, '').replace(/\}\s*$/, '');

  // The generated token substrate, emitted under an ATTRIBUTE strategy so the ThemeProvider store
  // (themePreference.svelte) can switch modes by writing/removing <html data-theme> (doc 17 §3):
  //
  //   · LIGHT tokens at :root AND html[data-theme='light']  — the default and the explicit light pick.
  //   · DARK tokens at html[data-theme='dark']              — the explicit dark pick, always wins.
  //   · DARK tokens under @media (prefers-color-scheme: dark), scoped html:not([data-theme='light'])
  //     — 'system' (no attribute) follows the OS; an explicit light choice opts OUT of it.
  //
  // The font-family + the app-chrome aliases + the legacy-token MIGRATION BRIDGE (doc 17) live at
  // :root once (theme-agnostic references to the role tokens above), so they re-resolve per mode.
  const themeCss = `${edenLightCss}
html[data-theme='light'] {
${edenLightCss.replace(/^:root\s*\{/, '').replace(/\}\s*$/, '')}}
html[data-theme='dark'] {
${darkBody}}
@media (prefers-color-scheme: dark) {
  html:not([data-theme='light']) {
${darkBody}  }
}
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

  /* ── MIGRATION BRIDGE (doc 17 §2/§3) ───────────────────────────────────────────────────────
     An entire legacy component world (src/lib/components/ + blocks/ + /p/[slug]) styles itself
     with custom properties that were DEFINED NOWHERE — they only rendered via fallbacks or not at
     all. This block aliases each ONE-WAY onto the real generated @eden role tokens so that world
     renders coherently in BOTH themes without touching the components. Every value here is a
     var(--color-* / --space-*) — never a new hue or px. This block DIES when that world migrates
     to real tokens directly (doc 17 §9, a later wave: W-UI-4 surfaces / the /p[slug] ruling). Do
     not extend it; migrate the consumer instead. */

  /* Base ink/ground/accent + geometry. */
  --fg: var(--color-on-surface);
  --bg: var(--color-surface);
  --muted: color-mix(in oklab, var(--color-on-surface) 55%, var(--color-surface));
  --accent: var(--color-primary);
  --line: color-mix(in oklab, var(--color-on-surface) 14%, var(--color-surface));
  --radius: var(--space-2);
  --navbg: color-mix(in oklab, var(--color-primary) 6%, var(--color-surface));
  --quote: color-mix(in oklab, var(--color-primary) 8%, var(--color-surface));
  --codebg: color-mix(in oklab, var(--color-primary) 10%, var(--color-surface));
  --chipbg: color-mix(in oklab, var(--color-primary) 12%, var(--color-surface));

  /* The C21 named brand seeds the legacy world referenced directly — mapped onto their role
     tokens (deep-forest/moss are the accent, sage is the accent container, bone is on-primary). */
  --color-deep-forest: var(--color-primary);
  --color-moss: var(--color-primary);
  --color-sage: var(--color-primary-container);
  --color-bone: var(--color-on-primary);
  --color-text-on-surface: var(--color-on-surface);

  /* Table + chip + tier accents. */
  --th: color-mix(in oklab, var(--color-on-surface) 5%, var(--color-surface));
  --chip-info-bg: color-mix(in oklab, var(--color-info) 12%, var(--color-surface));
  --chip-warn-fg: var(--color-warning);
  --tier-product: var(--color-primary);
  --tier-architecture: var(--color-info);
  --tier-implementation: var(--color-secondary);

  /* The fenced-code surface (doc 12: "Deep-Forest-tinted surface", syntax in Sage/Moss/Bone).
     A primary-tinted panel; the hljs token hues ride the status/role ramp so code reads in the
     locked identity in either theme. */
  --code-surface: color-mix(in oklab, var(--color-primary) 9%, var(--color-surface));
  --code-surface-bar: color-mix(in oklab, var(--color-primary) 14%, var(--color-surface));
  --code-border: color-mix(in oklab, var(--color-primary) 22%, var(--color-surface));
  --code-bar-fg: color-mix(in oklab, var(--color-on-surface) 60%, var(--color-surface));
  --code-fg: var(--color-on-surface);
  --code-comment: color-mix(in oklab, var(--color-on-surface) 48%, var(--color-surface));
  --code-keyword: var(--color-primary);
  --code-string: var(--color-success);
  --code-number: var(--color-warning);
  --code-function: var(--color-info);
  --code-variable: var(--color-error);
  /* ── end MIGRATION BRIDGE ──────────────────────────────────────────────────────────────── */
}`;

  // On mount, reconcile the store's runtime authority with whatever the app.html inline bootstrap
  // wrote pre-hydration (both read the 'eden-theme' key, so this is normally a no-op — it just
  // guarantees <html data-theme> matches the persisted preference).
  onMount(() => themePreference.sync());
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
