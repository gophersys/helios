<script lang="ts">
  import type { Tab } from './types';

  interface Props {
    /** Array of tab configurations */
    tabs: Tab[];
    /** Currently active tab ID */
    activeTab: string;
    /** Called when a tab is selected */
    onchange?: (tabId: string) => void;
    /** Size variant */
    size?: 'sm' | 'md' | 'lg';
    /** Visual variant */
    variant?: 'pills' | 'underline' | 'segment';
    /** Full width tabs */
    fullWidth?: boolean;
  }

  let {
    tabs,
    activeTab = $bindable(),
    onchange,
    size = 'md',
    variant = 'segment',
    fullWidth = false
  }: Props = $props();

  function selectTab(tabId: string) {
    if (tabs.find(t => t.id === tabId)?.disabled) return;
    activeTab = tabId;
    onchange?.(tabId);
  }

  const sizeClasses = {
    sm: 'text-xs px-3 py-1.5',
    md: 'text-sm px-4 py-2',
    lg: 'text-base px-5 py-2.5'
  };

  const variantClasses = {
    segment: {
      container: 'flex gap-1 rounded-lg bg-surface-2 p-0.5',
      tab: 'rounded-md font-medium transition-all',
      active: 'bg-surface-1 text-text-primary shadow-sm',
      inactive: 'text-text-tertiary hover:text-text-secondary'
    },
    pills: {
      container: 'flex gap-2',
      tab: 'rounded-full font-medium transition-all border',
      active: 'bg-accent text-white border-accent',
      inactive: 'bg-transparent text-text-secondary border-border hover:bg-surface-2'
    },
    underline: {
      container: 'flex gap-4 border-b border-border',
      tab: 'pb-2 font-medium transition-all border-b-2 -mb-px',
      active: 'text-accent border-accent',
      inactive: 'text-text-tertiary border-transparent hover:text-text-secondary hover:border-border'
    }
  };
</script>

<div
  class={variantClasses[variant].container}
  class:w-full={fullWidth}
  role="tablist"
>
  {#each tabs as tab (tab.id)}
    <button
      type="button"
      role="tab"
      aria-selected={activeTab === tab.id}
      aria-disabled={tab.disabled}
      disabled={tab.disabled}
      onclick={() => selectTab(tab.id)}
      class={[
        variantClasses[variant].tab,
        sizeClasses[size],
        activeTab === tab.id
          ? variantClasses[variant].active
          : variantClasses[variant].inactive,
        fullWidth ? 'flex-1' : '',
        tab.disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'
      ].filter(Boolean).join(' ')}
    >
      <span class="inline-flex items-center gap-2">
        {#if tab.icon}
          {@const Icon = tab.icon}
          <Icon size={size === 'sm' ? 14 : size === 'lg' ? 18 : 16} />
        {/if}
        {tab.label}
        {#if tab.badge !== undefined}
          <span class="ml-1 inline-flex items-center justify-center rounded-full bg-accent/20 px-1.5 py-0.5 text-2xs font-medium text-accent">
            {tab.badge}
          </span>
        {/if}
      </span>
    </button>
  {/each}
</div>
