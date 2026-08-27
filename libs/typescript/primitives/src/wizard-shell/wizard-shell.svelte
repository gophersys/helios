<!--
  @eden/primitives — WizardShell (ADR-0024 / doc 17 §6 the wizard pattern).

  The FULL-SCREEN focus organism doc 17 §6 rules — NOT a modal. One question per screen: a thin top
  PROGRESS bar (fraction = the active step's index), a mono `1 / 3` COUNTER, the mono uppercase-tracked
  EYEBROW, the SERIF DISPLAY title at the LARGEST generated step, a one-sentence LEAD, a content region
  capped at a scale-derived reading MEASURE, and a FOOTER (the consumer's back/next/cancel buttons —
  the shell owns LAYOUT + the KEYBOARD CONTRACT, the consumer owns the button wiring).

  THE KEYBOARD CONTRACT (doc 17 §6): Enter advances (calls `onAdvance` — but ONLY when the consumer
  marks the active step `advanceable`, so a screen with an invalid field does not skip ahead, and Enter
  inside a textarea/select never hijacks). Escape calls `onExit` (the ruling's "Esc offers exit" — the
  shell fires the intent; the consumer renders the confirm). Focus is TRAPPED within the shell (Tab /
  Shift+Tab cycle the focusables, never escaping to the page behind), and the FIRST field auto-focuses
  via a slot-forwarded `autofocus` action the consumer places on its first input.

  THE APPEARANCE is decided entirely by `deriveWizardShellTokens` (wizard-shell/tokens.ts): every
  color/size/space is a CSS custom property whose value is DERIVED from an @eden/theme token, and the
  progress-fill transition rides the theme's motion slice (reduced-motion honored below). This template
  carries NO literal color and NO literal px — it references `var(--eden-wizard-shell-*)` only.

  THE APP MIGRATION SEAM: the root spreads `...rest` so the CONSUMER can put `data-testid` /
  `data-step` (and any attribute) on the rendered root — these are load-bearing in the app's e2e. The
  internal type classes are the audit-sampled vocabulary `.eyebrow` / `.screen__title` / `.lead` (the
  SAME names CreateProjectFlow / SetupWizard used), so the app's UI-math audits keep sampling >0 nodes.
-->
<script lang="ts">
  import type { Snippet } from 'svelte';
  import { tick } from 'svelte';
  import type { Theme } from '@eden/theme';
  import { defaultButtonTheme } from '../button/tokens.js';
  import {
    deriveWizardShellTokens,
    wizardShellStyleVars,
    wizardProgressFraction,
    type WizardStep,
  } from './tokens.js';

  interface WizardShellProps {
    /** The ordered step metadata — one entry per screen (the progress-bar length). */
    steps: readonly WizardStep[];
    /** The active step id — selects which step's copy + progress fraction render. */
    active: string;
    /** The generated theme to derive tokens from; defaults to the C21 reference brand theme. */
    theme?: Theme;
    /**
     * Whether the active step may advance on Enter. The shell fires {@link onAdvance} on Enter ONLY
     * when this is true — so a screen with an invalid field, or a still-thinking step, does not skip
     * ahead. Defaults to `true` (the common single-input screen).
     */
    advanceable?: boolean;
    /** Enter-advance intent — fired when Enter is pressed on an advanceable step (doc 17 §6). */
    onAdvance?: () => void;
    /** Escape-exit intent — fired on Escape ("Esc offers exit"; the consumer renders the confirm). */
    onExit?: () => void;
    /** The step BODY (the single input / editable cards) — the consumer renders the screen content. */
    body: Snippet<[{ autofocus: (node: HTMLElement) => void }]>;
    /** The FOOTER actions (back / next / cancel — the consumer's Eden Buttons; the shell lays out). */
    footer?: Snippet;
    /** The accessible label for the wizard region (screen-reader only; defaults to "Setup wizard"). */
    label?: string;
    /** Pass-through attributes (data-testid / data-step / any attr) spread onto the rendered root. */
    [key: string]: unknown;
  }

  let {
    steps,
    active,
    theme,
    advanceable = true,
    onAdvance,
    onExit,
    body,
    footer,
    label = 'Setup wizard',
    ...rest
  }: WizardShellProps = $props();

  const resolvedTheme = $derived(theme ?? defaultButtonTheme());
  const tokens = $derived(deriveWizardShellTokens(resolvedTheme));

  // The active step's index → the progress fraction (index / (count − 1)); an unknown id reads as the
  // first step (index 0, an empty bar) rather than throwing — a total, defensive lookup.
  const activeIndex = $derived(
    Math.max(
      0,
      steps.findIndex((s) => s.id === active),
    ),
  );
  const activeStep = $derived(steps[activeIndex]);
  const fraction = $derived(wizardProgressFraction(activeIndex, steps.length));
  const styleVars = $derived(wizardShellStyleVars(tokens, fraction));

  // The `1 / 3` mono counter — 1-based (a human reads "step one of three"), the active index + 1.
  const counter = $derived(`${String(activeIndex + 1)} / ${String(steps.length)}`);

  // A stable id base per instance for the region↔title link (SSR-consistent Svelte 5 rune).
  const uid = $props.id();
  const titleId = $derived(`eden-wizard-shell-${uid}-title`);

  let rootEl: HTMLElement | undefined = $state();

  /** The slot-forwarded first-field focus action: the consumer places `use:autofocus` on its first
   *  input. On mount (after the DOM settles) it focuses that node — so a wizard step lands with the
   *  cursor in the question's answer, no click required (doc 17 §6 "a single input"). */
  function autofocus(node: HTMLElement): void {
    // The step body is (re)mounted per active step, so the action runs once per screen — `tick` waits
    // for the render to settle before moving focus (the trap's tabbables must exist first).
    void tick().then(() => {
      node.focus();
    });
  }

  /** The tabbable elements INSIDE the shell, in DOM order — the focus-trap cycle set. */
  function tabbables(): HTMLElement[] {
    if (!rootEl) return [];
    const selector =
      'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), ' +
      'textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
    return Array.from(rootEl.querySelectorAll<HTMLElement>(selector)).filter(
      (el) => el.offsetParent !== null || el === document.activeElement,
    );
  }

  /** Whether the Enter keypress should be swallowed to advance: only for single-line targets. A
   *  textarea (multi-line) and a select keep native Enter; a plain input / button / the surface
   *  itself advance. This is the "Enter advances" contract without hijacking multi-line editing. */
  function isAdvanceTarget(target: EventTarget | null): boolean {
    if (!(target instanceof HTMLElement)) return true;
    const tag = target.tagName;
    if (tag === 'TEXTAREA' || tag === 'SELECT') return false;
    // an Enter on a real button is the button's own activation — let it through (don't double-fire).
    if (tag === 'BUTTON') return false;
    return true;
  }

  function onKeydown(event: KeyboardEvent): void {
    if (event.key === 'Escape') {
      event.preventDefault();
      onExit?.();
      return;
    }
    if (event.key === 'Enter' && !event.shiftKey && isAdvanceTarget(event.target)) {
      if (advanceable) {
        event.preventDefault();
        onAdvance?.();
      }
      return;
    }
    if (event.key === 'Tab') {
      const cycle = tabbables();
      const first = cycle[0];
      const last = cycle[cycle.length - 1];
      if (!first || !last) {
        // nothing focusable inside — keep focus on the surface so it never escapes to the page.
        event.preventDefault();
        rootEl?.focus();
        return;
      }
      const activeEl = document.activeElement;
      if (event.shiftKey && (activeEl === first || activeEl === rootEl)) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && activeEl === last) {
        event.preventDefault();
        first.focus();
      }
    }
  }
</script>

<!--
  The full-viewport focus surface. role="dialog" + aria-modal marks it as the focus context (the
  keyboard trap is enforced above); aria-labelledby names it by the step title. tabindex="-1" lets the
  surface itself hold focus (the trap's fallback + the reduced-motion static anchor). `...rest` spreads
  the consumer's data-testid / data-step (the app-migration seam).
-->
<section
  bind:this={rootEl}
  class="eden-wizard-shell"
  data-eden-wizard-shell=""
  role="dialog"
  aria-modal="true"
  aria-labelledby={titleId}
  aria-label={label}
  tabindex="-1"
  style={styleVars}
  onkeydown={onKeydown}
  {...rest}
>
  <!-- The THIN top progress bar: a track with a scaleX-transformed fill (fraction = the step index).
       aria-hidden — the mono counter carries the same information to the a11y tree, so the bar is a
       purely visual reinforcement (no double announcement). -->
  <div class="eden-wizard-shell-progress" aria-hidden="true">
    <div class="eden-wizard-shell-progress-fill"></div>
  </div>

  <div class="eden-wizard-shell-frame">
    <!-- The header row: the mono eyebrow + the mono `1 / 3` counter (the data voice, P-D4). -->
    <header class="eden-wizard-shell-head">
      {#if activeStep?.eyebrow}
        <p class="eyebrow">{activeStep.eyebrow}</p>
      {:else}
        <span></span>
      {/if}
      <p class="eden-wizard-shell-counter" aria-label={`Step ${counter}`}>{counter}</p>
    </header>

    <!-- The content region, capped at the scale-derived reading measure. -->
    <div class="eden-wizard-shell-content">
      <h1 class="screen__title" id={titleId}>{activeStep?.title ?? ''}</h1>
      {#if activeStep?.lead}
        <p class="lead">{activeStep.lead}</p>
      {/if}
      <div class="eden-wizard-shell-body">
        {@render body({ autofocus })}
      </div>
    </div>

    {#if footer}
      <footer class="eden-wizard-shell-footer">
        {@render footer()}
      </footer>
    {/if}
  </div>
</section>

<style>
  /*
    Every value below is a CSS custom property whose VALUE is a derived @eden/theme token (emitted by
    wizardShellStyleVars). There is NO literal color and NO literal px here — the provenance lint and
    the design-correctness gate both rely on that. The three type classes (.eyebrow / .screen__title /
    .lead) are the audit-sampled vocabulary the app's UI-math audits sample — adopted as the shell's
    own class names so the migration keeps sampling >0 nodes.
  */
  .eden-wizard-shell {
    position: fixed;
    inset: 0;
    z-index: 20;

    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    align-items: center;

    color: var(--eden-wizard-shell-title);
    background: var(--eden-wizard-shell-surface);
  }

  .eden-wizard-shell:focus-visible {
    outline: none;
  }

  /* ── the THIN top progress bar (doc 17 §6) ── */
  .eden-wizard-shell-progress {
    inline-size: 100%;
    block-size: var(--eden-wizard-shell-bar-thickness);
    background: color-mix(in oklab, var(--eden-wizard-shell-track) 24%, transparent);
    overflow: hidden;
  }

  .eden-wizard-shell-progress-fill {
    block-size: 100%;
    inline-size: 100%;
    /* the fraction is a scaleX multiplier: 0 at the first step (empty), 1 at the last (full). The
       transform-origin is the leading edge so the fill GROWS from the start. */
    transform-origin: left center;
    transform: scaleX(var(--eden-wizard-shell-progress));
    background: var(--eden-wizard-shell-fill);
    border-radius: 0 var(--eden-wizard-shell-bar-radius) var(--eden-wizard-shell-bar-radius) 0;
    transition: transform var(--eden-wizard-shell-transition) var(--eden-wizard-shell-easing);
  }

  /* ── the centered focus frame, capped at the reading measure (a focus moment gets air, §5) ── */
  .eden-wizard-shell-frame {
    inline-size: 100%;
    max-inline-size: var(--eden-wizard-shell-measure);
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: var(--eden-wizard-shell-gap);
    padding: var(--eden-wizard-shell-gutter);
  }

  .eden-wizard-shell-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: var(--eden-wizard-shell-gap);
  }

  /* the eyebrow — the MONO uppercase-tracked accent overline (the data voice). */
  .eyebrow {
    margin: 0;
    color: var(--eden-wizard-shell-accent);
    font-family: var(--eden-wizard-shell-mono-font-family);
    font-size: var(--eden-wizard-shell-mono-font-size);
    line-height: var(--eden-wizard-shell-mono-line-height);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }

  /* the `1 / 3` counter — the MONO data datum (Chip/Kbd-class vocabulary). */
  .eden-wizard-shell-counter {
    margin: 0;
    color: var(--eden-wizard-shell-accent);
    font-family: var(--eden-wizard-shell-mono-font-family);
    font-size: var(--eden-wizard-shell-mono-font-size);
    line-height: var(--eden-wizard-shell-mono-line-height);
    font-variant-numeric: tabular-nums;
    letter-spacing: 0.04em;
  }

  .eden-wizard-shell-content {
    display: flex;
    flex-direction: column;
    gap: var(--eden-wizard-shell-gap);
  }

  /* the SERIF DISPLAY title at the LARGEST generated step (the identity moment, doc 17 §6). */
  .screen__title {
    margin: 0;
    color: var(--eden-wizard-shell-title);
    font-family: var(--eden-wizard-shell-title-font-family);
    font-size: var(--eden-wizard-shell-title-font-size);
    line-height: var(--eden-wizard-shell-title-line-height);
    font-weight: 600;
    letter-spacing: -0.015em;
    text-wrap: balance;
  }

  /* the one-sentence helper — the SANS body-large voice (the interface voice, never mixed, P-D4). */
  .lead {
    margin: 0;
    max-inline-size: 60ch;
    color: var(--eden-wizard-shell-lead);
    font-family: var(--eden-wizard-shell-lead-font-family);
    font-size: var(--eden-wizard-shell-lead-font-size);
    line-height: var(--eden-wizard-shell-lead-line-height);
  }

  .eden-wizard-shell-body {
    margin-block-start: var(--eden-wizard-shell-gap);
  }

  .eden-wizard-shell-footer {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: var(--eden-wizard-shell-gap);
    margin-block-start: var(--eden-wizard-shell-gap);
  }

  /* reduced-motion: the fill snaps to its fraction with NO transition (a STATIC bar), honoring the
     user's preference — the progress information stays (the fill still reflects the fraction), only
     the animated growth is removed. */
  @media (prefers-reduced-motion: reduce) {
    .eden-wizard-shell-progress-fill {
      transition: none;
    }
  }
</style>
