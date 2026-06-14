<script lang="ts">
  // An editable string-array field rendered as removable chips plus an add-input. Used across the
  // product wizard for the open-ended list fields (languages, frameworks, services, toolGrants,
  // skills, rules, egressAllow). Pure presentation over a bindable string[] — the parent owns the
  // value; this only mutates it. Keyboard-accessible: Enter (or comma) commits the typed token,
  // Backspace on an empty input removes the last chip, and each chip's ✕ is a real button.

  interface Props {
    /** The bindable list this editor mutates in place. */
    items: string[];
    /** The field label (rendered above the chips). */
    label: string;
    /** Placeholder for the add-input. */
    placeholder?: string;
    /** A stable testid stem: the input is `${testid}-input`, each chip `${testid}-chip`. */
    testid: string;
  }

  let { items = $bindable(), label, placeholder = 'Add…', testid }: Props = $props();

  let draft = $state('');

  function commit(): void {
    const token = draft.trim();
    draft = '';
    if (!token) return;
    if (items.includes(token)) return; // set semantics — no duplicates
    items = [...items, token];
  }

  function removeAt(index: number): void {
    items = items.filter((_, i) => i !== index);
  }

  function onKeydown(event: KeyboardEvent): void {
    if (event.key === 'Enter' || event.key === ',') {
      event.preventDefault();
      commit();
      return;
    }
    if (event.key === 'Backspace' && draft === '' && items.length > 0) {
      removeAt(items.length - 1);
    }
  }
</script>

<div class="chipinput" data-testid={testid}>
  <span class="chipinput__label">{label}</span>
  <div class="chipinput__box">
    {#each items as item, index (item)}
      <span class="tag" data-testid="{testid}-chip">
        <span class="tag__text">{item}</span>
        <button
          type="button"
          class="tag__remove"
          aria-label={`Remove ${item}`}
          data-testid="{testid}-remove"
          onclick={() => removeAt(index)}>✕</button
        >
      </span>
    {/each}
    <input
      class="chipinput__input"
      data-testid="{testid}-input"
      {placeholder}
      bind:value={draft}
      onkeydown={onKeydown}
      onblur={commit}
      autocomplete="off"
    />
  </div>
</div>

<style>
  .chipinput {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
  }
  .chipinput__label {
    font-size: var(--type-micro);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--muted);
  }
  .chipinput__box {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.4rem;
    padding: 0.45rem 0.5rem;
    border: 1px solid var(--panel-line);
    border-radius: var(--radius);
    background: var(--panel-bg);
  }
  .chipinput__box:focus-within {
    border-color: var(--accent);
    box-shadow: 0 0 0 1px var(--accent);
  }
  .tag {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    background: var(--chipbg, var(--navbg));
    border: 1px solid var(--panel-line);
    border-radius: 999px;
    padding: 0.2rem 0.3rem 0.2rem 0.6rem;
    font-size: 0.85rem;
    font-family: var(--font-code);
  }
  .tag__remove {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 1.15rem;
    height: 1.15rem;
    border: none;
    border-radius: 999px;
    background: transparent;
    color: var(--muted);
    cursor: pointer;
    font-size: 0.7rem;
    line-height: 1;
  }
  .tag__remove:hover {
    background: var(--chip-warn-bg);
    color: var(--chip-warn-fg);
  }
  .chipinput__input {
    flex: 1;
    min-width: 8ch;
    border: none;
    background: transparent;
    color: var(--fg);
    font: inherit;
    padding: 0.2rem;
  }
  .chipinput__input:focus {
    outline: none;
  }
</style>
