<script lang="ts">
  // The LOGIN screen — Eden's front door. A basic, pre-identity login: it loads the seeded DEFAULT
  // user from platformgateway's public bootstrap (GET /platform/bootstrap/default-user) and the
  // button continues into the Projects dashboard AS that user. There is no password yet (real auth is
  // a later backend piece); this establishes the identity the dashboard renders. Token-driven from
  // @eden/theme; the brand mark + button match the dashboard.
  import { goto } from '$app/navigation';
  import { Button } from '@eden/primitives';
  import { edenTheme } from '$lib/theme/edenTheme';
  import { currentUser } from '$lib/platform/currentUser.svelte';

  const theme = edenTheme;

  // Load the default user on mount so the button can name them ("Continue as Mateo Segura") — proof
  // the platform API round-trips. A failure (platform API down) leaves the generic "Continue" label;
  // the button still works (the dashboard loads the identity lazily too).
  $effect(() => {
    if (!currentUser.user && !currentUser.loading) void currentUser.load();
  });

  let continuing = $state(false);

  async function continueAsDefault(): Promise<void> {
    continuing = true;
    // Ensure the identity is loaded before landing on the dashboard (idempotent if already loaded).
    if (!currentUser.user) await currentUser.load();
    await goto('/projects');
  }

  const buttonLabel = $derived(
    currentUser.user ? `Continue as ${currentUser.user.name}` : 'Continue',
  );
</script>

<svelte:head><title>Eden — Sign in</title></svelte:head>

<div class="login" data-testid="login-screen">
  <div class="login__card">
    <div class="login__brand">
      <span class="login__mark" aria-hidden="true">◆</span>
      <span class="login__name">Eden</span>
    </div>
    <p class="login__tagline">The agentic engineering platform</p>

    <div class="login__who" data-testid="login-default-user">
      {#if currentUser.user}
        <span class="login__avatar" aria-hidden="true">{currentUser.user.name.charAt(0)}</span>
        <span class="login__identity">
          <span class="login__username">{currentUser.user.name}</span>
          <span class="login__email">{currentUser.user.email}</span>
        </span>
      {:else if currentUser.loading}
        <span class="login__hint">Connecting to the platform…</span>
      {:else}
        <span class="login__hint" data-testid="login-default-user-error"
          >Default user unavailable — continue to the dashboard.</span
        >
      {/if}
    </div>

    <div class="login__action" data-testid="login-continue">
      <Button variant="primary" {theme} onclick={continueAsDefault} disabled={continuing}>
        {continuing ? 'Signing in…' : buttonLabel}
      </Button>
    </div>
  </div>
</div>

<style>
  .login {
    display: grid;
    place-items: center;
    min-height: 100dvh;
    padding: var(--space-6, 32px);
    background: var(--eden-app-bg, var(--color-surface, #0f1115));
    color: var(--eden-app-fg, var(--color-on-surface, #e8e8ea));
  }
  .login__card {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-5, 24px);
    width: min(420px, 100%);
    padding: var(--space-7, 48px) var(--space-6, 32px);
    border: 1px solid color-mix(in oklab, var(--color-on-surface, #fff) 10%, transparent);
    border-radius: var(--radius-lg, 18px);
    background: color-mix(
      in oklab,
      var(--color-on-surface, #fff) 3%,
      var(--color-surface, #14161b)
    );
    box-shadow: 0 24px 60px -28px rgba(0, 0, 0, 0.65);
  }
  .login__brand {
    display: flex;
    align-items: center;
    gap: var(--space-2, 8px);
  }
  .login__mark {
    color: var(--color-primary, #7aa2f7);
    font-size: 1.5rem;
    line-height: 1;
  }
  .login__name {
    font-family: var(--font-display, var(--font-sans, system-ui));
    font-weight: 600;
    font-size: 1.6rem;
    letter-spacing: 0.01em;
  }
  .login__tagline {
    margin: 0;
    color: color-mix(in oklab, var(--color-on-surface, #fff) 62%, transparent);
    font-size: 0.95rem;
    text-align: center;
  }
  .login__who {
    display: flex;
    align-items: center;
    gap: var(--space-3, 12px);
    min-height: 44px;
    width: 100%;
    justify-content: center;
  }
  .login__avatar {
    display: grid;
    place-items: center;
    width: 40px;
    height: 40px;
    border-radius: 999px;
    background: color-mix(
      in oklab,
      var(--color-primary, #7aa2f7) 24%,
      var(--color-surface, #14161b)
    );
    color: var(--color-on-surface, #fff);
    font-weight: 600;
  }
  .login__identity {
    display: flex;
    flex-direction: column;
    line-height: 1.25;
  }
  .login__username {
    font-weight: 600;
  }
  .login__email {
    font-size: 0.82rem;
    color: color-mix(in oklab, var(--color-on-surface, #fff) 55%, transparent);
  }
  .login__hint {
    color: color-mix(in oklab, var(--color-on-surface, #fff) 55%, transparent);
    font-size: 0.9rem;
    text-align: center;
  }
  .login__action {
    width: 100%;
    display: grid;
  }
</style>
