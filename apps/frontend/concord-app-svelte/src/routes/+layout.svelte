<script lang="ts">
  import '../app.css';
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { PUBLIC_APP_ENVIRONMENT } from '$env/static/public';
  import { createAuthContext } from '$lib/stores/auth.svelte';
  import { createThemeContext } from '$lib/stores/theme.svelte';
  import Layout from '$lib/components/layout.svelte';
  import EnvironmentBanner from '$lib/components/ui/environment-banner.svelte';

  let { children } = $props();

  // Create contexts at the root
  const auth = createAuthContext();
  const theme = createThemeContext();

  const envLabel = (() => {
    const env = PUBLIC_APP_ENVIRONMENT || 'development';
    if (env === 'production') return '';
    if (env === 'staging') return 'STAGING';
    if (env === 'local') return 'LOCAL';
    return 'DEV';
  })();

  // Initialize auth on mount
  onMount(async () => {
    await auth.init();
  });

  // Redirect logic
  $effect(() => {
    if (auth.isLoading) return;

    const isLoginPage = $page.url.pathname === '/login';

    if (!auth.isAuthenticated && !isLoginPage) {
      goto('/login');
    }
  });

  const isLoginPage = $derived($page.url.pathname === '/login');
</script>

<EnvironmentBanner />

{#if auth.isLoading}
  <div class="flex min-h-screen items-center justify-center bg-surface-0">
    <div class="text-sm text-text-tertiary">Loading...</div>
  </div>
{:else if isLoginPage}
  {@render children()}
{:else if auth.isAuthenticated}
  <Layout>
    {@render children()}
  </Layout>
{/if}
