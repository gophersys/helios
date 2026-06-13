<script lang="ts">
  // Global shell for @eden/frontend (the development spine, ADR-0015). The presentation
  // layer (doc 12) specifies the IA this app grows into; v0 establishes the token system
  // and the layout chrome, then renders a single page. The design tokens below are derived
  // from documents/design-system/tokens.json (the F6 design-system artifact, intake C21) —
  // Eden's locked visual identity — and mirror docs/tools/render-html.mjs so the static
  // reading copies and the Svelte app are the same aesthetic at two fidelities (doc 12 §7).
  //
  // Three families, three roles, locked: Fraunces (display/headings), Inter (text/body),
  // JetBrains Mono (code/chips/micro-labels). Imported as variable fonts so the full weight
  // axis is available to the type scale.
  import '@fontsource-variable/fraunces';
  import '@fontsource-variable/inter';
  import '@fontsource-variable/jetbrains-mono';

  let { children } = $props();
</script>

<div class="eden-app">
  {@render children()}
</div>

<style>
  /* Eden design tokens (documents/design-system/tokens.json) — light-first, with a dark
     variant derived from the SAME five colors behind prefers-color-scheme: dark. The named
     set mirrors docs/tools/render-html.mjs (the static reading copies) so the Svelte app and
     the static renders share one palette (doc 12 §7), extended with panel/chip-status tokens
     for the presentation-layer surfaces (status chips, panels — doc 12 §5).

     The five source colors:
       Bone        #F4F1E8  background / text on dark
       Ink         #1A1A1A  text on light
       Deep Forest #243D2C  primary surface
       Moss        #5C7F5C  signature accent
       Sage        #A8B89C  soft support
     Everything below resolves to one of these five (or a token-derived alpha of one). */
  :global(:root) {
    /* Raw palette (the five locked colors) */
    --color-bone: #f4f1e8;
    --color-ink: #1a1a1a;
    --color-deep-forest: #243d2c;
    --color-moss: #5c7f5c;
    --color-sage: #a8b89c;

    /* Semantic roles (tokens.json §semantic) */
    --color-background: var(--color-bone);
    --color-text: var(--color-ink);
    --color-surface-primary: var(--color-deep-forest);
    --color-text-on-surface: var(--color-bone);
    --color-accent: var(--color-moss);
    --color-support: var(--color-sage);

    /* Type families (tokens.json §font) — three roles, locked. */
    --font-display: 'Fraunces Variable', Fraunces, Georgia, serif;
    --font-text: 'Inter Variable', Inter, -apple-system, 'Segoe UI', sans-serif;
    --font-code: 'JetBrains Mono Variable', 'JetBrains Mono', 'SF Mono', ui-monospace, monospace;

    /* Type scale (tokens.json §typography), clamp()ed down for screen sanity. The display
       sizes hold their character on large screens but never blow out a narrow viewport. */
    --type-display-1: clamp(3.5rem, 8vw, 6rem); /* 96px */
    --type-display-2: clamp(2.75rem, 6vw, 4rem); /* 64px */
    --type-heading-1: clamp(2rem, 4vw, 2.5rem); /* 40px */
    --type-heading-2: clamp(1.5rem, 3vw, 1.75rem); /* 28px */
    --type-lead: 1.5rem; /* 24px */
    --type-body: 1.125rem; /* 18px */
    --type-caption: 0.875rem; /* 14px */
    --type-micro: 0.75rem; /* 12px */
    --type-code: 1rem; /* 16px */

    /* Derived working tokens — every value below is one of the five colors or a token-derived
       alpha, never a new hue. (--fg/--bg/--accent etc. are the names the components consume.) */
    --bg: var(--color-background);
    --fg: var(--color-text);
    --muted: color-mix(in srgb, var(--color-ink) 58%, var(--color-bone));
    --line: color-mix(in srgb, var(--color-ink) 14%, var(--color-bone));
    --accent: var(--color-accent);
    --chipbg: color-mix(in srgb, var(--color-sage) 32%, var(--color-bone));
    --codebg: color-mix(in srgb, var(--color-sage) 20%, var(--color-bone));
    --quote: color-mix(in srgb, var(--color-sage) 16%, var(--color-bone));
    --navbg: color-mix(in srgb, var(--color-sage) 12%, var(--color-bone));
    --th: color-mix(in srgb, var(--color-sage) 22%, var(--color-bone));

    /* Panel surfaces (doc 12 §4 panels around the project model). */
    --panel-bg: color-mix(in srgb, var(--color-bone) 92%, white);
    --panel-line: color-mix(in srgb, var(--color-ink) 14%, var(--color-bone));
    --panel-shadow:
      0 1px 2px color-mix(in srgb, var(--color-ink) 8%, transparent),
      0 1px 3px color-mix(in srgb, var(--color-ink) 6%, transparent);

    /* Status-chip palette (doc 12 §5: draft · review · approved · superseded), mapped onto the
       five tokens per the locked identity:
         draft       (tone "warn")  → Sage      — soft support
         review      (tone "info")  → Moss      — accent / in-progress
         approved    (tone "ok")    → Deep Forest surface, Bone text
         superseded  (tone "muted") → Ink at reduced opacity
       The tone names (warn/info/ok/muted) are the existing abstraction in documentModel.ts;
       only the colors they resolve to change. */
    --chip-fg: var(--muted);
    --chip-neutral-bg: color-mix(in srgb, var(--color-sage) 28%, var(--color-bone));
    --chip-neutral-fg: var(--color-ink);
    /* review → Moss */
    --chip-info-bg: color-mix(in srgb, var(--color-moss) 22%, var(--color-bone));
    --chip-info-fg: var(--color-deep-forest);
    /* approved → Deep Forest surface, Bone text */
    --chip-ok-bg: var(--color-deep-forest);
    --chip-ok-fg: var(--color-bone);
    /* draft → Sage */
    --chip-warn-bg: color-mix(in srgb, var(--color-sage) 50%, var(--color-bone));
    --chip-warn-fg: var(--color-deep-forest);
    /* superseded → Ink at reduced opacity */
    --chip-muted-bg: color-mix(in srgb, var(--color-ink) 8%, var(--color-bone));
    --chip-muted-fg: color-mix(in srgb, var(--color-ink) 55%, var(--color-bone));

    /* Tier accents (doc 11 §2 tiers). The identity locks one accent (Moss); the three tiers
       are differentiated by depth along the same Sage→Moss→Deep-Forest axis, no new hues. */
    --tier-product: var(--color-deep-forest);
    --tier-architecture: var(--color-moss);
    --tier-implementation: color-mix(in srgb, var(--color-sage) 70%, var(--color-ink));

    --radius: 8px;
    --radius-chip: 999px;

    /* Role-bound family aliases the components already reference. */
    --font-sans: var(--font-text);
    --font-mono: var(--font-code);
  }

  /* Dark variant — derived from the SAME five tokens (intake C21 / task): Ink background,
     Deep-Forest surfaces, Bone text, Moss accent, Sage support. No colors outside the five. */
  @media (prefers-color-scheme: dark) {
    :global(:root) {
      --color-background: var(--color-ink);
      --color-text: var(--color-bone);
      --color-surface-primary: var(--color-deep-forest);
      --color-text-on-surface: var(--color-bone);
      --color-accent: var(--color-moss);
      --color-support: var(--color-sage);

      --bg: var(--color-ink);
      --fg: var(--color-bone);
      --muted: color-mix(in srgb, var(--color-bone) 56%, var(--color-ink));
      --line: color-mix(in srgb, var(--color-bone) 16%, var(--color-ink));
      --accent: color-mix(in srgb, var(--color-moss) 72%, var(--color-bone));
      --chipbg: color-mix(in srgb, var(--color-deep-forest) 70%, var(--color-ink));
      --codebg: color-mix(in srgb, var(--color-bone) 6%, var(--color-ink));
      --quote: color-mix(in srgb, var(--color-deep-forest) 35%, var(--color-ink));
      --navbg: color-mix(in srgb, var(--color-deep-forest) 22%, var(--color-ink));
      --th: color-mix(in srgb, var(--color-deep-forest) 45%, var(--color-ink));

      --panel-bg: color-mix(in srgb, var(--color-deep-forest) 18%, var(--color-ink));
      --panel-line: color-mix(in srgb, var(--color-bone) 16%, var(--color-ink));
      --panel-shadow:
        0 1px 2px color-mix(in srgb, black 40%, transparent),
        0 1px 3px color-mix(in srgb, black 30%, transparent);

      --chip-fg: var(--muted);
      --chip-neutral-bg: color-mix(in srgb, var(--color-deep-forest) 55%, var(--color-ink));
      --chip-neutral-fg: var(--color-bone);
      /* review → Moss */
      --chip-info-bg: color-mix(in srgb, var(--color-moss) 38%, var(--color-ink));
      --chip-info-fg: color-mix(in srgb, var(--color-sage) 75%, var(--color-bone));
      /* approved → Deep Forest surface, Bone text (already legible on the darker ground) */
      --chip-ok-bg: var(--color-deep-forest);
      --chip-ok-fg: var(--color-bone);
      /* draft → Sage */
      --chip-warn-bg: color-mix(in srgb, var(--color-sage) 30%, var(--color-ink));
      --chip-warn-fg: color-mix(in srgb, var(--color-sage) 80%, var(--color-bone));
      /* superseded → Bone at reduced opacity (the light-side "Ink reduced" inverted) */
      --chip-muted-bg: color-mix(in srgb, var(--color-bone) 8%, var(--color-ink));
      --chip-muted-fg: color-mix(in srgb, var(--color-bone) 52%, var(--color-ink));

      --tier-product: color-mix(in srgb, var(--color-sage) 55%, var(--color-bone));
      --tier-architecture: color-mix(in srgb, var(--color-moss) 60%, var(--color-bone));
      --tier-implementation: var(--color-sage);
    }
  }

  :global(*) {
    box-sizing: border-box;
  }

  :global(html) {
    scroll-behavior: smooth;
  }

  :global(body) {
    margin: 0;
    background: var(--bg);
    color: var(--fg);
    font-family: var(--font-text);
    font-size: var(--type-body);
    line-height: 1.65;
  }

  /* Headings in Fraunces (display role), the locked type scale. */
  :global(h1),
  :global(h2),
  :global(h3) {
    font-family: var(--font-display);
    font-weight: 600;
    line-height: 1.15;
  }
  :global(h1) {
    font-size: var(--type-heading-1);
    letter-spacing: -0.015em;
  }
  :global(h2) {
    font-size: var(--type-heading-2);
    font-weight: 400;
  }
  :global(h3) {
    font-size: var(--type-lead);
  }

  :global(a) {
    color: var(--accent);
  }

  :global(code) {
    font-family: var(--font-code);
    font-size: 0.84em;
    background: var(--codebg);
    border-radius: 4px;
    padding: 0.1em 0.35em;
  }

  /* Reusable presentation primitives, available app-wide.
     .panel — a bordered surface (doc 12 §4). */
  :global(.panel) {
    background: var(--panel-bg);
    border: 1px solid var(--panel-line);
    border-radius: var(--radius);
    box-shadow: var(--panel-shadow);
    padding: 1.2rem 1.4rem;
  }

  /* .chip — a status chip (doc 12 §5). Tone via .chip--{info,ok,warn,muted};
     default is neutral. Chips are micro-labels: JetBrains Mono, letterspaced, uppercase
     (tokens.json typography.micro). */
  :global(.chip) {
    display: inline-flex;
    align-items: center;
    gap: 0.35em;
    background: var(--chip-neutral-bg);
    color: var(--chip-neutral-fg);
    font-family: var(--font-code);
    font-size: var(--type-micro);
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    border-radius: var(--radius-chip);
    padding: 0.18rem 0.6rem;
    line-height: 1.4;
    white-space: nowrap;
  }
  :global(.chip--info) {
    background: var(--chip-info-bg);
    color: var(--chip-info-fg);
  }
  :global(.chip--ok) {
    background: var(--chip-ok-bg);
    color: var(--chip-ok-fg);
  }
  :global(.chip--warn) {
    background: var(--chip-warn-bg);
    color: var(--chip-warn-fg);
  }
  :global(.chip--muted) {
    background: var(--chip-muted-bg);
    color: var(--chip-muted-fg);
  }

  .eden-app {
    min-height: 100vh;
  }
</style>
