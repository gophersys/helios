<script lang="ts">
  // CREATE PROJECT FLOW — the animated, multi-screen "start a new project" experience. It replaces
  // the dense form wizard with a short, confident "trust me" flow: the user says what they want in
  // one breath, Eden scopes it, and the user WATCHES the agent auto-select the platform targets and
  // the stack before launching the build. Simplicity is the design: one idea in, the agent does the
  // thinking, three quick screens out.
  //
  //   1. SPARK     — one prompt: "what do you want to build?" (be brief; details come later).
  //   2. THINKING  — a transient scoping animation while POST /product/propose runs.
  //   3. SCOPE     — the agent SELECTS the platform targets out of the palette (web/mobile/desktop/
  //                  service/cli), staggered; the project name is editable, the summary shown.
  //   4. STACK     — the proposed languages/frameworks/services reveal as chips; the harness is named;
  //                  "Build it" hands the assembled ProductConfig to the parent (POST /sessions).
  //
  // The component owns only local flow state. propose() and onlaunch() are the parent's GatewayClient
  // calls, injected as callbacks, so this stays a pure, testable view with no network of its own. The
  // proposed config is authoritative (normalized server-side); the only edit surfaced is the name —
  // everything else is the agent's pick (the "trust me" promise), tunable later in settings.

  import { fly, fade } from 'svelte/transition';
  import { cubicOut } from 'svelte/easing';
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
  }
  let { propose, onlaunch, oncancel }: Props = $props();

  type Step = 'spark' | 'thinking' | 'scope' | 'stack';
  let step = $state<Step>('spark');

  let idea = $state('');
  let config = $state<ProductConfig | null>(null);
  let projectName = $state('');
  let error = $state<string | null>(null);
  let launching = $state(false);

  const targets = $derived(config ? deriveTargets(config) : []);
  const stack = $derived(config ? deriveStack(config) : []);
  const ideaValid = $derived(idea.trim().length > 0);

  // The three content screens, for the progress dots (THINKING is a transient overlay of SPARK, not
  // its own dot).
  const DOTS: { id: Step; name: string }[] = [
    { id: 'spark', name: 'Idea' },
    { id: 'scope', name: 'Scope' },
    { id: 'stack', name: 'Stack' },
  ];
  const dotIndex = $derived(step === 'thinking' ? 0 : DOTS.findIndex((d) => d.id === step));

  // Rotating status lines for the THINKING animation. setInterval (not requestAnimationFrame) so the
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
      step = 'scope';
    } catch (cause) {
      stopThinking();
      error = cause instanceof Error ? cause.message : String(cause);
      step = 'spark';
    }
  }

  function toStack(): void {
    error = null;
    step = 'stack';
  }
  function backToScope(): void {
    error = null;
    step = 'scope';
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
    // The proposal is authoritative; the only user edit is the name. Fold it in and hand off.
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

  function onScrimKeydown(event: KeyboardEvent): void {
    if (event.key === 'Escape') oncancel();
  }
  // The dialog subtree stops keydowns from reaching the workspace's global ⌘K handler, but must
  // still honor Escape-to-close itself (the scrim handler never sees it once focus is inside) —
  // the same precedent as Modal.svelte's panel handler.
  function onFlowKeydown(event: KeyboardEvent): void {
    if (event.key === 'Escape') {
      oncancel();
      return;
    }
    event.stopPropagation();
  }
  function onSparkKeydown(event: KeyboardEvent): void {
    // Cmd/Ctrl+Enter submits the idea straight from the textarea.
    if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
      event.preventDefault();
      void spark();
    }
  }

  // Clean up the rotating-status interval if the flow unmounts mid-think.
  $effect(() => () => stopThinking());

  const screenIn = { x: 28, duration: 300, easing: cubicOut } as const;
</script>

<div
  class="scrim"
  role="presentation"
  onclick={oncancel}
  onkeydown={onScrimKeydown}
  data-testid="create-scrim"
>
  <div
    class="flow"
    role="dialog"
    tabindex="-1"
    aria-modal="true"
    aria-label="New project"
    data-testid="create-flow"
    data-step={step}
    onclick={(event) => event.stopPropagation()}
    onkeydown={onFlowKeydown}
  >
    <header class="flow__head">
      <div class="flow__progress" aria-hidden="true">
        {#each DOTS as dot, index (dot.id)}
          <span class="dot" class:dot--done={index < dotIndex} class:dot--on={index === dotIndex}
          ></span>
        {/each}
      </div>
      <button type="button" class="flow__close" aria-label="Cancel" onclick={oncancel}>✕</button>
    </header>

    <div class="flow__body">
      {#if step === 'spark'}
        <!-- ── 1. SPARK ────────────────────────────────────────────────────── -->
        <section class="screen" data-testid="create-spark-screen" in:fly={screenIn}>
          <p class="eyebrow">New project</p>
          <h2 class="screen__title">What do you want to build?</h2>
          <p class="lead">Be brief — we'll capture the details together.</p>
          <textarea
            class="spark"
            data-testid="create-spark"
            rows="3"
            aria-label="What do you want to build?"
            placeholder="A tool that turns my invoices into a clean dashboard…"
            bind:value={idea}
            onkeydown={onSparkKeydown}
          ></textarea>
          {#if error}
            <p class="flow__error" data-testid="create-error" role="alert">{error}</p>
          {/if}
        </section>
      {:else if step === 'thinking'}
        <!-- ── 2. THINKING ─────────────────────────────────────────────────── -->
        <section class="screen screen--center" data-testid="create-thinking" in:fade={{ duration: 200 }}>
          <div class="orbit" aria-hidden="true">
            <span class="orbit__core"></span>
            <span class="orbit__ring"></span>
            <span class="orbit__dot orbit__dot--1"></span>
            <span class="orbit__dot orbit__dot--2"></span>
            <span class="orbit__dot orbit__dot--3"></span>
          </div>
          <p class="thinking-line" data-testid="create-thinking-line" role="status">{thinkingLine}</p>
        </section>
      {:else if step === 'scope' && config}
        <!-- ── 3. SCOPE — the agent auto-selects the targets ───────────────── -->
        <section class="screen" data-testid="create-scope" in:fly={screenIn}>
          <p class="eyebrow">Here's the plan</p>
          <input
            class="name"
            data-testid="create-name"
            aria-label="Project name"
            bind:value={projectName}
            autocomplete="off"
            spellcheck="false"
          />
          <p class="lead summary" data-testid="create-summary">{config.summary}</p>

          <p class="targets__caption">This needs</p>
          <ul class="targets" role="list" data-testid="create-targets">
            {#each targets as target, index (target.id)}
              <li
                class="target"
                class:target--on={target.selected}
                data-testid="create-target"
                data-target-id={target.id}
                data-selected={target.selected}
                style="--i: {index}"
              >
                <span class="target__check" aria-hidden="true">✓</span>
                <span class="target__label">{target.label}</span>
                {#if target.selected}
                  <span class="target__hint">{target.hint}</span>
                {/if}
              </li>
            {/each}
          </ul>
          {#if error}
            <p class="flow__error" data-testid="create-error" role="alert">{error}</p>
          {/if}
        </section>
      {:else if step === 'stack' && config}
        <!-- ── 4. STACK ────────────────────────────────────────────────────── -->
        <section class="screen" data-testid="create-stack" in:fly={screenIn}>
          <p class="eyebrow">And here's the stack</p>
          <h2 class="screen__title screen__title--sm">We'll build {projectName || config.productName} with…</h2>
          <ul class="chips" role="list" data-testid="create-stack-list">
            {#each stack as chip, index (chip.role + chip.label)}
              <li
                class="chip chip--{chip.role}"
                data-testid="create-stack-item"
                data-role={chip.role}
                style="--i: {index}"
                in:fly={{ y: 10, delay: index * 60, duration: 280, easing: cubicOut }}
              >
                {chip.label}
              </li>
            {/each}
          </ul>
          <p class="runline" data-testid="create-runline">
            Built by <strong>{config.capabilities.harness}</strong>
            · <span class="runline__model">{config.capabilities.model}</span>
          </p>
          {#if error}
            <p class="flow__error" data-testid="create-error" role="alert">{error}</p>
          {/if}
        </section>
      {/if}
    </div>

    <!-- ── nav ────────────────────────────────────────────────────────────── -->
    <footer class="flow__nav">
      {#if step === 'spark'}
        <button type="button" class="btn" data-testid="create-cancel" onclick={oncancel}>Cancel</button>
        <button
          type="button"
          class="btn btn--accent"
          data-testid="create-start"
          disabled={!ideaValid}
          onclick={spark}>Let's build it →</button
        >
      {:else if step === 'thinking'}
        <span class="nav-spacer"></span>
        <button type="button" class="btn" data-testid="create-cancel" onclick={oncancel}>Cancel</button>
      {:else if step === 'scope'}
        <button type="button" class="btn" data-testid="create-back" onclick={backToSpark}>← Back</button>
        <button type="button" class="btn btn--accent" data-testid="create-next" onclick={toStack}
          >Looks right →</button
        >
      {:else if step === 'stack'}
        <button type="button" class="btn" data-testid="create-back" onclick={backToScope}>← Back</button>
        <button
          type="button"
          class="btn btn--accent"
          data-testid="create-launch"
          disabled={launching || !config}
          onclick={launch}>{launching ? 'Building…' : 'Build it →'}</button
        >
      {/if}
    </footer>
  </div>
</div>

<style>
  /* ── token bridge ─────────────────────────────────────────────────────────.
     @eden/theme emits --color-*, --space-*, --font-size-* (+ the +layout --eden-app-* aliases) but
     NOT the --accent/--fg/--panel-* vocabulary this subtree reads. Bridge each to a generated role
     token at the root so the whole flow inherits a math-sourced value (one hue source, no literals)
     — the same token-bridge pattern the chat overlays use. */
  .scrim {
    --accent: var(--color-primary);
    --on-accent: var(--color-on-primary);
    --fg: var(--color-on-surface);
    --muted: var(--eden-app-muted, color-mix(in oklab, var(--color-on-surface) 62%, var(--color-surface)));
    --panel-bg: var(--color-surface);
    --panel-line: var(--color-outline);
    --radius: var(--eden-app-radius, var(--space-2, 8px));
    --micro: var(--font-size-caption, 12px);
    --warn: var(--color-warning);

    position: fixed;
    inset: 0;
    background: color-mix(in srgb, var(--color-on-surface) 55%, transparent);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 1.5rem;
    z-index: 10;
  }
  .flow {
    width: min(560px, 100%);
    min-height: min(64vh, 540px);
    max-height: min(88vh, 720px);
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    background: var(--panel-bg);
    border: 1px solid var(--panel-line);
    border-radius: calc(var(--radius) * 1.75);
    padding: 1.25rem 1.4rem 1.1rem;
    box-shadow: 0 18px 56px color-mix(in srgb, var(--color-on-surface) 22%, transparent);
    overflow: hidden;
  }

  /* ── head: progress dots + close ── */
  .flow__head {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .flow__progress {
    display: inline-flex;
    gap: 0.4rem;
    align-items: center;
  }
  .dot {
    width: 0.5rem;
    height: 0.5rem;
    border-radius: 999px;
    background: color-mix(in oklab, var(--fg) 18%, transparent);
    transition: background 0.2s ease, width 0.2s ease;
  }
  .dot--on {
    width: 1.4rem;
    background: var(--accent);
  }
  .dot--done {
    background: color-mix(in oklab, var(--accent) 55%, transparent);
  }
  .flow__close {
    border: none;
    background: transparent;
    color: var(--muted);
    cursor: pointer;
    font-size: 1rem;
    line-height: 1;
    padding: 0.3rem;
    border-radius: var(--radius);
  }
  .flow__close:hover {
    color: var(--fg);
  }
  .flow__close:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }

  /* ── body / screens ── */
  .flow__body {
    flex: 1;
    min-height: 0;
    display: flex;
    overflow-y: auto;
    padding: 0.3rem 0.15rem;
  }
  .screen {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 0.7rem;
  }
  .screen--center {
    align-items: center;
    justify-content: center;
    gap: 1.4rem;
    text-align: center;
  }
  .eyebrow {
    font-family: var(--font-code);
    font-size: var(--micro);
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--accent);
    margin: 0;
  }
  .screen__title {
    margin: 0;
    font-size: 1.7rem;
    line-height: 1.15;
    letter-spacing: -0.015em;
    color: var(--fg);
  }
  .screen__title--sm {
    font-size: 1.25rem;
  }
  .lead {
    margin: 0;
    color: var(--muted);
    line-height: 1.5;
  }
  .summary {
    color: var(--fg);
    font-size: 1.02rem;
  }

  /* ── SPARK ── */
  .spark {
    font: inherit;
    font-size: 1.05rem;
    margin-top: 0.3rem;
    padding: 0.85rem 1rem;
    border: 1px solid var(--panel-line);
    border-radius: calc(var(--radius) * 1.25);
    background: color-mix(in oklab, var(--fg) 2%, var(--panel-bg));
    color: var(--fg);
    resize: vertical;
    line-height: 1.5;
    min-height: 6.5rem;
  }
  .spark::placeholder {
    color: color-mix(in oklab, var(--muted) 85%, transparent);
  }
  .spark:focus-visible {
    outline: none;
    border-color: var(--accent);
    box-shadow: 0 0 0 2px color-mix(in oklab, var(--accent) 35%, transparent);
  }

  /* ── SCOPE: editable name + targets ── */
  .name {
    font: inherit;
    font-size: 1.55rem;
    font-weight: 650;
    letter-spacing: -0.015em;
    padding: 0.2rem 0.3rem;
    margin: -0.2rem -0.3rem 0;
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
    border-color: var(--accent);
    box-shadow: 0 0 0 2px color-mix(in oklab, var(--accent) 30%, transparent);
  }
  .targets__caption {
    margin: 0.4rem 0 0;
    font-size: var(--micro);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--muted);
  }
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
    /* unselected targets sit quietly; selected ones pop in (the agent "choosing" them). */
    opacity: 0.5;
    transition: opacity 0.25s ease;
  }
  .target__check {
    display: none;
    font-size: 0.8rem;
    line-height: 1;
  }
  .target__hint {
    color: color-mix(in oklab, var(--on-accent) 82%, transparent);
    font-size: 0.78rem;
  }
  .target--on {
    opacity: 1;
    color: var(--on-accent);
    background: var(--accent);
    border-color: var(--accent);
    font-weight: 600;
    animation: target-pop 0.42s cubic-bezier(0.2, 1.3, 0.5, 1) both;
    animation-delay: calc(var(--i) * 90ms + 120ms);
  }
  .target--on .target__check {
    display: inline-block;
    color: var(--on-accent);
    animation: check-in 0.3s ease both;
    animation-delay: calc(var(--i) * 90ms + 260ms);
  }
  @keyframes target-pop {
    0% {
      opacity: 0;
      transform: scale(0.82);
    }
    60% {
      transform: scale(1.06);
    }
    100% {
      opacity: 1;
      transform: scale(1);
    }
  }
  @keyframes check-in {
    from {
      opacity: 0;
      transform: scale(0);
    }
    to {
      opacity: 1;
      transform: scale(1);
    }
  }

  /* ── STACK chips ── */
  .chips {
    list-style: none;
    margin: 0.2rem 0 0;
    padding: 0;
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }
  .chip {
    display: inline-flex;
    align-items: center;
    padding: 0.4rem 0.75rem;
    border-radius: 999px;
    font-size: 0.88rem;
    font-family: var(--font-code);
    border: 1px solid var(--panel-line);
    background: color-mix(in oklab, var(--fg) 4%, var(--panel-bg));
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
    margin: 0.7rem 0 0;
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

  /* ── THINKING orbit ── */
  .orbit {
    position: relative;
    width: 5.5rem;
    height: 5.5rem;
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
    color: var(--fg);
    font-size: 1.05rem;
    font-weight: 550;
  }
  @keyframes orbit {
    from {
      transform: rotate(0) translateX(2.4rem);
    }
    to {
      transform: rotate(360deg) translateX(2.4rem);
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
    border-radius: var(--radius);
    color: var(--warn);
    background: color-mix(in oklab, var(--warn) 12%, var(--panel-bg));
    border: 1px solid color-mix(in oklab, var(--warn) 45%, transparent);
    font-size: 0.88rem;
  }

  /* ── nav ── */
  .flow__nav {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 0.6rem;
    padding-top: 0.6rem;
  }
  .nav-spacer {
    flex: 1;
  }
  .btn {
    font: inherit;
    font-size: 0.92rem;
    font-weight: 600;
    padding: 0.6rem 1.1rem;
    border-radius: calc(var(--radius) * 1.25);
    border: 1px solid var(--panel-line);
    background: var(--panel-bg);
    color: var(--fg);
    cursor: pointer;
    transition: border-color 0.12s ease, background 0.12s ease, transform 0.08s ease;
  }
  .btn:hover:not(:disabled) {
    border-color: var(--accent);
  }
  .btn:active:not(:disabled) {
    transform: translateY(1px);
  }
  .btn:focus-visible {
    outline: 2px solid var(--accent);
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
  }

  @media (prefers-reduced-motion: reduce) {
    .target--on,
    .target--on .target__check,
    .orbit__core,
    .orbit__dot {
      animation: none;
    }
    .dot,
    .btn {
      transition: none;
    }
  }
</style>
