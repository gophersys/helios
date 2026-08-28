<!--
  The WizardShell a11y-evidence harness view (ADR-0024 / RD-16 · doc 17 §6). Mounts the full-screen
  wizard organism with a real 3-step model, a first-field input carrying the slot-forwarded autofocus
  action, and a footer of real Eden Buttons — so Playwright can run axe on the REAL Chromium AND WebKit
  engines and assert the FOCUS TRAP, ESCAPE-exit, ENTER-advance, reduced-motion static bar, and the
  token-driven serif/mono voices THROUGH the browser. The consumer puts `data-testid` + `data-step` on
  the root (the app-migration seam) and drives back/next itself (the shell owns layout + the contract).
-->
<script lang="ts">
  import { WizardShell, Button, type WizardStep } from '@eden/primitives';

  const steps: WizardStep[] = [
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

  let active = $state('spark');
  let answer = $state('');
  let exited = $state(false);
  let advanced = $state(0);

  const index = $derived(steps.findIndex((s) => s.id === active));

  function advance(): void {
    advanced += 1;
    const next = steps[index + 1];
    if (next) active = next.id;
  }
  function back(): void {
    const prev = steps[index - 1];
    if (prev) active = prev.id;
  }
  function exit(): void {
    exited = true;
  }
</script>

<a href="#before" data-testid="before">before</a>

<WizardShell
  {steps}
  {active}
  advanceable={true}
  onAdvance={advance}
  onExit={exit}
  data-testid="wizard"
  data-step={active}
>
  {#snippet body({ autofocus })}
    <label class="answer-field">
      <span class="answer-label">Your answer</span>
      <input use:autofocus bind:value={answer} data-testid="answer" placeholder="Type here…" />
    </label>
    <output data-testid="advanced">{advanced}</output>
    <output data-testid="exited">{exited ? 'exited' : ''}</output>
  {/snippet}

  {#snippet footer()}
    <Button variant="ghost" onclick={back} data-testid="back">Back</Button>
    <Button variant="primary" onclick={advance} data-testid="next">Next</Button>
  {/snippet}
</WizardShell>

<a href="#after" data-testid="after">after</a>

<style>
  .answer-field {
    display: flex;
    flex-direction: column;
    gap: var(--space-2, 8px);
  }
  .answer-label {
    font-size: var(--font-size-caption, 12px);
    color: var(--color-outline);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }
  input {
    box-sizing: border-box;
    inline-size: 100%;
    min-block-size: 44px;
    padding: var(--space-3, 12px);
    font-size: var(--font-size-body-large, 18px);
    color: var(--color-on-surface);
    background: var(--color-surface);
    border: 1px solid var(--color-outline);
    border-radius: var(--space-2, 8px);
  }
  input:focus-visible {
    outline: 2px solid var(--color-primary);
    outline-offset: 2px;
  }
</style>
