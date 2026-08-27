<!--
  The Wave-1 a11y-evidence harness view (ADR-0024 / RD-16 · doc 17 §3/§4). Mounts the ATOM/MOLECULE
  set — Badge, Chip (incl. removable), Kbd, Spinner, Divider, Card, StatRow, Tabs, EmptyState — in a
  focusable sequence, so Playwright can run axe on the REAL Chromium AND WebKit engines and assert
  keyboard operability + token-driven colour + the 44px hit floor for the interactive members (the
  Chip remove control, the Tabs). Every element carries a data-testid so the spec can target it.
-->
<script lang="ts">
  import {
    Badge,
    Chip,
    Kbd,
    Spinner,
    Divider,
    Card,
    StatRow,
    Tabs,
    EmptyState,
    Button,
    type Stat,
    type Tab,
  } from '@eden/primitives';

  let removed = $state('');
  let activeTab = $state('overview');

  const stats: Stat[] = [
    { label: 'namespaces', value: '12' },
    { label: 'workloads', value: '48' },
    { label: 'services', value: '31' },
  ];
  const tabs: Tab[] = [
    { value: 'overview', label: 'Overview' },
    { value: 'build', label: 'Build' },
    { value: 'insight', label: 'Insight', disabled: true },
  ];
</script>

<div class="wave1-stack">
  <a href="#before" data-testid="before">before</a>

  <!-- Badges — the health vocabulary (each carries a status word, never colour alone). -->
  <section data-testid="badges" aria-label="badges">
    <Badge variant="healthy" status>Healthy</Badge>
    <Badge variant="updating" status>Updating</Badge>
    <Badge variant="degraded" status>Degraded</Badge>
    <Badge variant="down" status>Down</Badge>
    <Badge variant="unknown" status>Unknown</Badge>
    <Badge variant="neutral">12</Badge>
    <Badge variant="accent">beta</Badge>
  </section>

  <!-- Chips — the mono data chips; one removable (the interactive remove control). -->
  <section data-testid="chips" aria-label="chips">
    <Chip>ns/eden-42</Chip>
    <Chip>a1b2c3d</Chip>
    <Chip
      variant="removable"
      removeLabel="Remove namespace filter"
      onRemove={() => (removed = 'namespace')}
    >
      namespace
    </Chip>
    <output data-testid="chip-removed">{removed}</output>
  </section>

  <!-- Kbd — the ⌘K key caps. -->
  <section data-testid="kbds" aria-label="keyboard shortcuts">
    <Kbd>⌘K</Kbd>
    <Kbd>Esc</Kbd>
    <Kbd>↵</Kbd>
  </section>

  <!-- Spinner — the loading atom (role=status + visually-hidden label). -->
  <section data-testid="spinners" aria-label="spinners">
    <Spinner variant="accent" label="Loading projects" />
    <Spinner variant="updating" label="Updating cluster" />
  </section>

  <!-- Divider — the inset rule (horizontal + vertical). -->
  <section data-testid="dividers" aria-label="dividers">
    <span>left</span>
    <Divider orientation="vertical" />
    <span>right</span>
    <Divider orientation="horizontal" />
  </section>

  <!-- StatRow — the Clusters header number-row (mono values over overline labels). -->
  <section data-testid="stat-row" aria-label="cluster totals">
    <StatRow {stats} />
  </section>

  <!-- Card — the surface molecule (header/body/footer slots, raised + flat). -->
  <section data-testid="cards" aria-label="cards">
    <Card variant="raised" aria-label="Project card">
      {#snippet header()}<strong>eden-platform</strong>{/snippet}
      {#snippet body()}<p>A raised card with the surface radius + raised shadow.</p>{/snippet}
      {#snippet footer()}<span>updated 2m ago</span>{/snippet}
    </Card>
    <Card variant="flat" aria-label="Flat card">
      {#snippet body()}<p>A flat, outlined card (no shadow).</p>{/snippet}
    </Card>
  </section>

  <!-- Tabs — the segmented view-switcher (bits-ui behavior; roving focus + activation). -->
  <section data-testid="tabs" aria-label="tabs">
    <Tabs {tabs} bind:value={activeTab} label="Project views">
      {#snippet panel(value)}
        <p>Panel content for {value}.</p>
      {/snippet}
    </Tabs>
  </section>

  <!-- EmptyState — a product surface (serif headline · body · action · content slot). -->
  <section data-testid="empty-state" aria-label="empty state">
    <EmptyState headline="No projects yet" body="Create your first project to begin.">
      {#snippet action()}
        <Button variant="primary" onclick={() => undefined}>Create project</Button>
      {/snippet}
      {#snippet content()}
        <ul>
          <li>Start from a template</li>
          <li>Import an existing repository</li>
        </ul>
      {/snippet}
    </EmptyState>
  </section>

  <a href="#after" data-testid="after">after</a>
</div>

<style>
  .wave1-stack {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: var(--space-6, 24px);
    padding: var(--space-8, 32px);
  }
  section {
    display: flex;
    align-items: center;
    gap: var(--space-3, 12px);
    flex-wrap: wrap;
  }
</style>
