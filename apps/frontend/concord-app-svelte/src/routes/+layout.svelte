<script lang="ts">
  import '../app.css';
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { goto, afterNavigate } from '$app/navigation';
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

  let routeAnnouncement = $state('');

  afterNavigate(() => {
    const title = document.title || $page.url.pathname;
    routeAnnouncement = 'Navigated to ' + title;
  });

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

<a href="#main-content" class="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:rounded focus:bg-surface-1 focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-text-primary focus:shadow-lg focus:ring-2 focus:ring-accent">Skip to main content</a>

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
{:else}
  <!-- Redirecting to login - show loading while redirect happens -->
  <div class="flex min-h-screen items-center justify-center bg-surface-0">
    <div class="text-sm text-text-tertiary">Redirecting to login...</div>
  </div>
{/if}

<div aria-live="polite" aria-atomic="true" class="sr-only">{routeAnnouncement}</div>
