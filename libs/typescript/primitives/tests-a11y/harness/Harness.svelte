<!--
  The a11y-evidence harness view. Mounts every Button variant in a focusable sequence (a sibling
  control before and after each, so a Tab-order assertion can prove the button participates in the
  natural tab sequence). The buttons carry data-testid so the spec can target them across engines.
-->
<script lang="ts">
  import {
    Button,
    Dialog,
    Popover,
    Tooltip,
    DropdownMenu,
    CommandPalette,
    type CommandPaletteGroup,
  } from '@eden/primitives';

  // A second, NESTED dialog (the OD-1 LIFO proof): the spec opens the outer dialog, then the inner,
  // then asserts Escape unwinds them last-in-first-out. Both are uncontrolled (bits-ui owns the state).
  let menuChoice = $state('');

  // The command palette (the OD-1 ⌘K): closed at rest so it does not interfere with the other axe
  // runs; the spec opens it via the trigger (two-way bind:open) and asserts axe-clean + keyboard
  // (Arrow/Enter/Escape, aria-activedescendant) + grouped roles through the portal.
  let paletteOpen = $state(false);
  let paletteValue = $state('');
  let paletteChoice = $state('');
  const paletteGroups: CommandPaletteGroup[] = [
    {
      value: 'navigation',
      heading: 'Navigation',
      items: [
        { value: 'go-home', label: 'Go to Home' },
        { value: 'go-settings', label: 'Open Settings', keywords: ['preferences'] },
        { value: 'go-inbox', label: 'Open Inbox' },
      ],
    },
    {
      value: 'actions',
      heading: 'Actions',
      items: [
        { value: 'new-file', label: 'Create file', keywords: ['new', 'document'] },
        { value: 'rename', label: 'Rename' },
        { value: 'delete', label: 'Delete', disabled: true },
      ],
    },
  ];
</script>

<div class="harness-stack">
  <a href="#before" data-testid="before">before</a>

  <Button variant="primary" onclick={() => undefined}>Primary action</Button>

  <Button variant="secondary" onclick={() => undefined}>Secondary action</Button>

  <Button variant="ghost" onclick={() => undefined}>Ghost action</Button>

  <Button variant="primary" disabled onclick={() => undefined}>Disabled action</Button>

  <!-- ── Overlay group (RD-16/OD-1): each closed at rest, so it does not interfere with the Button
       axe run; the spec opens each by its trigger and asserts axe-clean + keyboard through the portal. -->
  <section data-testid="overlays" aria-label="overlays">
    <Dialog title="Edit profile" description="Make changes to your profile here.">
      {#snippet trigger()}<span data-testid="dialog-trigger">Open dialog</span>{/snippet}
      <p>Dialog body content.</p>
      <Dialog title="Confirm discard" description="Discard unsaved changes?">
        {#snippet trigger()}<span data-testid="dialog-nested-trigger">Open nested dialog</span
          >{/snippet}
        <p>Nested dialog body (the LIFO proof).</p>
      </Dialog>
    </Dialog>

    <Popover>
      {#snippet trigger()}<span data-testid="popover-trigger">Open popover</span>{/snippet}
      <p>Popover body content.</p>
    </Popover>

    <Tooltip delayDuration={0}>
      {#snippet trigger()}<span data-testid="tooltip-trigger">Hover me</span>{/snippet}
      Tooltip label content.
    </Tooltip>

    <DropdownMenu
      items={[
        { label: 'Rename', onSelect: () => (menuChoice = 'Rename') },
        { label: 'Duplicate', onSelect: () => (menuChoice = 'Duplicate') },
        { label: 'Delete', onSelect: () => (menuChoice = 'Delete'), disabled: true },
      ]}
    >
      {#snippet trigger()}<span data-testid="menu-trigger">Open menu</span>{/snippet}
    </DropdownMenu>
    <output data-testid="menu-choice">{menuChoice}</output>
  </section>

  <!-- ── Command palette (RD-16/OD-1 ⌘K): closed at rest. The spec opens it via this trigger and
       asserts axe-clean + keyboard (Arrow/Enter/Escape, aria-activedescendant) + grouped roles
       through the portal; bind:value reads the selected command, onSelect records the choice. -->
  <section data-testid="command-palette" aria-label="command palette">
    <button type="button" data-testid="palette-trigger" onclick={() => (paletteOpen = true)}>
      Open command palette
    </button>
    <CommandPalette
      groups={paletteGroups}
      bind:open={paletteOpen}
      bind:value={paletteValue}
      label="Command palette"
      placeholder="Type a command or search…"
      onSelect={(v) => (paletteChoice = v)}
    />
    <output data-testid="palette-choice">{paletteChoice}</output>
    <output data-testid="palette-value">{paletteValue}</output>
  </section>

  <a href="#after" data-testid="after">after</a>
</div>

<style>
  .harness-stack {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: var(--space-4, 16px);
    padding: var(--space-8, 32px);
  }
</style>
