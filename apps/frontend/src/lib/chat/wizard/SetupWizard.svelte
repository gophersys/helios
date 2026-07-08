<script lang="ts">
  // SETUP WIZARD — the in-workspace product-scoping interview a project runs while its lifecycle
  // status is `wizard`. THE WIZARD IS THE SUPERVISOR'S FSM MADE VISIBLE: the supervisor session (the
  // live build agent the create-saga launched) drives the interview, and this surface renders that
  // interview from the artifacts the supervisor COMMITS to the project's workspace worktree
  // (init/product/questionnaire/* → the questions, init/product/answers/* → the recorded answers),
  // live, plus the supervisor session's SSE activity.
  //
  // W3: the presentation is now the shared full-screen @eden/primitives WizardShell (doc 17 §6) —
  // one question per screen, serif display question, mono `1 / 4` counter, thin progress bar, Enter
  // advances, Esc offers exit. ONLY the presentation moved: the four steps, the 1200ms worktree poll,
  // the SSE ChatSession lifecycle, every setup-* testid + data-step/data-ready/data-open-questions
  // attr, and the WizardSource I/O seam are all EXACTLY as before.
  //
  // The four steps (setupWizard.WIZARD_STEPS) mirror the supervisor's interview phases:
  //   1. STACKS        — choose the platform targets (web/desktop/mobile, a GROWABLE list).
  //   2. DESCRIBE      — a 100-word "describe the simplest product" brief, fed to the supervisor; this
  //                      is what makes the supervisor commit the questionnaire.
  //   3. QUESTIONNAIRE — the supervisor's committed questions arrive under init/product/questionnaire/*,
  //                      rendered LIVE from the worktree (polled — there is no project-level SSE yet).
  //   4. QA            — each answer posts to the supervisor + commits init/product/answers/*; the
  //                      ADVANCE GUARD (no open questions) gates finishing the step.
  //
  // It owns only local flow state + the worktree poll. All I/O is the injected WizardSource
  // (chat/wizard/wizardSource.ts) — list/read the committed files + send to the supervisor — so this
  // stays a pure, testable view: the live wizard binds the source to the gateway, the E2E binds a
  // FAKE supervisor file source + session.

  import { fade } from 'svelte/transition';
  import type { Theme } from '@eden/theme';
  import { WizardShell, type WizardStep as ShellStep } from '@eden/primitives';
  import type { ChatSession } from '$lib/gateway/session.svelte';
  import ChatStatusBar from '$lib/chat/ChatStatusBar.svelte';
  import {
    WIZARD_STACKS,
    WIZARD_STEPS,
    DESCRIBE_WORD_LIMIT,
    QUESTIONNAIRE_PREFIX,
    ANSWERS_PREFIX,
    countWords,
    describeWithinLimit,
    parseQuestions,
    parseAnswers,
    joinQuestions,
    hasOpenQuestions,
    questionnaireReady,
    type WizardStep,
    type WizardQuestionState,
  } from './setupWizard';
  import { loadFiles, type WizardSource } from './wizardSource';

  interface Props {
    /** The supervisor's committed-artifact + session-send seam (gateway-bound live, fake in the E2E). */
    source: WizardSource;
    /** The project name, shown in the header. */
    projectName: string;
    /** The live supervisor ChatSession, for the status bar (the FSM activity made visible). Optional
     *  — the wizard renders its content from the worktree regardless; the session only drives chrome. */
    session?: ChatSession | null;
    /** Invoked once the interview is complete (no open questions) and the user confirms — the host
     *  routes into the build workspace. */
    onfinish: () => void;
    /** The active generated theme, handed uniformly with every Eden component. */
    theme?: Theme;
    /** The worktree poll cadence (ms). The supervisor commits asynchronously and there is no
     *  project-level SSE yet, so the wizard polls the committed-artifact listing. */
    pollIntervalMs?: number;
  }
  let {
    source,
    projectName,
    session = null,
    onfinish,
    theme,
    pollIntervalMs = 1200,
  }: Props = $props();

  let step = $state<WizardStep>('stacks');
  let error = $state<string | null>(null);

  // ── step 1: stacks ──────────────────────────────────────────────────────────.
  let selectedStacks = $state<Set<string>>(new Set(['web']));
  const stacksValid = $derived(selectedStacks.size > 0);
  function toggleStack(id: string): void {
    const next = new Set(selectedStacks);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    selectedStacks = next;
  }

  // ── step 2: describe ────────────────────────────────────────────────────────.
  let brief = $state('');
  const briefWords = $derived(countWords(brief));
  const briefValid = $derived(describeWithinLimit(brief));
  let sending = $state(false);

  // ── steps 3+4: the supervisor's committed questionnaire + answers (live from the worktree) ──.
  let questions = $state<WizardQuestionState[]>([]);
  let questionnaireLoaded = $state(false);
  const ready = $derived(questionnaireReady(questions.map((s) => s.question)));
  const openQuestions = $derived(hasOpenQuestions(questions));
  // The per-question answer drafts (by question id), so the Q&A textareas are independent.
  let drafts = $state<Record<string, string>>({});
  let answering = $state<string | null>(null);

  // ── the WizardShell step metadata (the mono eyebrow + serif question + one-sentence lead per
  //    screen — the copy budget: question ≤ 6 words, helper ≤ 1 sentence, doc 17 §6). The 4 ids match
  //    WIZARD_STEPS exactly, so the progress bar length + `1 / 4` counter are the real step count. ──.
  const SHELL_STEPS: readonly ShellStep[] = [
    {
      id: 'stacks',
      eyebrow: 'Set up',
      title: 'What are you building?',
      lead: 'Pick the platforms your product needs — choose more than one.',
    },
    {
      id: 'describe',
      eyebrow: 'In one breath',
      title: 'Describe the simplest product',
      lead: 'The simplest version that’s still useful — the supervisor asks the rest.',
    },
    {
      id: 'questionnaire',
      eyebrow: 'The supervisor is scoping',
      title: 'A few questions',
      lead: 'The supervisor drafts what it needs to know. Review, then answer.',
    },
    {
      id: 'qa',
      eyebrow: 'Answer',
      title: 'Tell the supervisor',
      lead: 'Answer each question — every one is needed before the build starts.',
    },
  ];

  // Enter advances only when the active step is legal to advance (a valid field / a committed
  // questionnaire / no open questions). The shell keeps native Enter inside a textarea, so the brief
  // + answer boxes are never hijacked; this gates the button-equivalent transitions.
  const advanceable = $derived(
    (step === 'stacks' && stacksValid) ||
      (step === 'questionnaire' && ready) ||
      (step === 'qa' && ready && !openQuestions),
  );

  /** Reload the committed init/product/* artifacts from the worktree and re-derive the question
   *  state. Surfaced (never swallowed) on fault, but a transient read fault does NOT clear the
   *  already-rendered questionnaire (a gateway blip must not blank the interview). */
  async function reloadArtifacts(): Promise<void> {
    try {
      const [questionnaireFiles, answerFiles] = await Promise.all([
        loadFiles(source, QUESTIONNAIRE_PREFIX),
        loadFiles(source, ANSWERS_PREFIX),
      ]);
      const parsedQuestions = parseQuestions(questionnaireFiles);
      const parsedAnswers = parseAnswers(answerFiles);
      questions = joinQuestions(parsedQuestions, parsedAnswers);
      questionnaireLoaded = true;
      error = null;
    } catch (cause) {
      error = cause instanceof Error ? cause.message : String(cause);
    }
  }

  // Poll the worktree while the wizard is on the questionnaire/Q&A steps (the supervisor commits
  // asynchronously). The loop runs only on those steps and stops the instant the user leaves them.
  let pollTimer: ReturnType<typeof setInterval> | null = null;
  function startPolling(): void {
    stopPolling();
    void reloadArtifacts();
    pollTimer = setInterval(() => void reloadArtifacts(), pollIntervalMs);
  }
  function stopPolling(): void {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }
  $effect(() => {
    if (step === 'questionnaire' || step === 'qa') startPolling();
    else stopPolling();
    return stopPolling;
  });

  /** STACKS → DESCRIBE. */
  function toDescribe(): void {
    if (!stacksValid) return;
    error = null;
    step = 'describe';
  }
  function backToStacks(): void {
    error = null;
    step = 'stacks';
  }

  /** DESCRIBE → send the brief to the supervisor (this is what drives it to commit the
   *  questionnaire), then advance to the QUESTIONNAIRE step where it renders live. The brief is
   *  prefixed with the chosen stacks so the supervisor scopes against the targets. */
  async function submitBrief(): Promise<void> {
    if (!briefValid || sending) return;
    sending = true;
    error = null;
    const stacks = [...selectedStacks].join(', ');
    const message = `Stacks: ${stacks}\n\nProduct brief: ${brief.trim()}`;
    try {
      await source.sendToSupervisor(message);
      step = 'questionnaire';
    } catch (cause) {
      error = cause instanceof Error ? cause.message : String(cause);
    } finally {
      sending = false;
    }
  }
  function backToDescribe(): void {
    error = null;
    step = 'describe';
  }

  /** QUESTIONNAIRE → Q&A. Gated on the supervisor having committed at least one question. */
  function toQa(): void {
    if (!ready) return;
    error = null;
    step = 'qa';
  }
  function backToQuestionnaire(): void {
    error = null;
    step = 'questionnaire';
  }

  /** Answer one question: post it to the supervisor (which records it under init/product/answers/),
   *  then optimistically reload the artifacts so the answer reflects the instant it commits. */
  async function answerQuestion(state: WizardQuestionState): Promise<void> {
    const draft = (drafts[state.question.id] ?? '').trim();
    if (!draft || answering) return;
    answering = state.question.id;
    error = null;
    const message = `Answer to "${state.question.id}": ${draft}`;
    try {
      await source.sendToSupervisor(message);
      drafts = { ...drafts, [state.question.id]: '' };
      await reloadArtifacts();
    } catch (cause) {
      error = cause instanceof Error ? cause.message : String(cause);
    } finally {
      answering = null;
    }
  }

  /** Finish: only legal once the questionnaire exists and no question is open (the advance guard). */
  function finish(): void {
    if (!ready || openQuestions) return;
    onfinish();
  }

  function setDraft(id: string, value: string): void {
    drafts = { ...drafts, [id]: value };
  }

  // The shell's Enter-advance intent maps to the current step's forward transition (guarded by
  // `advanceable`, so an illegal step never fires). DESCRIBE's send is an explicit button (Enter
  // inside the brief textarea stays native), and answering a single question is its own button.
  function onAdvance(): void {
    if (step === 'stacks') toDescribe();
    else if (step === 'questionnaire') toQa();
    else if (step === 'qa') finish();
  }
</script>

<WizardShell
  steps={SHELL_STEPS}
  active={step}
  {theme}
  {advanceable}
  {onAdvance}
  label="Set up your project"
  data-testid="setup-wizard"
  data-step={step}
  data-ready={ready}
  data-open-questions={openQuestions}
>
  {#snippet body({ autofocus })}
    <p class="flow__name" data-testid="setup-project-name">{projectName}</p>

    {#if step === 'stacks'}
      <!-- ── 1. STACKS ───────────────────────────────────────────────────────── -->
      <ul class="stacks" role="list" data-testid="setup-stack-list">
        {#each WIZARD_STACKS as stack, index (stack.id)}
          {@const on = selectedStacks.has(stack.id)}
          <li>
            <button
              type="button"
              class="stack"
              class:stack--on={on}
              data-testid="setup-stack"
              data-stack-id={stack.id}
              data-selected={on}
              aria-pressed={on}
              onclick={() => toggleStack(stack.id)}
            >
              <span class="stack__glyph" aria-hidden="true">{stack.glyph}</span>
              <span class="stack__body">
                <span class="stack__label">{stack.label}</span>
                <span class="stack__hint">{stack.hint}</span>
              </span>
              <span class="stack__check" aria-hidden="true">{on ? '✓' : ''}</span>
            </button>
          </li>
        {/each}
      </ul>
    {:else if step === 'describe'}
      <!-- ── 2. DESCRIBE ─────────────────────────────────────────────────────── -->
      <div class="describe">
        <textarea
          class="brief"
          data-testid="setup-brief"
          rows="4"
          aria-label="Describe the simplest product"
          placeholder="A dashboard that turns my raw invoices into a clean monthly summary…"
          bind:value={brief}
          use:autofocus
        ></textarea>
        <p
          class="brief__count"
          class:brief__count--over={briefWords > DESCRIBE_WORD_LIMIT}
          data-testid="setup-brief-count"
          aria-live="polite"
        >
          {briefWords} / {DESCRIBE_WORD_LIMIT} words
        </p>
      </div>
    {:else if step === 'questionnaire'}
      <!-- ── 3. QUESTIONNAIRE (live from the worktree) ───────────────────────── -->
      <div data-testid="setup-questionnaire" in:fade={{ duration: 200 }}>
        {#if !ready}
          <div class="waiting" data-testid="setup-questionnaire-waiting" role="status">
            <span class="waiting__spinner" aria-hidden="true"></span>
            <p class="lead">
              {questionnaireLoaded
                ? 'Waiting for the supervisor to draft the questionnaire…'
                : 'Reading the supervisor’s notes…'}
            </p>
          </div>
        {:else}
          <p class="lead">
            The supervisor committed {questions.length} question{questions.length === 1 ? '' : 's'}.
            Review them, then answer.
          </p>
          <ul
            class="questions questions--preview"
            role="list"
            data-testid="setup-question-preview-list"
          >
            {#each questions as state (state.question.id)}
              <li
                class="question"
                data-testid="setup-question-preview"
                data-question-id={state.question.id}
                data-path={state.question.path}
              >
                <span class="question__path">{state.question.path}</span>
                <p class="question__prompt">{state.question.prompt}</p>
              </li>
            {/each}
          </ul>
        {/if}
      </div>
    {:else if step === 'qa'}
      <!-- ── 4. Q&A ──────────────────────────────────────────────────────────── -->
      <div data-testid="setup-qa">
        <p class="qa-status">
          {#if openQuestions}
            {questions.filter((q) => q.open).length} still open — answer each to continue.
          {:else}
            Everything's answered. You're ready to build.
          {/if}
        </p>
        <ul class="questions" role="list" data-testid="setup-qa-list">
          {#each questions as state (state.question.id)}
            <li
              class="question question--qa"
              class:question--answered={!state.open}
              data-testid="setup-qa-item"
              data-question-id={state.question.id}
              data-open={state.open}
            >
              <p class="question__prompt">{state.question.prompt}</p>
              {#if state.answer}
                <p class="question__answer" data-testid="setup-qa-answer">{state.answer.text}</p>
              {:else}
                <div class="qa__compose">
                  <textarea
                    class="qa__input"
                    data-testid="setup-qa-input"
                    data-question-id={state.question.id}
                    rows="2"
                    aria-label={`Answer: ${state.question.prompt}`}
                    placeholder="Your answer…"
                    value={drafts[state.question.id] ?? ''}
                    oninput={(event) => setDraft(state.question.id, event.currentTarget.value)}
                  ></textarea>
                  <button
                    type="button"
                    class="btn btn--accent qa__send"
                    data-testid="setup-qa-send"
                    data-question-id={state.question.id}
                    disabled={answering === state.question.id ||
                      (drafts[state.question.id] ?? '').trim().length === 0}
                    onclick={() => answerQuestion(state)}
                  >
                    {answering === state.question.id ? 'Sending…' : 'Answer'}
                  </button>
                </div>
              {/if}
            </li>
          {/each}
        </ul>
      </div>
    {/if}

    {#if error}
      <p class="flow__error" data-testid="setup-error" role="alert">{error}</p>
    {/if}

    <!-- the live supervisor status (the FSM activity made visible) -->
    {#if session}
      <div class="flow__status" data-testid="setup-status">
        <ChatStatusBar {session} {theme} />
      </div>
    {/if}
  {/snippet}

  {#snippet footer()}
    {#if step === 'stacks'}
      <span class="nav-spacer"></span>
      <button
        type="button"
        class="btn btn--accent"
        data-testid="setup-next"
        disabled={!stacksValid}
        onclick={toDescribe}>Continue →</button
      >
    {:else if step === 'describe'}
      <button type="button" class="btn" data-testid="setup-back" onclick={backToStacks}
        >← Back</button
      >
      <button
        type="button"
        class="btn btn--accent"
        data-testid="setup-send-brief"
        disabled={!briefValid || sending}
        onclick={submitBrief}>{sending ? 'Sending…' : 'Send to supervisor →'}</button
      >
    {:else if step === 'questionnaire'}
      <button type="button" class="btn" data-testid="setup-back" onclick={backToDescribe}
        >← Back</button
      >
      <button
        type="button"
        class="btn btn--accent"
        data-testid="setup-next"
        disabled={!ready}
        onclick={toQa}>Answer the questions →</button
      >
    {:else if step === 'qa'}
      <button type="button" class="btn" data-testid="setup-back" onclick={backToQuestionnaire}
        >← Back</button
      >
      <button
        type="button"
        class="btn btn--accent"
        data-testid="setup-finish"
        disabled={!ready || openQuestions}
        onclick={finish}>Start building →</button
      >
    {/if}
  {/snippet}
</WizardShell>

<style>
  /* ── token bridge ─────────────────────────────────────────────────────────.
     The WizardShell owns the surface / title / lead / eyebrow / counter / progress appearance (all
     @eden/theme-derived, no literals). This subtree styles only the STEP BODY content + the FOOTER
     buttons, bridging the generated @eden/theme role tokens to the --accent/--fg/--panel-* vocabulary
     this content reads — one hue source, no hand-set hex/px on a painted role. ── */
  .stacks,
  .describe,
  .questions,
  .qa-status,
  .waiting,
  .flow__name,
  .flow__status,
  .flow__error,
  .btn {
    --accent: var(--color-primary);
    --on-accent: var(--color-on-primary);
    --fg: var(--color-on-surface);
    --muted: var(
      --eden-app-muted,
      color-mix(in oklab, var(--color-on-surface) 62%, var(--color-surface))
    );
    --panel-bg: var(--color-surface);
    --panel-line: var(--color-outline);
    --radius: var(--eden-app-radius, var(--space-2, 8px));
    --micro: var(--font-size-caption, 12px);
    --warn: var(--color-warning);
  }

  .flow__name {
    margin: 0 0 0.4rem;
    font-family: var(--font-code);
    font-size: var(--micro);
    font-weight: 600;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }
  .lead {
    margin: 0 0 0.6rem;
    color: var(--color-outline);
    line-height: 1.5;
  }

  /* ── STACKS ── */
  .stacks {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
  }
  .stack {
    inline-size: 100%;
    display: flex;
    align-items: center;
    gap: 0.85rem;
    padding: 0.9rem 1rem;
    border: 1.5px solid var(--panel-line);
    border-radius: calc(var(--radius) * 1.25);
    background: color-mix(in oklab, var(--fg) 2%, var(--panel-bg));
    color: var(--fg);
    cursor: pointer;
    text-align: start;
    font: inherit;
    /* W5: the stack toggles ride the theme motion tokens (nearest ladder step + standard easing). */
    transition:
      border-color var(--duration-short-3, 0.15s) var(--ease-standard, ease),
      background var(--duration-short-3, 0.15s) var(--ease-standard, ease),
      transform var(--duration-short-1, 0.08s) var(--ease-standard, ease);
  }
  .stack:hover {
    border-color: color-mix(in oklab, var(--accent) 55%, var(--panel-line));
  }
  .stack:active {
    transform: translateY(1px);
  }
  .stack:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }
  .stack--on {
    border-color: var(--accent);
    background: color-mix(in oklab, var(--accent) 12%, var(--panel-bg));
  }
  .stack__glyph {
    font-size: 1.3rem;
    color: var(--accent);
    flex: none;
    width: 1.6rem;
    text-align: center;
  }
  .stack__body {
    display: flex;
    flex-direction: column;
    gap: 0.1rem;
    flex: 1;
    min-inline-size: 0;
  }
  .stack__label {
    font-weight: 650;
    color: var(--fg);
  }
  .stack__hint {
    font-size: 0.85rem;
    color: var(--muted);
  }
  .stack__check {
    flex: none;
    inline-size: 1.3rem;
    text-align: center;
    color: var(--accent);
    font-weight: 700;
  }

  /* ── DESCRIBE ── */
  .describe {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  .brief {
    font: inherit;
    font-size: 1.05rem;
    padding: 0.9rem 1.1rem;
    border: 1px solid var(--panel-line);
    border-radius: calc(var(--radius) * 1.25);
    background: color-mix(in oklab, var(--fg) 2%, var(--panel-bg));
    color: var(--fg);
    resize: vertical;
    line-height: 1.5;
    min-height: 7rem;
  }
  .brief::placeholder {
    color: color-mix(in oklab, var(--muted) 85%, transparent);
  }
  .brief:focus-visible {
    outline: none;
    border-color: var(--accent);
    box-shadow: 0 0 0 2px color-mix(in oklab, var(--accent) 35%, transparent);
  }
  .brief__count {
    margin: 0;
    align-self: flex-end;
    font-family: var(--font-code);
    font-size: var(--micro);
    color: var(--muted);
  }
  .brief__count--over {
    color: var(--warn);
    font-weight: 700;
  }

  /* ── QUESTIONNAIRE + Q&A ── */
  .qa-status {
    margin: 0 0 0.6rem;
    color: var(--color-outline);
    line-height: 1.5;
  }
  .waiting {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.9rem;
    padding: 2rem 1rem;
    text-align: center;
  }
  .waiting__spinner {
    inline-size: 1.9rem;
    block-size: 1.9rem;
    border-radius: 50%;
    border: 2.5px solid color-mix(in oklab, var(--accent) 28%, transparent);
    border-block-start-color: var(--accent);
    animation: setup-spin 0.7s linear infinite;
  }
  .questions {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
  }
  .question {
    border: 1px solid var(--panel-line);
    border-radius: calc(var(--radius) * 1.25);
    background: color-mix(in oklab, var(--fg) 2%, var(--panel-bg));
    padding: 0.85rem 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  .question__path {
    font-family: var(--font-code);
    font-size: 0.76rem;
    color: var(--muted);
    overflow-wrap: anywhere;
  }
  .question__prompt {
    margin: 0;
    color: var(--fg);
    line-height: 1.5;
    font-weight: 550;
  }
  .question--answered {
    border-color: color-mix(in oklab, var(--accent) 45%, var(--panel-line));
  }
  .question__answer {
    margin: 0;
    padding: 0.5rem 0.7rem;
    border-radius: var(--radius);
    background: color-mix(in oklab, var(--accent) 10%, var(--panel-bg));
    color: var(--fg);
    line-height: 1.5;
  }
  .qa__compose {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  .qa__input {
    font: inherit;
    font-size: 0.98rem;
    padding: 0.65rem 0.8rem;
    border: 1px solid var(--panel-line);
    border-radius: var(--radius);
    background: var(--panel-bg);
    color: var(--fg);
    resize: vertical;
    line-height: 1.5;
    min-height: 3rem;
  }
  .qa__input:focus-visible {
    outline: none;
    border-color: var(--accent);
    box-shadow: 0 0 0 2px color-mix(in oklab, var(--accent) 30%, transparent);
  }
  .qa__send {
    align-self: flex-end;
  }

  .flow__status {
    border-block-start: 1px solid var(--panel-line);
    margin-block-start: 0.8rem;
    padding-block-start: 0.6rem;
  }

  .flow__error {
    margin: 0.6rem 0 0;
    padding: 0.5rem 0.8rem;
    border-radius: var(--radius);
    color: var(--warn);
    background: color-mix(in oklab, var(--warn) 12%, var(--panel-bg));
    border: 1px solid color-mix(in oklab, var(--warn) 45%, transparent);
    font-size: 0.88rem;
  }

  /* ── footer buttons — native <button> carries the load-bearing setup-* testid directly (the e2e
     asserts setup-next / setup-send-brief / setup-finish by testid AND reads their disabled state +
     painted accent background — a wrapper would break both); `.btn` is a sampled UI-math class. ── */
  .nav-spacer {
    flex: 1;
  }
  .btn {
    font: inherit;
    font-size: 0.95rem;
    font-weight: 600;
    padding: 0.65rem 1.2rem;
    border-radius: calc(var(--radius) * 1.25);
    border: 1px solid var(--panel-line);
    background: var(--panel-bg);
    color: var(--fg);
    cursor: pointer;
    transition:
      border-color var(--duration-short-2, 0.12s) var(--ease-standard, ease),
      background var(--duration-short-2, 0.12s) var(--ease-standard, ease),
      transform var(--duration-short-1, 0.08s) var(--ease-standard, ease);
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

  @keyframes setup-spin {
    to {
      transform: rotate(360deg);
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .waiting__spinner {
      animation: none;
    }
    .stack,
    .btn {
      transition: none;
    }
  }
</style>
