<script lang="ts">
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  type IconComponent = any;

  type VariantType = 'danger' | 'warning' | 'primary';

  interface Props {
    label: string;
    icon: IconComponent;
    variant: VariantType;
    confirmMessage: string;
    onConfirm: () => Promise<void>;
    onError?: (err: Error) => void;
    disabled?: boolean;
  }

  let { label, icon, variant, confirmMessage, onConfirm, onError, disabled = false }: Props = $props();

  let confirming = $state(false);
  let loading = $state(false);
  let error = $state<string | null>(null);

  const buttonClass = $derived.by(() => {
    switch (variant) {
      case 'danger':
        return 'bg-error/10 text-error hover:bg-error/20';
      case 'warning':
        return 'bg-warning/10 text-warning hover:bg-warning/20';
      default:
        return 'bg-accent/10 text-accent hover:bg-accent/20';
    }
  });

  async function handleConfirm() {
    loading = true;
    error = null;
    try {
      await onConfirm();
      confirming = false;
    } catch (e) {
      const err = e instanceof Error ? e : new Error('Unknown error');
      error = err.message;
      onError?.(err);
    } finally {
      loading = false;
    }
  }

  function handleCancel() {
    confirming = false;
    error = null;
  }
</script>

{#if confirming}
  <div class="flex items-center gap-2">
    <span class="text-xs text-text-secondary">{confirmMessage}</span>
    <button
      onclick={handleConfirm}
      disabled={loading}
      class="px-2 py-1 text-xs font-medium rounded bg-error text-white hover:bg-error/90 disabled:opacity-50"
    >
      {loading ? 'Working...' : 'Confirm'}
    </button>
    <button
      onclick={handleCancel}
      disabled={loading}
      class="px-2 py-1 text-xs font-medium rounded bg-surface-2 text-text-secondary hover:bg-surface-2/80"
    >
      Cancel
    </button>
  </div>
{:else}
  <button
    onclick={() => confirming = true}
    {disabled}
    class="flex items-center gap-1.5 px-2 py-1 text-xs font-medium rounded {buttonClass} disabled:opacity-50"
  >
{#if icon}{@const Icon = icon}<Icon class="w-4 h-4" />{/if}
    {label}
  </button>
{/if}

{#if error}
  <span class="text-xs text-error ml-2">{error}</span>
{/if}
