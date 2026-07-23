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

  /* App-chrome aliases — the older chat-internal chrome (rails, chips, lines, the Build view's dense
     working surfaces) reads these. As of the shadcn transposition they are RE-POINTED at the SHADCN
     SKIN MAPPING below (one concept, one home): every chat-internal consumer inherits the shadcn skin
     — the 1px subtle hairline, the muted surface/text tones, the --radius-md geometry — for free,
     with no per-component edit. Custom properties resolve at use-time, so the forward reference to
     the shadcn block (defined further down at this same :root) is well-defined. */
  --eden-app-bg: var(--background);
  --eden-app-fg: var(--foreground);
  --eden-app-muted: var(--muted-foreground);
  --eden-app-line: var(--border);
  --eden-app-accent: var(--primary);
  --eden-app-rail-bg: var(--surface-muted);
  --eden-app-panel-bg: var(--card);
  --eden-app-panel-line: var(--border);
  --eden-app-radius: var(--radius-md);

  /* ── SHADCN SKIN MAPPING (doc 17 §skin — the ratified shadcn transposition) ─────────────────
     The shadcn-svelte variable vocabulary, DERIVED from the generated @eden/theme role tokens —
     NOT a hand-authored palette. Every value below resolves to a var(--color-* / --space-*) mix,
     so the whole shadcn skin re-derives per mode (light↔dark flip for free, since --color-* are
     re-scoped under html[data-theme]) — this is the math-pipeline → skin proof (color + radius).
     Every surface styles against THESE names, so swapping the C21 seed or the mode re-paints the
     whole skin with no per-screen edits. (ADR-0024: math is source of truth; doc 17: honest chrome
     + type voices unchanged — only geometry/color/density are reskinned.)

     Surfaces: a zinc-neutral surface ladder built by mixing on-surface ink into surface — the
     shadcn "background / card / popover / muted" ramp, but sourced from the generated ink so the
     brand's warmth carries through (never a raw gray). The canvas sits a hair cooler/darker than
     pure surface so raised --card panels (at the brighter --color-surface) read as elevated — the
     shadcn light-theme separation trick, sourced from the generated ink. */
  --background: color-mix(in oklab, var(--color-on-surface) 3%, var(--color-surface));
  --foreground: var(--color-on-surface);
  --card: var(--color-surface);
  --card-foreground: var(--color-on-surface);
  --popover: var(--color-surface);
  --popover-foreground: var(--color-on-surface);
  /* NOTE: the shadcn surface-muted is named --surface-muted (NOT --muted) deliberately — the legacy
     MIGRATION BRIDGE below squats --muted as a mid-gray TEXT color for the legacy components, a
     genuinely different concept. Colliding on --muted would break one or the other. One concept,
     one home: the shadcn surface tone gets its own name here; the text tone is --muted-foreground. */
  --surface-muted: color-mix(in oklab, var(--color-on-surface) 4%, var(--color-surface));
  --muted-foreground: color-mix(in oklab, var(--color-on-surface) 52%, var(--color-surface));
  /* Accent = the shadcn subtle hover/selected tint (a whisper of primary on surface). */
  --accent-surface: color-mix(in oklab, var(--color-primary) 8%, var(--color-surface));
  --accent-surface-foreground: var(--color-on-surface);
  /* Primary action pair — the solid brand button (never washed out). */
  --primary: var(--color-primary);
  --primary-foreground: var(--color-on-primary);
  /* Destructive = the generated error role. */
  --destructive: var(--color-error);
  --destructive-foreground: var(--color-on-primary);
  /* Status surfaces — the shadcn subtle-tint pattern for info/success/warning, sourced from the
     generated status roles so callouts/pills read in-brand and re-derive per mode. */
  --success: var(--color-success);
  --warning: var(--color-warning);
  --info: var(--color-info);
  --success-surface: color-mix(in oklab, var(--color-success) 12%, var(--color-surface));
  --warning-surface: color-mix(in oklab, var(--color-warning) 14%, var(--color-surface));
  --info-surface: color-mix(in oklab, var(--color-info) 12%, var(--color-surface));
  --destructive-surface: color-mix(in oklab, var(--color-error) 12%, var(--color-surface));
  /* Hairlines: the shadcn 1px subtle border ramp + the slightly stronger input edge + focus ring. */
  --border: color-mix(in oklab, var(--color-on-surface) 9%, var(--color-surface));
  --border-strong: color-mix(in oklab, var(--color-on-surface) 15%, var(--color-surface));
  --input: color-mix(in oklab, var(--color-on-surface) 13%, var(--color-surface));
  --ring: color-mix(in oklab, var(--color-primary) 55%, var(--color-surface));
  /* Radius scale — the shadcn geometry. The base is --radius-md (NOT --radius: the legacy bridge
     below squats --radius at --space-2 ~ 8px for the legacy component world; a distinct name keeps
     both intact — one concept, one home). sm/lg/xl are the shadcn geometry ladder steps. */
  --radius-md: 10px;
  --radius-sm: 7px;
  --radius-lg: 14px;
  --radius-xl: 18px;
  /* Shadow ramp — the refined shadcn elevation ladder, tinted with the generated ink (not pure
     black) so shadows read in the brand rather than as a hard drop. */
  --shadow-xs: 0 1px 2px 0 color-mix(in oklab, var(--color-on-surface) 6%, transparent);
  --shadow-sm:
    0 1px 2px 0 color-mix(in oklab, var(--color-on-surface) 7%, transparent),
    0 1px 3px 0 color-mix(in oklab, var(--color-on-surface) 5%, transparent);
  --shadow-md:
    0 2px 4px -1px color-mix(in oklab, var(--color-on-surface) 7%, transparent),
    0 4px 12px -2px color-mix(in oklab, var(--color-on-surface) 9%, transparent);
  --shadow-lg:
    0 8px 16px -4px color-mix(in oklab, var(--color-on-surface) 10%, transparent),
    0 16px 32px -8px color-mix(in oklab, var(--color-on-surface) 12%, transparent);
  /* ── end SHADCN SKIN MAPPING ─────────────────────────────────────────────────────────────── */

  /* ── MIGRATION BRIDGE (doc 17 §2/§3) ───────────────────────────────────────────────────────
     An entire legacy component world (src/lib/components/ + blocks/ + /p/[slug]) styles itself
     with custom properties that were DEFINED NOWHERE — they only rendered via fallbacks or not at
     all. This block aliases each ONE-WAY onto real tokens so that world renders coherently in BOTH
     themes without touching the components.

     SHADCN TRANSPOSITION — bridge retirement (the verdict's productionization item): the base
     ink/ground/accent/hairline/geometry tokens are now RE-POINTED at the SHADCN SKIN MAPPING above,
     so the legacy /p/[slug] document-world inherits the shadcn skin (1px subtle hairline, muted
     text tone, --radius-md geometry) for free — the reach we can retire SAFELY without editing the
     17 legacy consumers (src/lib/components/**, /p/[slug]). The legacy --muted IS a text tone, so it
     maps to the shadcn --muted-foreground (NOT the shadcn --surface-muted, a surface — one concept,
     one home, exactly the collision the spike flagged); legacy --radius (8px) maps to --radius-md.

     WHAT REMAINS (cannot be re-pointed to a shadcn painted role — these are semantic DOCUMENT-RENDER
     tokens, not chrome the reskin governs): the fenced-code surface ramp (--code-*, --codebg), the
     quote/chip tints (--quote, --chipbg, --chip-*), the table header wash (--th, --navbg), the C21
     named-brand seeds (--color-deep-forest/moss/sage/bone), and the SDLC tier accents (--tier-*).
     They still derive one-way from generated @eden role tokens (never a new hue). Full retirement =
     migrating the 17 legacy consumers to the shadcn vocabulary directly (doc 17 §9 /p/[slug] ruling,
     a later wave) — out of scope for the visual reskin. Do not extend this block; migrate consumers. */

  /* Base ink/ground/accent + geometry — RE-POINTED at the shadcn skin (bridge retirement). */
  --fg: var(--foreground);
  --bg: var(--background);
  --muted: var(--muted-foreground);
  --accent: var(--primary);
  --line: var(--border);
  --radius: var(--radius-md);
  --navbg: var(--surface-muted);
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

  /* Table + chip + tier accents. The table header wash aligns to the shadcn --surface-muted. */
  --th: var(--surface-muted);
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
