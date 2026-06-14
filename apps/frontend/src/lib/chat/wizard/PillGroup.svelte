<script lang="ts">
  // A closed-set selector rendered as toggleable pills. Two modes:
  //   - multi (default): `selected` is a bindable string[] the pills toggle into/out of (the
  //     PROCESS step's sdlcPhases multi-select).
  //   - single: exactly one option is active; toggling one selects it (productKind, harness,
  //     posture). The bindable `value` holds the single choice.
  // Keyboard-accessible: each pill is a real button with aria-pressed; in single mode the group
  // carries role="radiogroup" and each pill role="radio"/aria-checked.

  interface Props {
    /** The closed option set, in display order. */
    options: readonly string[];
    /** The group label (rendered above the pills). */
    label: string;
    /** Multi-select mode: the bindable selection list. Required when mode === 'multi'. */
    selected?: string[];
    /** Single-select mode: the bindable single value. Required when mode === 'single'. */
    value?: string;
    /** 'multi' (toggle a list) or 'single' (radio-style). Defaults to 'multi'. */
    mode?: 'multi' | 'single';
    /** A stable testid stem: each pill is `${testid}-${option}`. */
    testid: string;
  }

  let {
    options,
    label,
    selected = $bindable([]),
    value = $bindable(''),
    mode = 'multi',
    testid,
  }: Props = $props();

  function isOn(option: string): boolean {
    return mode === 'single' ? value === option : selected.includes(option);
  }

  function toggle(option: string): void {
    if (mode === 'single') {
      value = option;
      return;
    }
    selected = selected.includes(option)
      ? selected.filter((item) => item !== option)
      : [...selected, option];
  }
</script>

<div class="pillgroup" data-testid={testid}>
  <span class="pillgroup__label">{label}</span>
  <div class="pillgroup__row" role={mode === 'single' ? 'radiogroup' : 'group'} aria-label={label}>
    {#each options as option (option)}
      <button
        type="button"
        class="pill"
        class:pill--on={isOn(option)}
        data-testid="{testid}-{option}"
        role={mode === 'single' ? 'radio' : undefined}
        aria-checked={mode === 'single' ? isOn(option) : undefined}
        aria-pressed={mode === 'multi' ? isOn(option) : undefined}
        onclick={() => toggle(option)}
      >
        {option}
      </button>
    {/each}
  </div>
</div>

<style>
  .pillgroup {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
  }
  .pillgroup__label {
    font-size: var(--type-micro);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--muted);
  }
  .pillgroup__row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
  }
  .pill {
    font: inherit;
    font-family: var(--font-code);
    font-size: 0.85rem;
    padding: 0.35rem 0.75rem;
    border-radius: 999px;
    border: 1px solid var(--panel-line);
    background: var(--panel-bg);
    color: var(--fg);
    cursor: pointer;
    transition:
      border-color 0.12s ease,
      background 0.12s ease,
      color 0.12s ease;
  }
  .pill:hover {
    border-color: var(--accent);
  }
  .pill:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 1px;
  }
  .pill--on {
    background: var(--accent);
    color: var(--color-bone);
    border-color: var(--accent);
  }
</style>
