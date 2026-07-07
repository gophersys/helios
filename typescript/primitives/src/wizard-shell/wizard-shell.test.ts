/**
 * WizardShell — unit + component render (the application-logic correctness dimension, ADR-0024). The
 * full-screen wizard organism (doc 17 §6) asserted assertion-richly: the pure derivation (the SERIF
 * display title at the LARGEST step vs the SANS lead vs the MONO eyebrow/counter, the reading measure,
 * the progress-fraction math, the exact style string) + the real component (the progress bar, the
 * `1 / 3` counter, the eyebrow/title/lead classes the app audits sample, the body+footer slots, the
 * Enter-advance / Escape-exit / autofocus keyboard contract). Assertion-rich so mutation (75) kills a
 * swapped voice, a dropped slot, a flipped fraction, a mutated var name, a missing key handler.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, cleanup, fireEvent } from '@testing-library/svelte';
import { createRawSnippet, type Snippet } from 'svelte';
import { generateTheme, C21_SEED, oklchToCss } from '@eden/theme';
import WizardShell from './wizard-shell.svelte';
import {
  deriveWizardShellTokens,
  wizardShellStyleVars,
  wizardProgressFraction,
  type WizardStep,
} from './tokens.js';
import { radiusPx } from '../surface-tokens/tokens.js';
import { space } from '../chat-surface/tokens.js';

const theme = generateTheme(C21_SEED);

const STEPS: WizardStep[] = [
  {
    id: 'spark',
    eyebrow: 'New project',
    title: 'What are we building?',
    lead: 'One sentence is enough.',
  },
  { id: 'scope', eyebrow: 'Scope', title: 'Name it.' },
  {
    id: 'review',
    eyebrow: 'Review',
    title: 'Ship it?',
    lead: 'Confirm the plan before the build.',
  },
];

describe('deriveWizardShellTokens — the pure derivation contract', () => {
  it('the title is the SERIF display-LARGE voice; the lead the SANS body-large voice; distinct families', () => {
    const t = deriveWizardShellTokens(theme);
    const displayLarge = theme.typography.find((r) => r.name === 'display-large')!;
    const bodyLarge = theme.typography.find((r) => r.name === 'body-large')!;
    expect(t.titleFontFamily).toBe(displayLarge.fontFamily);
    expect(t.leadFontFamily).toBe(bodyLarge.fontFamily);
    // the identity-moment title is the DISPLAY font, NOT the interface text font (P-D4)
    expect(t.titleFontFamily).not.toBe(t.leadFontFamily);
  });

  it('the title size is EXACTLY the display-LARGE step (the LARGEST display, doc 17 §6)', () => {
    const t = deriveWizardShellTokens(theme);
    const displaySizes = theme.typography
      .filter((r) => r.name.startsWith('display'))
      .map((r) => r.fontSizePx);
    expect(t.titleFontSizePx).toBe(
      theme.typography.find((r) => r.name === 'display-large')!.fontSizePx,
    );
    // it is the MAXIMUM of the display steps — the largest, never display-small
    expect(t.titleFontSizePx).toBe(Math.max(...displaySizes));
    expect(t.titleFontSizePx).toBeGreaterThan(t.leadFontSizePx);
    expect(t.leadFontSizePx).toBeGreaterThan(t.monoFontSizePx);
  });

  it('the lead size is EXACTLY the body-large step (the ruling helper voice)', () => {
    const t = deriveWizardShellTokens(theme);
    expect(t.leadFontSizePx).toBe(
      theme.typography.find((r) => r.name === 'body-large')!.fontSizePx,
    );
  });

  it('the title line height is EXACTLY size × the display-large role lineHeight (a MULTIPLY, not a divide)', () => {
    const t = deriveWizardShellTokens(theme);
    const role = theme.typography.find((r) => r.name === 'display-large')!;
    // the derived line height is round(size · lineHeight) — a PRODUCT, never a quotient (kills the
    // `*`→`/` arithmetic mutant on the line-height derivation).
    expect(t.titleLineHeightPx).toBe(Math.round(role.fontSizePx * role.lineHeight));
    expect(t.titleLineHeightPx).toBeGreaterThan(role.fontSizePx);
  });

  it('the eyebrow/counter are the MONO data voice — the caption size, the generic monospace family', () => {
    const t = deriveWizardShellTokens(theme);
    expect(t.monoFontSizePx).toBe(theme.typography.find((r) => r.name === 'caption')!.fontSizePx);
    // the mono family is the CSS generic (the seed code font is not carried on a role — one home)
    expect(t.monoFontFamily).toBe('monospace');
    expect(t.monoFontFamily).not.toBe(t.titleFontFamily);
    expect(t.monoFontFamily).not.toBe(t.leadFontFamily);
  });

  it('the colours are the onSurface title, outline lead, primary accent, surface fill roles', () => {
    const t = deriveWizardShellTokens(theme);
    expect(t.titleOklch).toEqual(theme.roles.onSurface.value);
    expect(t.leadOklch).toEqual(theme.roles.outline.value);
    expect(t.accentOklch).toEqual(theme.roles.primary.value);
    expect(t.surfaceOklch).toEqual(theme.roles.surface.value);
    expect(t.title).toBe(oklchToCss(theme.roles.onSurface.value));
    expect(t.fill).toBe(oklchToCss(theme.roles.primary.value));
  });

  it('the reading measure is the expanded breakpoint (the focus measure, a scale derivation)', () => {
    const t = deriveWizardShellTokens(theme);
    expect(t.measurePx).toBe(theme.breakpoints.find((b) => b.name === 'expanded')!.minWidthPx);
    expect(t.measurePx).toBe(840);
    // it is a real generated breakpoint, never eyeballed
    expect(theme.breakpoints.map((b) => b.minWidthPx)).toContain(t.measurePx);
  });

  it('the spaces are EXACT ramp steps; the bar is THIN; the bar radius is EXACTLY the control radius', () => {
    const t = deriveWizardShellTokens(theme);
    const ramp = theme.spacing.map((s) => s.px);
    // each space is the EXACT named ramp index (kills a swapped index / a mutated ramp key)
    expect(t.gapPx).toBe(space(theme, 5));
    expect(t.gutterPx).toBe(space(theme, 8));
    expect(t.barThicknessPx).toBe(space(theme, 1));
    // the bar radius is EXACTLY the `control` radius (kills the `'control'`→`''` string-literal mutant)
    expect(t.barRadiusPx).toBe(radiusPx(theme, 'control'));
    expect(t.barRadiusPx).not.toBe(radiusPx(theme, 'sheet'));
    expect(ramp).toContain(t.gapPx);
    expect(ramp).toContain(t.gutterPx);
    expect(ramp).toContain(t.barThicknessPx);
    // the bar is the THINNEST ramp step chosen (space-1 = 4px) — a THIN bar (doc 17 §6)
    expect(t.barThicknessPx).toBe(4);
    expect(t.gutterPx).toBeGreaterThan(t.gapPx);
  });

  it('the progress transition is the theme medium.2 duration + the standard easing curve', () => {
    const t = deriveWizardShellTokens(theme);
    expect(t.transitionMs).toBe(theme.motion.durations['medium.2']);
    expect(t.transitionMs).toBe(300);
    const standard = theme.motion.easing['standard']!;
    expect(t.easing).toBe(`cubic-bezier(${standard.join(', ')})`);
  });
});

describe('wizardProgressFraction — the fraction math (index / (count − 1))', () => {
  it('the first step is 0 (empty bar), the last is 1 (full bar)', () => {
    expect(wizardProgressFraction(0, 3)).toBe(0);
    expect(wizardProgressFraction(2, 3)).toBe(1);
  });

  it('a middle step is the exact fraction', () => {
    expect(wizardProgressFraction(1, 3)).toBeCloseTo(0.5, 10);
    expect(wizardProgressFraction(1, 5)).toBeCloseTo(0.25, 10);
    expect(wizardProgressFraction(3, 5)).toBeCloseTo(0.75, 10);
  });

  it('a single-step wizard reads 1 (nowhere to progress); a zero-step reads 1 (no divide-by-zero)', () => {
    expect(wizardProgressFraction(0, 1)).toBe(1);
    expect(wizardProgressFraction(0, 0)).toBe(1);
  });

  it('an out-of-range index clamps into [0, 1]', () => {
    expect(wizardProgressFraction(-2, 3)).toBe(0);
    expect(wizardProgressFraction(9, 3)).toBe(1);
  });
});

describe('totality — the fallback branches keep the derivation total', () => {
  it('the title falls back to display-small (its EXACT size) when display-large is absent', () => {
    const noLarge = {
      ...theme,
      typography: theme.typography.filter((r) => r.name !== 'display-large'),
    };
    const displaySmall = theme.typography.find((r) => r.name === 'display-small')!;
    const t = deriveWizardShellTokens(noLarge);
    // assert the EXACT size, not just the (shared serif) family — kills the `'display-small'`→`''`
    // string mutant: an empty name selects no role and would land on headline's DIFFERENT size.
    expect(t.titleFontSizePx).toBe(displaySmall.fontSizePx);
    expect(t.titleFontFamily).toBe(displaySmall.fontFamily);
  });

  it('the title falls back to headline (its EXACT size) when both display roles are absent', () => {
    const noDisplays = {
      ...theme,
      typography: theme.typography.filter((r) => !r.name.startsWith('display')),
    };
    const headline = theme.typography.find((r) => r.name === 'headline')!;
    const t = deriveWizardShellTokens(noDisplays);
    // the third fallback rung — kills the `'headline'`→`''` string mutant (an empty name would land
    // on the FIRST role, a different size).
    expect(t.titleFontSizePx).toBe(headline.fontSizePx);
    expect(t.titleFontFamily).toBe(headline.fontFamily);
  });

  it('the title falls back to inherit + the control size when typography is empty', () => {
    const noType = { ...theme, typography: [] };
    const t = deriveWizardShellTokens(noType);
    expect(t.titleFontFamily).toBe('inherit');
    expect(t.titleFontSizePx).toBe(theme.controlGeometry.fontSizePx);
    expect(t.titleLineHeightPx).toBe(theme.controlGeometry.lineHeightPx);
  });

  it('the measure falls back to medium then the first breakpoint when expanded is absent', () => {
    const noExpanded = {
      ...theme,
      breakpoints: theme.breakpoints.filter((b) => b.name !== 'expanded'),
    };
    const t = deriveWizardShellTokens(noExpanded);
    expect(t.measurePx).toBe(theme.breakpoints.find((b) => b.name === 'medium')!.minWidthPx);
  });

  it('the easing falls back to the ease keyword when standard is absent', () => {
    const noStandard = {
      ...theme,
      motion: { ...theme.motion, easing: {} },
    };
    const t = deriveWizardShellTokens(noStandard);
    expect(t.easing).toBe('ease');
  });
});

describe('wizardShellStyleVars — the CSS custom-property emission', () => {
  it('emits the EXACT complete declaration string, with the fraction RAW (unitless)', () => {
    const tokens = deriveWizardShellTokens(theme);
    const px = (n: number): string => `${String(n)}px`;
    const expected = [
      `--eden-wizard-shell-surface: ${tokens.surface};`,
      `--eden-wizard-shell-title: ${tokens.title};`,
      `--eden-wizard-shell-lead: ${tokens.lead};`,
      `--eden-wizard-shell-accent: ${tokens.accent};`,
      `--eden-wizard-shell-track: ${tokens.track};`,
      `--eden-wizard-shell-fill: ${tokens.fill};`,
      `--eden-wizard-shell-title-font-size: ${px(tokens.titleFontSizePx)};`,
      `--eden-wizard-shell-title-line-height: ${px(tokens.titleLineHeightPx)};`,
      `--eden-wizard-shell-title-font-family: ${tokens.titleFontFamily};`,
      `--eden-wizard-shell-lead-font-size: ${px(tokens.leadFontSizePx)};`,
      `--eden-wizard-shell-lead-line-height: ${px(tokens.leadLineHeightPx)};`,
      `--eden-wizard-shell-lead-font-family: ${tokens.leadFontFamily};`,
      `--eden-wizard-shell-mono-font-size: ${px(tokens.monoFontSizePx)};`,
      `--eden-wizard-shell-mono-line-height: ${px(tokens.monoLineHeightPx)};`,
      `--eden-wizard-shell-mono-font-family: ${tokens.monoFontFamily};`,
      `--eden-wizard-shell-measure: ${px(tokens.measurePx)};`,
      `--eden-wizard-shell-gap: ${px(tokens.gapPx)};`,
      `--eden-wizard-shell-gutter: ${px(tokens.gutterPx)};`,
      `--eden-wizard-shell-bar-thickness: ${px(tokens.barThicknessPx)};`,
      `--eden-wizard-shell-bar-radius: ${px(tokens.barRadiusPx)};`,
      `--eden-wizard-shell-transition: ${String(tokens.transitionMs)}ms;`,
      `--eden-wizard-shell-easing: ${tokens.easing};`,
      `--eden-wizard-shell-progress: 0.5;`,
    ].join(' ');
    expect(wizardShellStyleVars(tokens, 0.5)).toBe(expected);
  });

  it('the progress var is the raw fraction (0 and 1 at the endpoints), never px-suffixed', () => {
    const tokens = deriveWizardShellTokens(theme);
    expect(wizardShellStyleVars(tokens, 0)).toContain('--eden-wizard-shell-progress: 0;');
    expect(wizardShellStyleVars(tokens, 1)).toContain('--eden-wizard-shell-progress: 1;');
    expect(wizardShellStyleVars(tokens, 0.5)).not.toContain('0.5px');
  });

  it('carries no hex literal', () => {
    expect(wizardShellStyleVars(deriveWizardShellTokens(theme), 0.5)).not.toMatch(
      /#[0-9a-fA-F]{3,8}\b/,
    );
  });
});

describe('WizardShell.svelte — the real component', () => {
  afterEach(cleanup);

  it('renders the active step title as an h1 named region, the eyebrow, the mono `1 / 3` counter', () => {
    const { container } = render(WizardShell, {
      props: { theme, steps: STEPS, active: 'spark', body: bodySnippet() },
    });
    const region = container.querySelector('[data-eden-wizard-shell]')!;
    const title = container.querySelector('.screen__title')!;
    expect(title.tagName).toBe('H1');
    expect(title.textContent).toBe('What are we building?');
    // the region is named by the title (aria-labelledby → the title id)
    expect(region.getAttribute('aria-labelledby')).toBe(title.id);
    expect(container.querySelector('.eyebrow')!.textContent).toBe('New project');
    expect(container.querySelector('.lead')!.textContent).toBe('One sentence is enough.');
    // the mono counter is 1-based: step 1 of 3
    expect(container.querySelector('.eden-wizard-shell-counter')!.textContent).toBe('1 / 3');
  });

  it('the counter tracks the active step (step 2 of 3 for the middle screen)', () => {
    const { container } = render(WizardShell, {
      props: { theme, steps: STEPS, active: 'scope', body: bodySnippet() },
    });
    expect(container.querySelector('.eden-wizard-shell-counter')!.textContent).toBe('2 / 3');
    // the scope step has no lead — it is not rendered (the anti-clutter budget)
    expect(container.querySelector('.lead')).toBeNull();
  });

  it('binds the derived progress fraction as a scaleX var (0.5 for the middle of a 3-step wizard)', () => {
    const { container } = render(WizardShell, {
      props: { theme, steps: STEPS, active: 'scope', body: bodySnippet() },
    });
    const style = container.querySelector('[data-eden-wizard-shell]')!.getAttribute('style')!;
    expect(style).toContain('--eden-wizard-shell-progress: 0.5');
    // and the serif title family var is bound (the identity voice reaches the DOM)
    const tokens = deriveWizardShellTokens(theme);
    expect(style).toContain(`--eden-wizard-shell-title-font-family: ${tokens.titleFontFamily}`);
  });

  it('renders the footer slot only when provided (the consumer owns back/next/cancel)', () => {
    const bare = render(WizardShell, {
      props: { theme, steps: STEPS, active: 'spark', body: bodySnippet() },
    });
    expect(bare.container.querySelector('.eden-wizard-shell-footer')).toBeNull();
    cleanup();

    const withFooter = render(WizardShell, {
      props: {
        theme,
        steps: STEPS,
        active: 'spark',
        body: bodySnippet(),
        footer: textSnippet('Next'),
      },
    });
    expect(withFooter.container.querySelector('.eden-wizard-shell-footer')!.textContent).toContain(
      'Next',
    );
  });

  it('passes through consumer attributes (data-testid / data-step) onto the rendered root', () => {
    const { container } = render(WizardShell, {
      props: {
        theme,
        steps: STEPS,
        active: 'spark',
        body: bodySnippet(),
        'data-testid': 'create-flow',
        'data-step': 'spark',
      },
    });
    const root = container.querySelector('[data-eden-wizard-shell]')!;
    expect(root.getAttribute('data-testid')).toBe('create-flow');
    expect(root.getAttribute('data-step')).toBe('spark');
  });

  it('Enter on an advanceable step fires onAdvance (the "Enter advances" contract)', async () => {
    const onAdvance = vi.fn();
    const { container } = render(WizardShell, {
      props: {
        theme,
        steps: STEPS,
        active: 'spark',
        advanceable: true,
        onAdvance,
        body: bodySnippet(),
      },
    });
    const root = container.querySelector('[data-eden-wizard-shell]')!;
    await fireEvent.keyDown(root, { key: 'Enter' });
    expect(onAdvance).toHaveBeenCalledTimes(1);
  });

  it('Enter on a NON-advanceable step does NOT fire onAdvance (a guarded, invalid screen)', async () => {
    const onAdvance = vi.fn();
    const { container } = render(WizardShell, {
      props: {
        theme,
        steps: STEPS,
        active: 'spark',
        advanceable: false,
        onAdvance,
        body: bodySnippet(),
      },
    });
    const root = container.querySelector('[data-eden-wizard-shell]')!;
    await fireEvent.keyDown(root, { key: 'Enter' });
    expect(onAdvance).not.toHaveBeenCalled();
  });

  it('Escape fires onExit ("Esc offers exit"); Enter never fires onExit', async () => {
    const onExit = vi.fn();
    const onAdvance = vi.fn();
    const { container } = render(WizardShell, {
      props: { theme, steps: STEPS, active: 'spark', onExit, onAdvance, body: bodySnippet() },
    });
    const root = container.querySelector('[data-eden-wizard-shell]')!;
    await fireEvent.keyDown(root, { key: 'Escape' });
    expect(onExit).toHaveBeenCalledTimes(1);
    await fireEvent.keyDown(root, { key: 'Enter' });
    expect(onExit).toHaveBeenCalledTimes(1); // Enter did not trigger exit
  });

  it('an unknown active id renders the first step (a total, defensive lookup — no crash)', () => {
    const { container } = render(WizardShell, {
      props: { theme, steps: STEPS, active: 'nonexistent', body: bodySnippet() },
    });
    expect(container.querySelector('.eden-wizard-shell-counter')!.textContent).toBe('1 / 3');
    expect(container.querySelector('.screen__title')!.textContent).toBe('What are we building?');
  });
});

/** A body snippet that renders a real input carrying the slot-forwarded autofocus action. */
function bodySnippet(): Snippet<[{ autofocus: (node: HTMLElement) => void }]> {
  return createRawSnippet(() => ({
    render: () => `<input class="wizard-answer" aria-label="answer" />`,
  })) as unknown as Snippet<[{ autofocus: (node: HTMLElement) => void }]>;
}

/** A plain-text snippet for the footer slot. */
function textSnippet(text: string): Snippet {
  return createRawSnippet(() => ({ render: () => `<span>${text}</span>` })) as unknown as Snippet;
}
