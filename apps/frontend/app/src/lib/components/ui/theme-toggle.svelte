<script lang="ts">
  import { Sun, Moon } from 'lucide-svelte';
  import { getTheme } from '$lib/stores/theme.svelte';

  const theme = getTheme();
</script>

<button
  onclick={() => theme.toggle()}
  class="flex h-8 w-8 items-center justify-center rounded-lg text-text-secondary transition-colors hover:bg-surface-2 hover:text-text-primary"
  title={theme.theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
  aria-label={theme.theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
>
  {#if theme.theme === 'dark'}
    <Sun size={18} strokeWidth={1.75} />
  {:else}
    <Moon size={18} strokeWidth={1.75} />
  {/if}
</button>
