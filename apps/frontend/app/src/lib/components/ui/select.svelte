<script lang="ts">
  import { ChevronDown, Check } from 'lucide-svelte';
  import type { SelectOption } from './types';

  type Option = SelectOption;

  let {
    value = $bindable(''),
    options = [],
    placeholder = '',
    label = '',
    compact = false,
    disabled = false,
    required = false,
    class: className = '',
    onchange
  }: {
    value?: string | number | null;
    options?: Option[];
    placeholder?: string;
    label?: string;
    compact?: boolean;
    disabled?: boolean;
    required?: boolean;
    class?: string;
    onchange?: (e: Event) => void;
  } = $props();

  const selectId = crypto.randomUUID?.() ?? Math.random().toString(36).slice(2);

  let open = $state(false);
  let triggerEl = $state<HTMLButtonElement | null>(null);

  const displayLabel = $derived.by(() => {
    const v = String(value);
    if (!v && placeholder) return placeholder;
    const match = options.find(o => o.value === v);
    return match ? match.label : v || placeholder || '';
  });

  const isPlaceholder = $derived(!value && !!placeholder);

  function toggle() {
    if (disabled) return;
    open = !open;
  }

  function select(optValue: string) {
    value = optValue;
    open = false;
    // Fire synthetic change event for onchange handlers
    if (onchange) {
      const evt = new Event('change', { bubbles: true });
      onchange(evt);
    }
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') {
      open = false;
      triggerEl?.focus();
    } else if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      toggle();
    }
  }

  function handleOptionKeydown(e: KeyboardEvent, optValue: string) {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      select(optValue);
    }
  }

  function handleClickOutside(e: MouseEvent) {
    if (triggerEl && !triggerEl.closest('.select-wrapper')?.contains(e.target as Node)) {
      open = false;
    }
  }
</script>

<svelte:window onclick={handleClickOutside} />

<div class="select-wrapper relative {className}">
  {#if label}
    <label for={selectId} class="mb-1 block text-2xs font-medium text-text-tertiary">{label}</label>
  {/if}
  <div class="relative grid">
    <!-- Invisible sizer: renders every option label so the grid cell (and trigger) is always as wide as the longest one -->
    <span
      class="pointer-events-none col-start-1 row-start-1 flex items-center border border-transparent"
      class:px-3={!compact}
      class:py-2={!compact}
      class:px-2={compact}
      class:py-1={compact}
      aria-hidden="true"
      style="visibility:hidden;height:0;overflow-y:clip"
    >
      <span class="text-sm" class:text-xs={compact}>
        {#each options as opt}
          <span class="block whitespace-nowrap">{opt.label}</span>
        {/each}
        {#if placeholder}
          <span class="block whitespace-nowrap">{placeholder}</span>
        {/if}
      </span>
      <ChevronDown size={compact ? 14 : 16} class="ml-1 shrink-0" strokeWidth={1.75} />
    </span>

    <!-- Trigger button -->
    <button
      id={selectId}
      bind:this={triggerEl}
      type="button"
      {disabled}
      onclick={toggle}
      onkeydown={handleKeydown}
      class="col-start-1 row-start-1 flex w-full min-w-0 cursor-pointer items-center justify-between border bg-surface-0 text-left text-sm transition-colors hover:border-text-tertiary focus:border-accent focus:outline-none disabled:cursor-not-allowed disabled:opacity-50 {open ? 'rounded-t-lg border-accent ring-1 ring-accent/30' : 'rounded-lg border-border'}"
      class:px-3={!compact}
      class:py-2={!compact}
      class:px-2={compact}
      class:py-1={compact}
      class:text-xs={compact}
    >
      <span
        class="truncate"
        class:text-text-primary={!isPlaceholder}
        class:text-text-tertiary={isPlaceholder}
      >
        {displayLabel}
      </span>
      <ChevronDown
        size={compact ? 14 : 16}
        class="ml-1 shrink-0 text-text-tertiary transition-transform {open ? 'rotate-180' : ''}"
        strokeWidth={1.75}
      />
    </button>

    {#if open}
      <div
        class="absolute top-full z-dropdown -mt-px max-h-48 min-w-full w-max overflow-auto rounded-b-lg border border-t-0 border-border bg-surface-1 py-1 shadow-lg"
        role="listbox"
      >
        {#if placeholder}
          <button
            type="button"
            role="option"
            aria-selected={!value}
            onclick={() => select('')}
            onkeydown={(e) => handleOptionKeydown(e, '')}
            class="flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm text-text-tertiary transition-colors hover:bg-surface-2"
            class:text-xs={compact}
          >
            <span class="w-4 shrink-0">
              {#if !value}<Check size={14} class="text-accent" />{/if}
            </span>
            <span class="whitespace-nowrap">{placeholder}</span>
          </button>
        {/if}
        {#each options as option}
          <button
            type="button"
            role="option"
            aria-selected={String(value) === option.value}
            onclick={() => select(option.value)}
            onkeydown={(e) => handleOptionKeydown(e, option.value)}
            class="flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm text-text-primary transition-colors hover:bg-surface-2"
            class:text-xs={compact}
            class:bg-accent-muted={String(value) === option.value}
            class:text-accent={String(value) === option.value}
          >
            <span class="w-4 shrink-0">
              {#if String(value) === option.value}<Check size={14} class="text-accent" />{/if}
            </span>
            <span class="whitespace-nowrap">{option.label}</span>
          </button>
        {/each}
      </div>
    {/if}
  </div>

  <!-- Hidden native select for form validation -->
  {#if required}
    <select
      {value}
      {required}
      tabindex={-1}
      aria-hidden="true"
      class="absolute h-0 w-0 opacity-0"
      onchange={() => {}}
    >
      {#if placeholder}
        <option value="">{placeholder}</option>
      {/if}
      {#each options as option}
        <option value={option.value}>{option.label}</option>
      {/each}
    </select>
  {/if}
</div>
