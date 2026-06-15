<script lang="ts">
  // The PRODUCT WIZARD — the create flow that mirrors Eden kicking off a PRODUCT, replacing the
  // simple "new session" modal. A "session" IS a PRODUCT Eden builds via its 10-phase SDLC. The
  // flow:
  //   1. DEFINE       — productName + the prompt; on Next, POST /product/propose (Eden scopes it).
  //   2. STACK        — the AI-proposed kind + summary + languages/frameworks + services, editable.
  //   3. CAPABILITIES — harness/model + toolGrants + skills + rules, editable.
  //   4. PROCESS      — the sdlcPhases to run (multi-select) + autonomy, editable.
  //   5. SAFETY       — sandbox posture + egressAllow, editable.
  //   6. REVIEW       — the assembled ProductConfig summary → launch.
  // On launch the parent creates the session (POST /sessions carrying `product`) and opens the chat
  // view; the running session streams the real agent over the existing SSE seam (unchanged).
  //
  // This component owns ONLY the wizard's local form state. propose() and createSession() are the
  // parent's GatewayClient calls, injected as callbacks so this stays a pure form (testable, no
  // network of its own). The proposed config seeds steps 2–5; every field is editable before launch.

  import {
    PRODUCT_HARNESSES,
    PRODUCT_KINDS,
    SDLC_PHASES,
    type ProductConfig,
    type ProductHarness,
  } from '$lib/gateway/types';
  import ChipInput from './ChipInput.svelte';
  import PillGroup from './PillGroup.svelte';

  interface LaunchPayload {
    product: ProductConfig;
    harness: ProductHarness;
    prompt: string;
  }

  interface Props {
    /** Runs POST /product/propose and returns the normalized, wizard-ready ProductConfig. */
    propose: (prompt: string) => Promise<ProductConfig>;
    /** Invoked on REVIEW → Launch with the assembled, edited config + the chosen harness + prompt. */
    onlaunch: (payload: LaunchPayload) => Promise<void> | void;
    /** Invoked on Cancel / Escape (close the wizard without launching). */
    oncancel: () => void;
  }

  let { propose, onlaunch, oncancel }: Props = $props();

  // ── the six steps ──────────────────────────────────────────────────────────.
  const STEPS = ['Define', 'Stack', 'Capabilities', 'Process', 'Safety', 'Review'] as const;
  type StepIndex = 0 | 1 | 2 | 3 | 4 | 5;
  let step = $state<StepIndex>(0);

  // ── step 1 (DEFINE) inputs ─────────────────────────────────────────────────.
  let productName = $state('');
  let prompt = $state('');

  // ── the proposed + edited config (seeds steps 2–6) ─────────────────────────.
  let config = $state<ProductConfig | null>(null);

  // ── PROCESS step extra (autonomy) — carried into the launch prompt preamble ─.
  let autonomy = $state<'supervised' | 'autonomous'>('supervised');

  // ── flow state ─────────────────────────────────────────────────────────────.
  let proposing = $state(false);
  let launching = $state(false);
  let error = $state<string | null>(null);

  const defineValid = $derived(prompt.trim().length > 0);

  /** Step 1 → 2: ask Eden to scope the product from the prompt, seed the editable config. */
  async function scopeProduct(): Promise<void> {
    if (!defineValid || proposing) return;
    proposing = true;
    error = null;
    try {
      const proposed = await propose(prompt.trim());
      // The user's typed productName wins over the proposal when they supplied one.
      if (productName.trim()) proposed.productName = productName.trim();
      else productName = proposed.productName;
      config = proposed;
      step = 1;
    } catch (cause) {
      error = cause instanceof Error ? cause.message : String(cause);
    } finally {
      proposing = false;
    }
  }

  function back(): void {
    error = null;
    if (step > 0) step = (step - 1) as StepIndex;
  }

  /** Next from steps 2–5 (step 1 is gated on the async propose via scopeProduct). */
  function next(): void {
    error = null;
    if (step === 0) {
      void scopeProduct();
      return;
    }
    // Keep productName and the config in sync on the way out of STACK.
    if (config && step === 1) config.productName = productName.trim() || config.productName;
    if (step < 5) step = (step + 1) as StepIndex;
  }

  /** REVIEW → Launch: hand the assembled config to the parent (which POSTs /sessions). */
  async function launch(): Promise<void> {
    if (!config || launching) return;
    launching = true;
    error = null;
    // Fold the wizard-only autonomy choice into the prompt so the build agent sees it (the
    // ProductConfig schema carries the product spec; autonomy is a run-mode hint on the prompt).
    const autonomyHint =
      autonomy === 'autonomous'
        ? 'Run autonomously end-to-end; only pause for a blocking decision.'
        : 'Run supervised; check in at each phase boundary before proceeding.';
    try {
      await onlaunch({
        product: config,
        harness: config.capabilities.harness,
        prompt: `${prompt.trim()}\n\n${autonomyHint}`,
      });
    } catch (cause) {
      error = cause instanceof Error ? cause.message : String(cause);
      launching = false;
    }
  }

  function onScrimKeydown(event: KeyboardEvent): void {
    if (event.key === 'Escape') oncancel();
  }
</script>

<div
  class="scrim"
  role="presentation"
  onclick={oncancel}
  onkeydown={onScrimKeydown}
  data-testid="wizard-scrim"
>
  <div
    class="wizard panel"
    role="dialog"
    tabindex="-1"
    aria-modal="true"
    aria-label="New product"
    data-testid="product-wizard"
    data-step={STEPS[step].toLowerCase()}
    onclick={(event) => event.stopPropagation()}
    onkeydown={(event) => event.stopPropagation()}
  >
    <!-- ── header + progress ──────────────────────────────────────────────── -->
    <header class="wizard__head">
      <div>
        <p class="eyebrow">Eden · new product</p>
        <h2 class="wizard__title">{STEPS[step]}</h2>
      </div>
      <button type="button" class="wizard__close" aria-label="Cancel" onclick={oncancel}>✕</button>
    </header>

    <ol class="steps" data-testid="wizard-steps" aria-label="Progress">
      {#each STEPS as name, index (name)}
        <li
          class="steps__item"
          class:steps__item--done={index < step}
          class:steps__item--current={index === step}
          aria-current={index === step ? 'step' : undefined}
        >
          <span class="steps__dot">{index + 1}</span>
          <span class="steps__name">{name}</span>
        </li>
      {/each}
    </ol>

    <div class="wizard__body">
      {#if step === 0}
        <!-- ── 1. DEFINE ──────────────────────────────────────────────────── -->
        <p class="lead">
          What are you building? Describe the product — Eden scopes it into a configuration you can
          edit before the build starts.
        </p>
        <label class="field">
          <span class="field__label">Product name (optional — Eden proposes one)</span>
          <input
            class="field__input"
            data-testid="wizard-name"
            placeholder="invoice-service"
            bind:value={productName}
            autocomplete="off"
          />
        </label>
        <label class="field">
          <span class="field__label">What are you building?</span>
          <textarea
            class="field__input field__input--area"
            data-testid="wizard-prompt"
            rows="5"
            placeholder="A Go service that ingests invoices over NATS, persists them to Postgres, and exposes a REST API…"
            bind:value={prompt}
          ></textarea>
        </label>
        {#if proposing}
          <p class="scoping" data-testid="wizard-scoping" role="status">
            <span class="spinner" aria-hidden="true"></span>
            Eden is scoping your product…
          </p>
        {/if}
      {:else if step === 1 && config}
        <!-- ── 2. STACK ───────────────────────────────────────────────────── -->
        <label class="field">
          <span class="field__label">Product name</span>
          <input
            class="field__input"
            data-testid="wizard-name-stack"
            bind:value={productName}
            autocomplete="off"
          />
        </label>
        <PillGroup
          options={PRODUCT_KINDS}
          label="Product kind"
          mode="single"
          bind:value={config.productKind}
          testid="wizard-kind"
        />
        <label class="field">
          <span class="field__label">Summary — what we'll build</span>
          <textarea
            class="field__input field__input--area"
            data-testid="wizard-summary"
            rows="2"
            bind:value={config.summary}
          ></textarea>
        </label>
        <ChipInput
          bind:items={config.stack.languages}
          label="Languages"
          placeholder="go, typescript…"
          testid="wizard-languages"
        />
        <ChipInput
          bind:items={config.stack.frameworks}
          label="Frameworks"
          placeholder="svelte…"
          testid="wizard-frameworks"
        />
        <ChipInput
          bind:items={config.services}
          label="Services"
          placeholder="nats, postgres, vault…"
          testid="wizard-services"
        />
      {:else if step === 2 && config}
        <!-- ── 3. CAPABILITIES ────────────────────────────────────────────── -->
        <PillGroup
          options={PRODUCT_HARNESSES}
          label="Harness"
          mode="single"
          bind:value={config.capabilities.harness}
          testid="wizard-harness"
        />
        <label class="field">
          <span class="field__label">Model</span>
          <input
            class="field__input"
            data-testid="wizard-model"
            bind:value={config.capabilities.model}
            autocomplete="off"
          />
        </label>
        <ChipInput
          bind:items={config.capabilities.toolGrants}
          label="Tool grants"
          placeholder="filesystem, shell, git, network-egress…"
          testid="wizard-toolgrants"
        />
        <ChipInput
          bind:items={config.capabilities.skills}
          label="Skills"
          placeholder="code-review, deep-research…"
          testid="wizard-skills"
        />
        <ChipInput
          bind:items={config.capabilities.rules}
          label="Rules"
          placeholder="library-pipeline, test-taxonomy…"
          testid="wizard-rules"
        />
      {:else if step === 3 && config}
        <!-- ── 4. PROCESS ─────────────────────────────────────────────────── -->
        <PillGroup
          options={SDLC_PHASES}
          label="SDLC phases to run"
          mode="multi"
          bind:selected={config.sdlcPhases}
          testid="wizard-phases"
        />
        <PillGroup
          options={['supervised', 'autonomous']}
          label="Autonomy"
          mode="single"
          bind:value={autonomy}
          testid="wizard-autonomy"
        />
      {:else if step === 4 && config}
        <!-- ── 5. SAFETY ──────────────────────────────────────────────────── -->
        <PillGroup
          options={['strict', 'relaxed']}
          label="Sandbox posture"
          mode="single"
          bind:value={config.sandbox.posture}
          testid="wizard-posture"
        />
        <p class="hint">
          {config.sandbox.posture === 'strict'
            ? 'Strict — default-deny egress; the build agent reaches only the hosts you allow below.'
            : 'Relaxed — broader egress; use only for a trusted, supervised build.'}
        </p>
        <ChipInput
          bind:items={config.sandbox.egressAllow}
          label="Egress allow-list (hosts)"
          placeholder="api.github.com, registry.npmjs.org…"
          testid="wizard-egress"
        />
      {:else if step === 5 && config}
        <!-- ── 6. REVIEW & LAUNCH ─────────────────────────────────────────── -->
        <p class="lead">Review the product Eden will build, then launch the session.</p>
        <dl class="review" data-testid="wizard-review">
          <div class="review__row">
            <dt>Product</dt>
            <dd data-testid="review-name">{productName.trim() || config.productName}</dd>
          </div>
          <div class="review__row">
            <dt>Kind</dt>
            <dd data-testid="review-kind">{config.productKind}</dd>
          </div>
          <div class="review__row">
            <dt>Summary</dt>
            <dd>{config.summary}</dd>
          </div>
          <div class="review__row">
            <dt>Stack</dt>
            <dd data-testid="review-stack">
              {[...config.stack.languages, ...config.stack.frameworks].join(', ') || '—'}
            </dd>
          </div>
          <div class="review__row">
            <dt>Services</dt>
            <dd>{config.services.join(', ') || 'none'}</dd>
          </div>
          <div class="review__row">
            <dt>Harness</dt>
            <dd data-testid="review-harness">
              {config.capabilities.harness} · {config.capabilities.model}
            </dd>
          </div>
          <div class="review__row">
            <dt>Tool grants</dt>
            <dd>{config.capabilities.toolGrants.join(', ') || 'none'}</dd>
          </div>
          <div class="review__row">
            <dt>Phases</dt>
            <dd data-testid="review-phases">{config.sdlcPhases.join(' → ') || '—'}</dd>
          </div>
          <div class="review__row">
            <dt>Autonomy</dt>
            <dd>{autonomy}</dd>
          </div>
          <div class="review__row">
            <dt>Sandbox</dt>
            <dd data-testid="review-sandbox">
              {config.sandbox.posture}{config.sandbox.egressAllow.length
                ? ` · allow ${config.sandbox.egressAllow.join(', ')}`
                : ''}
            </dd>
          </div>
        </dl>
      {/if}

      {#if error}
        <p class="wizard__error" data-testid="wizard-error">{error}</p>
      {/if}
    </div>

    <!-- ── nav ────────────────────────────────────────────────────────────── -->
    <footer class="wizard__nav">
      <button
        type="button"
        class="btn"
        data-testid="wizard-cancel"
        onclick={step === 0 ? oncancel : back}
      >
        {step === 0 ? 'Cancel' : 'Back'}
      </button>

      {#if step < 5}
        <button
          type="button"
          class="btn btn--accent"
          data-testid="wizard-next"
          disabled={(step === 0 && (!defineValid || proposing)) || (step > 0 && !config)}
          onclick={next}
        >
          {step === 0 ? (proposing ? 'Scoping…' : 'Scope product →') : 'Next →'}
        </button>
      {:else}
        <button
          type="button"
          class="btn btn--accent"
          data-testid="wizard-launch"
          disabled={launching || !config}
          onclick={launch}
        >
          {launching ? 'Launching…' : 'Launch build'}
        </button>
      {/if}
    </footer>
  </div>
</div>

<style>
  /* ── token bridge ─────────────────────────────────────────────────────────.
     The wizard subtree (this component + PillGroup + ChipInput) was authored against a local
     token vocabulary (--accent, --muted, --panel-*, --fg, --radius, --color-bone/ink, --type-micro,
     --chip-warn-*, --navbg/--chipbg) that the generated @eden/theme substrate does NOT emit — it
     emits --color-*, --space-*, --font-size-*, plus the +layout --eden-app-* aliases. Left unbridged,
     every accent control rendered with no background and transparent text (--accent/--color-bone
     undefined), inputs/borders were unstyled, and micro-labels collapsed to the inherited size — the
     create-flow centerpiece was invisible. Bridge each local token to a GENERATED role token here, at
     the wizard root, so the whole subtree inherits a math-sourced value (one hue source, no literals). */
  .scrim {
    --accent: var(--color-primary);
    --color-bone: var(--color-on-primary);
    --color-ink: var(--color-on-surface);
    --fg: var(--color-on-surface);
    --muted: var(--eden-app-muted);
    --panel-bg: var(--color-surface);
    --panel-line: var(--color-outline);
    --radius: var(--eden-app-radius, var(--space-2, 8px));
    --type-micro: var(--font-size-caption, 12px);
    --chip-warn-fg: var(--color-warning);
    --chip-warn-bg: color-mix(in oklab, var(--color-warning) 14%, var(--color-surface));
    --navbg: color-mix(in oklab, var(--color-on-surface) 6%, var(--color-surface));
    --chipbg: var(--navbg);

    position: fixed;
    inset: 0;
    background: color-mix(in srgb, var(--color-ink) 55%, transparent);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 1.5rem;
    z-index: 10;
  }
  /* The `.wizard panel` surface (the dialog card). `.panel` was a bare, undefined class — give it the
     generated surface (token-driven) so the wizard reads as a raised panel, not a transparent box. */
  .panel {
    background: var(--panel-bg);
    border: 1px solid var(--panel-line);
    border-radius: calc(var(--radius) * 1.5);
    padding: 1.25rem;
    box-shadow: 0 12px 40px color-mix(in srgb, var(--color-on-surface) 18%, transparent);
  }
  .wizard {
    width: min(640px, 100%);
    max-height: min(88vh, 760px);
    display: flex;
    flex-direction: column;
    gap: 1rem;
    overflow: hidden;
  }
  .wizard__head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 0.6rem;
  }
  .eyebrow {
    font-family: var(--font-code);
    font-size: var(--type-micro);
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--muted);
    margin: 0 0 0.2rem;
  }
  .wizard__title {
    margin: 0;
    font-size: 1.4rem;
  }
  .wizard__close {
    border: none;
    background: transparent;
    color: var(--muted);
    cursor: pointer;
    font-size: 1rem;
    padding: 0.3rem;
    line-height: 1;
  }
  .wizard__close:hover {
    color: var(--fg);
  }

  /* ── progress ── */
  .steps {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    gap: 0.3rem;
    flex-wrap: wrap;
  }
  .steps__item {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    font-size: var(--type-micro);
    color: var(--muted);
    flex: 1 1 0;
    min-width: max-content;
  }
  .steps__dot {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 1.4rem;
    height: 1.4rem;
    border-radius: 999px;
    border: 1px solid var(--panel-line);
    font-family: var(--font-code);
    font-weight: 650;
    flex: none;
  }
  .steps__name {
    white-space: nowrap;
  }
  .steps__item--current .steps__dot {
    background: var(--accent);
    color: var(--color-bone);
    border-color: var(--accent);
  }
  .steps__item--current {
    color: var(--fg);
    font-weight: 650;
  }
  .steps__item--done .steps__dot {
    border-color: var(--accent);
    color: var(--accent);
  }

  /* ── body ── */
  .wizard__body {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    overflow-y: auto;
    padding: 0.2rem 0.1rem;
  }
  .lead {
    margin: 0;
    color: var(--muted);
    line-height: 1.5;
  }
  .hint {
    margin: 0;
    font-size: 0.85rem;
    color: var(--muted);
  }
  .field {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
  }
  .field__label {
    font-size: var(--type-micro);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--muted);
  }
  .field__input {
    font: inherit;
    padding: 0.6rem 0.8rem;
    border: 1px solid var(--panel-line);
    border-radius: var(--radius);
    background: var(--panel-bg);
    color: var(--fg);
  }
  .field__input--area {
    resize: vertical;
    line-height: 1.5;
  }
  .field__input:focus {
    outline: none;
    border-color: var(--accent);
    box-shadow: 0 0 0 1px var(--accent);
  }

  .scoping {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    margin: 0;
    color: var(--accent);
    font-weight: 600;
  }
  .spinner {
    width: 1rem;
    height: 1rem;
    border: 2px solid color-mix(in srgb, var(--accent) 30%, transparent);
    border-top-color: var(--accent);
    border-radius: 999px;
    animation: spin 0.7s linear infinite;
  }
  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  /* ── review ── */
  .review {
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 0;
    border: 1px solid var(--panel-line);
    border-radius: var(--radius);
    overflow: hidden;
  }
  .review__row {
    display: grid;
    grid-template-columns: 9rem 1fr;
    gap: 0.6rem;
    padding: 0.55rem 0.8rem;
    border-bottom: 1px solid var(--panel-line);
  }
  .review__row:last-child {
    border-bottom: none;
  }
  .review dt {
    font-size: var(--type-micro);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--muted);
    margin: 0;
  }
  .review dd {
    margin: 0;
    word-break: break-word;
    line-height: 1.45;
  }

  .wizard__error {
    color: var(--chip-warn-fg);
    background: var(--chip-warn-bg);
    border: 1px solid var(--chip-warn-fg);
    border-radius: var(--radius);
    padding: 0.5rem 0.8rem;
    margin: 0;
    font-size: 0.88rem;
  }

  /* ── nav ── */
  .wizard__nav {
    display: flex;
    justify-content: space-between;
    gap: 0.6rem;
    padding-top: 0.2rem;
  }
  .btn {
    font: inherit;
    font-size: 0.9rem;
    font-weight: 600;
    padding: 0.55rem 1rem;
    border-radius: var(--radius);
    border: 1px solid var(--panel-line);
    background: var(--panel-bg);
    color: var(--fg);
    cursor: pointer;
    transition:
      border-color 0.12s ease,
      background 0.12s ease;
  }
  .btn:hover:not(:disabled) {
    border-color: var(--accent);
  }
  .btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .btn--accent {
    background: var(--accent);
    color: var(--color-bone);
    border-color: var(--accent);
  }
</style>
