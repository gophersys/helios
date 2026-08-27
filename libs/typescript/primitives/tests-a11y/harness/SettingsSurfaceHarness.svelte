<!--
  The SettingsSurface a11y-evidence harness view (ADR-0024 / RD-16 · doc 17 §4/§7). Mounts the sheet-
  hosted Settings organism OPEN with a real 4-section model (Profile / Appearance / Agents / Connections),
  a per-section content snippet, and "before"/"after" page anchors OUTSIDE the sheet — so Playwright can
  run axe on the REAL Chromium AND WebKit engines and assert the FOCUS TRAP (Tab never escapes to the
  page anchors), ESCAPE-dismiss (the bits-ui Dialog behavior, reinvented nowhere), the rail's active
  state (aria-current), and the token-driven mono/sans voices THROUGH the portal. The consumer drives
  the active section itself (the surface owns the sheet + the rail; the consumer owns the content).
-->
<script lang="ts">
  import { SettingsSurface, Button, Field, Input, type SettingsSection } from '@eden/primitives';

  const sections: SettingsSection[] = [
    { id: 'profile', label: 'Profile' },
    { id: 'appearance', label: 'Appearance' },
    { id: 'agents', label: 'Agents' },
    { id: 'connections', label: 'Connections' },
  ];

  let open = $state(true);
  let active = $state('appearance');
</script>

<a href="#before" data-testid="before">before</a>
<button type="button" data-testid="open-settings" onclick={() => (open = true)}>Open settings</button>

<SettingsSurface {sections} bind:active bind:open title="Settings" data-testid="settings">
  {#snippet content(section)}
    {#if section === 'profile'}
      <div class="section" data-testid="section-profile">
        <h2 class="section__title">Profile</h2>
        <dl class="rows">
          <dt>Name</dt>
          <dd><code>Ada Lovelace</code></dd>
          <dt>Email</dt>
          <dd><code>ada@eden.dev</code></dd>
        </dl>
      </div>
    {:else if section === 'appearance'}
      <div class="section" data-testid="section-appearance">
        <h2 class="section__title">Appearance</h2>
        <div class="seg" role="radiogroup" aria-label="Colour mode">
          <button type="button" role="radio" aria-checked="true" data-testid="mode-light">Light</button>
          <button type="button" role="radio" aria-checked="false" data-testid="mode-dark">Dark</button>
          <button type="button" role="radio" aria-checked="false" data-testid="mode-system">System</button>
        </div>
      </div>
    {:else if section === 'agents'}
      <div class="section" data-testid="section-agents">
        <h2 class="section__title">Agents</h2>
        <Field label="Default model">
          {#snippet control({ id })}
            <Input {id} value="" placeholder="inherit" />
          {/snippet}
        </Field>
        <Button variant="primary" onclick={() => undefined}>Save</Button>
      </div>
    {:else}
      <div class="section" data-testid="section-connections">
        <h2 class="section__title">Connections</h2>
        <dl class="rows">
          <dt>Gateway</dt>
          <dd><code>gateway up</code></dd>
        </dl>
      </div>
    {/if}
  {/snippet}
</SettingsSurface>

<a href="#after" data-testid="after">after</a>

<style>
  .section {
    display: flex;
    flex-direction: column;
    gap: var(--space-4, 16px);
  }
  .section__title {
    margin: 0;
    font-size: var(--font-size-title, 20px);
    color: var(--color-on-surface);
  }
  .rows {
    margin: 0;
    display: grid;
    grid-template-columns: auto 1fr;
    gap: var(--space-2, 8px) var(--space-4, 16px);
    color: var(--color-on-surface);
  }
  dt {
    color: var(--color-outline);
    font-size: var(--font-size-caption, 12px);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }
  code {
    font-family: monospace;
    color: var(--color-on-surface);
  }
  .seg {
    display: inline-flex;
    gap: var(--space-1, 4px);
  }
  .seg button {
    min-block-size: 44px;
    padding: var(--space-2, 8px) var(--space-4, 16px);
    background: var(--color-surface);
    color: var(--color-on-surface);
    border: 1px solid var(--color-outline);
    border-radius: var(--space-2, 8px);
    cursor: pointer;
  }
  .seg button[aria-checked='true'] {
    border-color: var(--color-primary);
    color: var(--color-primary);
  }
  .seg button:focus-visible {
    outline: 2px solid var(--color-primary);
    outline-offset: 2px;
  }
</style>
