<!--
  The form-action a11y-evidence harness view (ADR-0024 / RD-16). Mounts the FORM/ACTION component
  group — the Button variants (primary/secondary/ghost/danger), the IconButton, a standalone Input
  and Textarea, and two Fields (one valid, one erroring) — in a focusable sequence so a Tab-order
  assertion can prove each control participates in the natural tab sequence. Every control carries a
  data-testid so the spec can target it across the Chromium AND WebKit engines.
-->
<script lang="ts">
  import { Button, IconButton, Input, Textarea, Field } from '@eden/primitives';

  let email = $state('');
  let bio = $state('');
</script>

<div class="form-harness-stack">
  <a href="#before" data-testid="before">before</a>

  <!-- Button — all four variants (danger added in this build). -->
  <div class="row">
    <Button variant="primary" onclick={() => undefined}>Primary action</Button>
    <Button variant="secondary" onclick={() => undefined}>Secondary action</Button>
    <Button variant="ghost" onclick={() => undefined}>Ghost action</Button>
    <Button variant="danger" onclick={() => undefined}>Danger action</Button>
    <Button variant="primary" disabled onclick={() => undefined}>Disabled action</Button>
  </div>

  <!-- IconButton — icon-only, REQUIRED accessible name via the label prop. -->
  <div class="row">
    <IconButton label="Close panel" variant="primary" onclick={() => undefined}>
      <svg
        viewBox="0 0 24 24"
        aria-hidden="true"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
      >
        <path d="M6 6l12 12M18 6L6 18" />
      </svg>
    </IconButton>
    <IconButton label="Delete item" variant="danger" onclick={() => undefined}>
      <svg
        viewBox="0 0 24 24"
        aria-hidden="true"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
      >
        <path d="M5 7h14M9 7V5h6v2M7 7l1 12h8l1-12" />
      </svg>
    </IconButton>
  </div>

  <!-- Standalone Input + Textarea (aria-label, since they are not inside a Field here). A plain
       text input is the canonical `textbox` role; a textarea is also a `textbox`. -->
  <Input aria-label="Search" type="text" placeholder="Search…" bind:value={email} />
  <Textarea aria-label="Notes" placeholder="Notes…" rows={3} bind:value={bio} />

  <!-- Field — the label + control + error wiring. One valid, one erroring (role=alert). -->
  <Field label="Email address">
    {#snippet control({ id, describedby, invalid })}
      <Input
        {id}
        aria-describedby={describedby}
        {invalid}
        type="email"
        placeholder="you@example.com"
      />
    {/snippet}
  </Field>

  <Field label="Message" error="A message is required.">
    {#snippet control({ id, describedby, invalid })}
      <Textarea
        {id}
        aria-describedby={describedby}
        {invalid}
        rows={3}
        placeholder="Type your message…"
      />
    {/snippet}
  </Field>

  <a href="#after" data-testid="after">after</a>
</div>

<style>
  .form-harness-stack {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: var(--space-6, 24px);
    padding: var(--space-8, 32px);
    max-inline-size: 28rem;
  }
  .row {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-4, 16px);
  }
  .form-harness-stack :global(.eden-input),
  .form-harness-stack :global(.eden-textarea) {
    inline-size: 100%;
  }
</style>
