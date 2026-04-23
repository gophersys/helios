<script lang="ts">
  import '../app.css';
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { goto, afterNavigate } from '$app/navigation';
  import { PUBLIC_APP_ENVIRONMENT } from '$env/static/public';
  import { createAuthContext } from '$lib/stores/auth.svelte';
  import { createThemeContext } from '$lib/stores/theme.svelte';
  import { reportJsError, trackNavigation } from '$lib/stores/error-reporter.svelte';
  import Layout from '$lib/components/layout.svelte';
  import EnvironmentBanner from '$lib/components/ui/environment-banner.svelte';
  import ErrorReportModal from '$lib/components/ui/error-report-modal.svelte';
  import ActionContextMenu from '$lib/components/ui/action-context-menu.svelte';
  import ToastContainer from '$lib/components/ui/toast-container.svelte';
  import { highlightAction, readActionFromUrl } from '$lib/actions/deep-link';

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
  let boundaryError = $state<{ message: string; stack?: string } | null>(null);
  const isDev = PUBLIC_APP_ENVIRONMENT === 'development' || PUBLIC_APP_ENVIRONMENT === 'local' || !PUBLIC_APP_ENVIRONMENT;

  afterNavigate(({ to }) => {
    const title = document.title || $page.url.pathname;
    routeAnnouncement = 'Navigated to ' + title;
    if (to?.url) trackNavigation(to.url.pathname);

    // Deep-link handler: if the URL has ?a=<actionId> and a matching
    // element exists on the loaded page, scroll to it and pulse it.
    // Wait two animation frames so the page's onMount/effects have
    // stamped their data-action attributes into the DOM.
    const actionId = readActionFromUrl($page.url);
    if (actionId) {
      requestAnimationFrame(() => {
        requestAnimationFrame(() => highlightAction(actionId));
      });
    }
  });

  // Initialize auth on mount
  onMount(async () => {
    await auth.init();

    // Catch unhandled JS errors globally
    window.addEventListener('error', (e) => {
      boundaryError = { message: e.message, stack: e.filename + ':' + e.lineno };
      reportJsError({
        message: e.message,
        stack: e.error?.stack,
        url: e.filename,
      });
    });

    // Catch unhandled promise rejections globally
    const STALE_CHUNK_RE = /Failed to fetch dynamically imported module|error loading dynamically imported module|importing a module script failed/i;
    window.addEventListener('unhandledrejection', (e) => {
      const msg = e.reason?.message || String(e.reason);

      if (STALE_CHUNK_RE.test(msg)) {
        const key = 'concord:chunk-reload';
        const last = sessionStorage.getItem(key);
        if (!last || Date.now() - Number(last) > 10_000) {
          sessionStorage.setItem(key, String(Date.now()));
          location.reload();
          return;
        }
      }

      boundaryError = { message: msg, stack: e.reason?.stack };
      reportJsError({
        message: msg,
        stack: e.reason?.stack,
      });
    });
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
    <svelte:boundary onerror={(e: unknown, _reset: () => void) => { const msg = e instanceof Error ? e.message : String(e ?? 'Unknown error'); const stack = e instanceof Error ? e.stack : undefined; boundaryError = { message: msg, stack }; console.error('[boundary]', e); }}>
      {@render children()}
      {#snippet failed(error: unknown, reset: () => void)}
        <div class="p-8">
          <div class="rounded-lg border border-error/30 bg-error-muted p-4">
            <h2 class="text-lg font-semibold text-error mb-2">Something went wrong</h2>
            <p class="text-sm text-text-primary mb-3">{(error as Error)?.message || 'Unknown error'}</p>
            <button onclick={() => location.reload()} class="btn btn-sm btn-primary">
              Reload Page
            </button>
          </div>
        </div>
      {/snippet}
    </svelte:boundary>
  </Layout>
{:else}
  <!-- Redirecting to login - show loading while redirect happens -->
  <div class="flex min-h-screen items-center justify-center bg-surface-0">
    <div class="text-sm text-text-tertiary">Redirecting to login...</div>
  </div>
{/if}

<div aria-live="polite" aria-atomic="true" class="sr-only">{routeAnnouncement}</div>

<ErrorReportModal />
<ActionContextMenu />
<ToastContainer />

<!-- Dev error toast — persists until dismissed -->
{#if isDev && boundaryError}
  <div class="fixed bottom-4 right-4 left-4 sm:left-auto sm:max-w-lg z-50 rounded-lg border border-error/50 bg-surface-1 shadow-xl overflow-hidden">
    <div class="flex items-center justify-between bg-error px-3 py-1.5">
      <span class="text-xs font-bold text-white">Runtime Error</span>
      <button onclick={() => (boundaryError = null)} class="text-white/80 hover:text-white text-xs">dismiss</button>
    </div>
    <div class="px-3 py-2 max-h-48 overflow-auto">
      <p class="text-sm font-medium text-error mb-2">{boundaryError.message}</p>
      {#if boundaryError.stack}
        <pre class="text-2xs text-text-tertiary whitespace-pre-wrap font-mono">{boundaryError.stack}</pre>
      {/if}
    </div>
  </div>
{/if}
