<script lang="ts">
  // CREATE PROJECT FLOW — the full-screen, focus-moment "start a new project" experience (doc 17 §6).
  // It is the @eden/primitives WizardShell made concrete: one question per screen, the serif display
  // question at the largest step, a mono `1 / N` counter, a thin progress bar, Enter advances, Esc
  // offers exit. The "trust me" promise is unchanged — the user says what they want in one breath,
  // Eden scopes it, and the user reviews the agent's pick before launching — but the presentation is
  // now full-screen (not a scrim modal) and collapses to TWO visible steps (doc 17 §6 "larger, simpler
  // words"; the survey's MINIMAL FULL-SCREEN STEP COUNT plan):
  //
  //   1. SPARK    — one prompt: "What are we building?" (be brief; details come later). Enter fires
  //                 POST /product/propose.
  //   2. THINKING — a transient scoping interstitial while the propose round-trips (NOT a step: it
  //                 keeps the SPARK progress fraction, no counter jump).
  //   3. REVIEW   — the proposal rendered as editable CARDS: the project name is the ONLY editable
  //                 field (a deliberate product + data-integrity contract), and the platform targets,
  //                 stack chips, and run-line are shown as the agent's pick. "Build it" hands the
  //                 assembled ProductConfig to the parent (POST /sessions + POST /projects).
  //
  // The component owns only local flow state. propose() and onlaunch() are the parent's GatewayClient
  // calls, injected as callbacks, so this stays a pure, testable view with no network of its own. The
  // proposed config is authoritative (normalized server-side); the only edit surfaced is the name —
  // everything else is the agent's pick (the "trust me" promise), tunable later in settings. The wire
  // payload is byte-identical to the pre-full-screen flow: the proposed config rides faithfully, with
  // only the name overridden.
  //
  // WIRE CONTRACT (pinned by tests/e2e/create-product.spec.ts): SPARK submit → POST /product/propose
  // → returns the normalized ProductConfig. REVIEW renders it (create-name seeded to productName,
  // create-summary=summary, targets auto-selected, stack chips, runline harness · model). Build
  // (create-launch) → onlaunch with product == proposed + only productName overridden.

  import { fade } from 'svelte/transition';
  import { cubicOut } from 'svelte/easing';
  import type { Theme } from '@eden/theme';
  import { WizardShell, type WizardStep } from '@eden/primitives';
  import type { ProductConfig, ProductHarness } from '$lib/gateway/types';
  import { deriveStack, deriveTargets } from './projectScope';

  interface LaunchPayload {
    product: ProductConfig;
    harness: ProductHarness;
    prompt: string;
  }
  interface Props {
    /** Runs POST /product/propose and returns the normalized, complete ProductConfig. */
    propose: (prompt: string) => Promise<ProductConfig>;
    /** Invoked on "Build it" with the assembled config + the chosen harness + the original idea. */
    onlaunch: (payload: LaunchPayload) => Promise<void> | void;
    /** Invoked on Cancel / Escape (close the flow without launching). */
    oncancel: () => void;
    /** The active generated theme, handed uniformly with every Eden component. */
    theme?: Theme;
  }
  let { propose, onlaunch, oncancel, theme }: Props = $props();

  // The rendered step. `thinking` is a transient overlay of SPARK (it keeps SPARK's progress
  // fraction) — the two VISIBLE steps are SPARK and REVIEW, so the WizardShell counter reads `1 / 2`.
  type Step = 'spark' | 'thinking' | 'review';
  let step = $state<Step>('spark');

  let idea = $state('');
  let config = $state<ProductConfig | null>(null);
  let projectName = $state('');
  let error = $state<string | null>(null);
  let launching = $state(false);

  const targets = $derived(config ? deriveTargets(config) : []);
  const stack = $derived(config ? deriveStack(config) : []);
  const ideaValid = $derived(idea.trim().length > 0);

  // The two VISIBLE wizard steps (THINKING is a transient overlay of SPARK, not its own step) — the
  // WizardShell reads this for the progress bar length + the `1 / 2` mono counter. The active step id
  // is `spark` while thinking (so the counter/bar do not jump during the interstitial).
  const STEPS: readonly WizardStep[] = [
    {
      id: 'spark',
      eyebrow: 'New project',
      title: 'What are we building?',
      lead: "Say it in one breath — we'll capture the details together.",
    },
    {
      id: 'review',
      eyebrow: "Here's the plan",
      title: 'Review and build',
      lead: 'The name is yours to edit — everything else is the agent’s pick.',
    },
  ];
  const activeStepId = $derived(step === 'thinking' ? 'spark' : step);
  // Enter advances only from SPARK (with a valid idea); REVIEW's build is an explicit button, and the
  // THINKING interstitial must not advance. The textarea keeps native Enter (the shell only swallows
  // Enter on single-line targets), so this gates the shell's Enter contract precisely.
  const advanceable = $derived(step === 'spark' && ideaValid);

  // Rotating status lines for the THINKING interstitial. setInterval (not requestAnimationFrame) so the
  // copy keeps cycling even in a headless/background page, where rAF is throttled to a stop.
  const THINKING_LINES = [
    'Reading your idea…',
    'Choosing the targets…',
    'Picking the stack…',
    'Almost there…',
  ];
  let thinkingLine = $state(THINKING_LINES[0]);
  let thinkingTimer: ReturnType<typeof setInterval> | null = null;
  function startThinking(): void {
    let index = 0;
    thinkingLine = THINKING_LINES[0];
    thinkingTimer = setInterval(() => {
      index = (index + 1) % THINKING_LINES.length;
      thinkingLine = THINKING_LINES[index];
    }, 1100);
  }
  function stopThinking(): void {
    if (thinkingTimer) {
      clearInterval(thinkingTimer);
      thinkingTimer = null;
    }
  }

  async function spark(): Promise<void> {
    if (!ideaValid || step === 'thinking') return;
    error = null;
    step = 'thinking';
    startThinking();
    try {
      const proposed = await propose(idea.trim());
      config = proposed;
      projectName = proposed.productName;
      stopThinking();
      step = 'review';
    } catch (cause) {
      stopThinking();
      error = cause instanceof Error ? cause.message : String(cause);
      step = 'spark';
    }
  }

  function backToSpark(): void {
    error = null;
    config = null;
    step = 'spark';
  }

  async function launch(): Promise<void> {
    if (!config || launching) return;
    launching = true;
    error = null;
    // The proposal is authoritative; the only user edit is the name. Fold it in and hand off — the
    // create payload carries the proposed config with ONLY productName overridden (the data-integrity
    // contract the e2e pins byte-for-byte).
    const product: ProductConfig = {
      ...config,
      productName: projectName.trim() || config.productName,
    };
    try {
      await onlaunch({ product, harness: product.capabilities.harness, prompt: idea.trim() });
    } catch (cause) {
      error = cause instanceof Error ? cause.message : String(cause);
      launching = false;
    }
  }

  // The shell's Enter-advance intent: only SPARK advances (gated by `advanceable`); REVIEW never
  // auto-advances (its build is a deliberate button press).
  function onAdvance(): void {
    if (step === 'spark') void spark();
  }

  // Clean up the rotating-status interval if the flow unmounts mid-think.
  $effect(() => () => stopThinking());
</script>

<WizardShell
  steps={STEPS}
  active={activeStepId}
  {theme}
  {advanceable}
  {onAdvance}
  onExit={oncancel}
  label="New project"
  data-testid="create-flow"
  data-step={step}
>
  {#snippet body({ autofocus })}
    {#if step === 'spark' || step === 'thinking'}
      <!-- ── 1. SPARK (with the THINKING interstitial overlaid) ─────────────────── -->
      {#if step === 'thinking'}
        <div class="thinking" data-testid="create-thinking" in:fade={{ duration: 200 }}>
          <div class="orbit" aria-hidden="true">
            <span class="orbit__core"></span>
            <span class="orbit__ring"></span>
            <span class="orbit__dot orbit__dot--1"></span>
            <span class="orbit__dot orbit__dot--2"></span>
            <span class="orbit__dot orbit__dot--3"></span>
          </div>
          <p class="thinking-line" data-testid="create-thinking-line" role="status">
            {thinkingLine}
          </p>
        </div>
      {:else}
        <div class="spark-body">
          <textarea
            class="spark"
            data-testid="create-spark"
            rows="3"
            aria-label="What are we building?"
            placeholder="A tool that turns my invoices into a clean dashboard…"
            bind:value={idea}
            use:autofocus
          ></textarea>
          {#if error}
            <p class="flow__error" data-testid="create-error" role="alert">{error}</p>
          {/if}
        </div>
      {/if}
    {:else if step === 'review' && config}
      <!-- ── 2. REVIEW — the proposal as editable cards (name editable; the rest is the pick) ── -->
      <div class="review" data-testid="create-scope">
        <div class="card card--name">
          <label class="card__caption" for="create-name-input">Project name</label>
          <input
            id="create-name-input"
            class="name"
            data-testid="create-name"
            aria-label="Project name"
            bind:value={projectName}
            autocomplete="off"
            spellcheck="false"
            use:autofocus
          />
          <p class="lead summary" data-testid="create-summary">{config.summary}</p>
        </div>

        <div class="card" data-testid="create-stack">
          <p class="card__caption">This needs</p>
          <ul class="targets" role="list" data-testid="create-targets">
            {#each targets as target (target.id)}
              <li
                class="target"
                class:target--on={target.selected}
                data-testid="create-target"
                data-target-id={target.id}
                data-selected={target.selected}
              >
                <span class="target__check" aria-hidden="true">✓</span>
                <span class="target__label">{target.label}</span>
                {#if target.selected}
                  <span class="target__hint">{target.hint}</span>
                {/if}
              </li>
            {/each}
          </ul>

          <p class="card__caption card__caption--stack">Built with</p>
          <ul class="chips" role="list" data-testid="create-stack-list">
            {#each stack as chip (chip.role + chip.label)}
              <li
                class="chip chip--{chip.role}"
                data-testid="create-stack-item"
                data-role={chip.role}
              >
                {chip.label}
              </li>
            {/each}
          </ul>

          <p class="runline" data-testid="create-runline">
            Built by <strong>{config.capabilities.harness}</strong>
            · <span class="runline__model">{config.capabilities.model}</span>
          </p>
        </div>

        {#if error}
          <p class="flow__error" data-testid="create-error" role="alert">{error}</p>
        {/if}
      </div>
    {/if}
  {/snippet}

  {#snippet footer()}
    {#if step === 'spark'}
      <button type="button" class="btn" data-testid="create-cancel" onclick={oncancel}
        >Cancel</button
      >
      <button
        type="button"
        class="btn btn--accent"
        data-testid="create-start"
        disabled={!ideaValid}
        onclick={spark}>Let's build it →</button
      >
    {:else if step === 'thinking'}
      <span class="nav-spacer"></span>
      <button type="button" class="btn" data-testid="create-cancel" onclick={oncancel}
        >Cancel</button
      >
    {:else if step === 'review'}
      <button type="button" class="btn" data-testid="create-back" onclick={backToSpark}
        >← Back</button
      >
      <button
        type="button"
        class="btn btn--accent"
        data-testid="create-launch"
        disabled={launching || !config}
        onclick={launch}>{launching ? 'Building…' : 'Build it →'}</button
      >
    {/if}
  {/snippet}
</WizardShell>

<style>
  /* ── token bridge ─────────────────────────────────────────────────────────.
     The WizardShell owns the surface / title / lead / eyebrow / counter / progress appearance
     (all @eden/theme-derived, no literals). This subtree styles only the STEP BODY (the input +
     the review cards) and the FOOTER buttons, bridging the generated @eden/theme role tokens to the
     --accent/--fg/--panel-* vocabulary this content reads — the same math-sourced bridge the app's
     overlays use. One hue source, no hand-set hex or px on a painted role. */
  /* The local bridge now points at the SHADCN SKIN MAPPING (from +layout.svelte) — the same skin the
     rest of the app rides. --radius seeds the shadcn --radius-md geometry; --line/--input/--ring the
     shadcn hairline + focus vocabulary. */
  .spark-body,
  .review {
    --accent: var(--color-primary);
    --on-accent: var(--color-on-primary);
    --fg: var(--foreground, var(--color-on-surface));
    --muted: var(
      --muted-foreground,
      color-mix(in oklab, var(--color-on-surface) 62%, var(--color-surface))
    );
    --panel-bg: var(--card, var(--color-surface));
    --panel-line: var(--border, var(--color-outline));
    --panel-input: var(--input, var(--color-outline));
    --focus-ring: var(--ring, var(--color-primary));
    --radius: var(--radius-md, var(--space-2, 8px));
    --micro: var(--font-size-caption, 12px);
    --warn: var(--color-warning);
  }

  /* ── SPARK input ── the shadcn textarea: a 1px --input edge, --radius-lg corners, --ring focus halo. */
  .spark-body {
    display: flex;
    flex-direction: column;
    gap: 0.7rem;
  }
  .spark {
    font: inherit;
    font-size: 1.2rem;
    padding: 1rem 1.15rem;
    border: 1px solid var(--panel-input);
    border-radius: var(--radius-lg, 14px);
    background: var(--background, color-mix(in oklab, var(--fg) 2%, var(--panel-bg)));
    color: var(--fg);
    resize: vertical;
    line-height: 1.5;
    min-height: 7.5rem;
    transition:
      border-color var(--duration-short-2, 120ms) var(--ease-standard, ease),
      box-shadow var(--duration-short-2, 120ms) var(--ease-standard, ease);
  }
  .spark::placeholder {
    color: color-mix(in oklab, var(--muted) 85%, transparent);
  }
  .spark:focus-visible {
    outline: none;
    border-color: var(--focus-ring);
    box-shadow: 0 0 0 3px color-mix(in oklab, var(--focus-ring) 30%, transparent);
  }

  /* ── REVIEW cards ── shadcn Cards: a --card surface, 1px --border, --radius-lg corners, --shadow-xs. */
  .review {
    display: flex;
    flex-direction: column;
    gap: 0.9rem;
  }
  .card {
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
    padding: 1.1rem 1.2rem;
    border: 1px solid var(--panel-line);
    border-radius: var(--radius-lg, 14px);
    background: var(--panel-bg);
    box-shadow: var(--shadow-xs);
  }
  .card__caption {
    margin: 0;
    font-size: var(--micro);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--muted);
  }
  .card__caption--stack {
    margin-top: 0.5rem;
  }
  .name {
    font: inherit;
    font-size: 1.7rem;
    font-weight: 650;
    letter-spacing: -0.015em;
    padding: 0.35rem 0.5rem;
    margin: -0.1rem -0.5rem;
    border: 1px solid transparent;
    border-radius: var(--radius);
    background: transparent;
    color: var(--fg);
  }
  .name:hover {
    border-color: var(--panel-line);
  }
  .name:focus-visible {
    outline: none;
    border-color: var(--focus-ring);
    box-shadow: 0 0 0 3px color-mix(in oklab, var(--focus-ring) 30%, transparent);
  }
  .summary {
    margin: 0;
    color: var(--fg);
    font-size: 1.02rem;
    line-height: 1.5;
  }

  /* targets */
  .targets {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-wrap: wrap;
    gap: 0.6rem;
  }
  .target {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    padding: 0.55rem 0.85rem;
    border: 1.5px solid var(--panel-line);
    border-radius: 999px;
    color: var(--muted);
    background: transparent;
    font-size: 0.92rem;
    opacity: 0.55;
  }
  .target__check {
    display: none;
    font-size: 0.8rem;
    line-height: 1;
  }
  .target__hint {
    color: color-mix(in oklab, var(--on-accent) 88%, var(--accent));
    font-size: 0.78rem;
  }
  .target--on {
    opacity: 1;
    color: var(--on-accent);
    background: var(--accent);
    border-color: var(--accent);
    font-weight: 600;
  }
  .target--on .target__check {
    display: inline-block;
    color: var(--on-accent);
  }

  /* stack chips */
  .chips {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }
  /* Shadcn "outline" badges — a --surface-muted fill, a 1px --border, --radius-md corners. */
  .chip {
    display: inline-flex;
    align-items: center;
    padding: 0.4rem 0.75rem;
    border-radius: var(--radius-md, 10px);
    font-size: 0.88rem;
    font-family: var(--font-code);
    border: 1px solid var(--panel-line);
    background: var(--surface-muted, color-mix(in oklab, var(--fg) 4%, var(--panel-bg)));
    color: var(--fg);
  }
  .chip--language {
    border-color: color-mix(in oklab, var(--accent) 55%, var(--panel-line));
    background: color-mix(in oklab, var(--accent) 12%, var(--panel-bg));
  }
  .chip--service {
    border-style: dashed;
  }
  .runline {
    margin: 0.4rem 0 0;
    font-size: 0.85rem;
    color: var(--muted);
  }
  .runline strong {
    color: var(--fg);
    text-transform: capitalize;
  }
  .runline__model {
    font-family: var(--font-code);
  }

  /* ── THINKING orbit interstitial ── */
  .thinking {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 1.4rem;
    padding: 2rem 1rem;
    text-align: center;
    color: var(--color-on-surface);
  }
  .orbit {
    position: relative;
    width: 6rem;
    height: 6rem;
    --accent: var(--color-primary);
  }
  .orbit__core {
    position: absolute;
    inset: 38%;
    border-radius: 999px;
    background: var(--accent);
    animation: pulse 1.6s ease-in-out infinite;
  }
  .orbit__ring {
    position: absolute;
    inset: 0;
    border-radius: 999px;
    border: 1.5px solid color-mix(in oklab, var(--accent) 30%, transparent);
  }
  .orbit__dot {
    position: absolute;
    top: 50%;
    left: 50%;
    width: 0.6rem;
    height: 0.6rem;
    margin: -0.3rem;
    border-radius: 999px;
    background: var(--accent);
    transform-origin: 0 0;
    animation: orbit 1.5s linear infinite;
  }
  .orbit__dot--2 {
    animation-delay: -0.5s;
    opacity: 0.7;
  }
  .orbit__dot--3 {
    animation-delay: -1s;
    opacity: 0.45;
  }
  .thinking-line {
    margin: 0;
    color: var(--color-on-surface);
    font-size: 1.1rem;
    font-weight: 550;
  }
  @keyframes orbit {
    from {
      transform: rotate(0) translateX(2.6rem);
    }
    to {
      transform: rotate(360deg) translateX(2.6rem);
    }
  }
  @keyframes pulse {
    0%,
    100% {
      transform: scale(1);
      opacity: 1;
    }
    50% {
      transform: scale(1.25);
      opacity: 0.7;
    }
  }

  /* ── error ── */
  .flow__error {
    margin: 0.2rem 0 0;
    padding: 0.5rem 0.8rem;
    border-radius: var(--radius-md, 10px);
    color: var(--warn);
    background: var(--warning-surface, color-mix(in oklab, var(--warn) 12%, var(--panel-bg)));
    border: 1px solid color-mix(in oklab, var(--warn) 45%, transparent);
    font-size: 0.88rem;
  }

  /* ── footer buttons ── the shell lays out the footer; the consumer owns the button vocabulary. A
     native <button> carries the load-bearing data-testid directly (the e2e asserts create-start /
     create-launch by testid AND reads their disabled state + painted accent background — a wrapper
     span would break both), and `.btn` is a sampled class the UI-math audit reads. ── */
  .nav-spacer {
    flex: 1;
  }
  /* Footer buttons in the shadcn vocabulary — the default is an "outline" button (--card fill,
     1px --border, --radius-md); the accent is the solid --primary button with the --shadow-sm lift. */
  .btn {
    --accent: var(--color-primary);
    --on-accent: var(--color-on-primary);
    --fg: var(--foreground, var(--color-on-surface));
    --panel-bg: var(--card, var(--color-surface));
    --panel-line: var(--border, var(--color-outline));
    --focus-ring: var(--ring, var(--color-primary));

    font: inherit;
    font-size: 0.95rem;
    font-weight: 600;
    padding: 0.65rem 1.2rem;
    border-radius: var(--radius-md, 10px);
    border: 1px solid var(--panel-line);
    background: var(--panel-bg);
    color: var(--fg);
    cursor: pointer;
    /* W5: the wizard buttons ride the theme motion tokens (nearest ladder step + standard easing). */
    transition:
      border-color var(--duration-short-2, 0.12s) var(--ease-standard, ease),
      background var(--duration-short-2, 0.12s) var(--ease-standard, ease),
      box-shadow var(--duration-short-2, 0.12s) var(--ease-standard, ease),
      transform var(--duration-short-1, 0.08s) var(--ease-standard, ease);
  }
  .btn:hover:not(:disabled) {
    border-color: var(--border-strong, var(--accent));
    background: var(--accent-surface, var(--panel-bg));
  }
  .btn:active:not(:disabled) {
    transform: translateY(1px);
  }
  .btn:focus-visible {
    outline: 2px solid var(--focus-ring);
    outline-offset: 2px;
  }
  .btn:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }
  .btn--accent {
    background: var(--accent);
    color: var(--on-accent);
    border-color: var(--accent);
    box-shadow: var(--shadow-sm);
  }
  .btn--accent:hover:not(:disabled) {
    filter: brightness(1.08);
    background: var(--accent);
    box-shadow: var(--shadow-md);
  }

  @media (prefers-reduced-motion: reduce) {
    .orbit__core,
    .orbit__dot {
      animation: none;
    }
    .btn {
      transition: none;
    }
  }
</style>
