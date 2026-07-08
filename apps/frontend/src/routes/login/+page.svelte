<script lang="ts">
  // The LOGIN screen — Eden's front door (doc 17 §7 "rebuilt honest"). REAL authentication: email +
  // password POSTs to /auth/login, which mints an Eden session JWT (stored in a cookie) + returns the
  // profile; the shell then reads the authenticated identity. A dev "Continue as <default user>"
  // shortcut signs in with the seeded default credentials for the demo.
  //
  // W3: honest chrome (P-D6). The fake disabled Google/GitHub OAuth buttons + the "coming soon" span
  // are GONE — nothing disabled-that-looks-enabled, no non-functional control. OAuth appears only when
  // it works. The screen is a real brand moment (◆ + serif display, the platform line) over the
  // @eden/primitives Field/Input/Button, with a SOLID accent submit (no washed-out look).
  import { goto } from '$app/navigation';
  import { Field, Input, Button } from '@eden/primitives';
  import { currentUser } from '$lib/platform/currentUser.svelte';
  import { PlatformClient, PlatformError, type PlatformUser } from '$lib/platform/client';
  import { edenLightTheme, edenDarkTheme } from '$lib/theme/edenTheme';
  import { themePreference } from '$lib/theme/themePreference.svelte';

  const client = new PlatformClient();

  // The @eden/primitives Field/Input/Button derive their appearance from the theme OBJECT handed in
  // (not the runtime data-theme CSS switch), so on the login — a bare route outside the shell — we
  // resolve the ACTIVE mode reactively and hand the matching generated theme. W5: the OS/preference
  // resolution lives in ONE home — themePreference.resolvedMode (W4 added it, folding light/dark/system
  // and the live OS-dark signal); the login no longer re-implements its own matchMedia $effect. That
  // keeps the honest chrome tracking dark mode (doc 17 §3/§7) off the single source of truth.
  const theme = $derived(themePreference.resolvedMode === 'dark' ? edenDarkTheme : edenLightTheme);

  // The seeded default user (the public bootstrap) names the dev shortcut. A LOCAL hint only (not the
  // authenticated session) — login() establishes the real session. A failure leaves the shortcut hidden.
  let hint = $state<PlatformUser | null>(null);
  $effect(() => {
    void client
      .defaultUser()
      .then((user) => (hint = user))
      .catch(() => {});
  });

  // The dev default password — a DEV-only convenience so the demo signs in with one click; it matches
  // the backend's EDEN_PLATFORM_DEFAULT_USER_PASSWORD default. The real flow uses the form.
  const DEV_PASSWORD = 'eden';

  let email = $state('');
  let password = $state('');
  let submitting = $state(false);
  let error = $state<string | null>(null);

  const canSubmit = $derived(email.trim().length > 0 && password.length > 0 && !submitting);

  async function signIn(loginEmail: string, loginPassword: string): Promise<void> {
    submitting = true;
    error = null;
    try {
      await currentUser.login(loginEmail, loginPassword);
      await goto('/projects');
    } catch (cause) {
      error =
        cause instanceof PlatformError
          ? cause.message
          : 'Sign in failed — check your email and password.';
    } finally {
      submitting = false;
    }
  }

  function onSubmit(event: SubmitEvent): void {
    event.preventDefault();
    if (email.trim() && password) void signIn(email.trim(), password);
  }

  function continueAsDefault(): void {
    if (hint) void signIn(hint.email, DEV_PASSWORD);
  }
</script>

<svelte:head><title>Eden — Sign in</title></svelte:head>

<div class="login" data-testid="login-screen">
  <form class="login__card" onsubmit={onSubmit}>
    <div class="login__brand">
      <span class="login__mark" aria-hidden="true">◆</span>
      <h1 class="login__name">Eden</h1>
    </div>
    <p class="login__tagline">The agentic engineering platform</p>

    <div class="login__fields">
      <Field label="Email" {theme}>
        {#snippet control({ id, describedby, invalid })}
          <Input
            {id}
            {theme}
            type="email"
            bind:value={email}
            placeholder="you@example.com"
            aria-describedby={describedby}
            {invalid}
          />
        {/snippet}
      </Field>
      <Field label="Password" {theme}>
        {#snippet control({ id, describedby, invalid })}
          <Input
            {id}
            {theme}
            type="password"
            bind:value={password}
            placeholder="••••••••"
            aria-describedby={describedby}
            {invalid}
          />
        {/snippet}
      </Field>
    </div>

    {#if error}<p class="login__error" data-testid="login-error" role="alert">{error}</p>{/if}

    <span class="login__submit">
      <Button variant="primary" {theme} type="submit" disabled={!canSubmit}>
        {submitting ? 'Signing in…' : 'Sign in'}
      </Button>
    </span>

    {#if hint}
      <div class="login__dev-wrap" data-testid="login-continue">
        <button
          type="button"
          class="login__dev"
          onclick={continueAsDefault}
          disabled={submitting}
          title="Sign in with the seeded default credentials (dev)"
        >
          <span class="login__dev-avatar" aria-hidden="true">{hint.name.charAt(0)}</span>
          <span class="login__dev-identity" data-testid="login-default-user">
            <span class="login__dev-name">Continue as {hint.name}</span>
            <span class="login__dev-email">{hint.email}</span>
          </span>
          <span class="login__dev-tag">dev</span>
        </button>
      </div>
    {/if}
  </form>
</div>

<style>
  /* The login is a focus moment (P-D5): generous, centered, one brand moment. Every painted value is
     a generated @eden/theme role token — no hand-set hex/px on a color role (P-D3). */
  .login {
    display: grid;
    place-items: center;
    min-height: 100dvh;
    padding: var(--space-6, 32px);
    background: var(--color-surface);
    color: var(--color-on-surface);
  }
  .login__card {
    display: flex;
    flex-direction: column;
    align-items: stretch;
    gap: var(--space-4, 16px);
    width: min(400px, 100%);
    padding: var(--space-7, 40px) var(--space-6, 32px);
    border: 1px solid var(--color-outline);
    border-radius: var(--eden-app-radius, 16px);
    background: color-mix(in oklab, var(--color-on-surface) 3%, var(--color-surface));
    box-shadow: 0 24px 60px -28px color-mix(in oklab, var(--color-on-surface) 45%, transparent);
  }
  .login__brand {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-2, 8px);
  }
  .login__mark {
    color: var(--color-primary);
    font-size: 1.6rem;
  }
  /* The brand name is the serif DISPLAY identity voice (P-D4) — the one identity moment on the screen. */
  .login__name {
    margin: 0;
    font-family: var(--font-display, var(--font-serif, serif));
    font-weight: 600;
    font-size: 2rem;
    letter-spacing: -0.02em;
    color: var(--color-on-surface);
  }
  .login__tagline {
    margin: 0 0 var(--space-2, 8px);
    text-align: center;
    color: var(--color-outline);
    font-size: 0.95rem;
  }
  .login__fields {
    display: flex;
    flex-direction: column;
    gap: var(--space-3, 12px);
  }
  .login__error {
    margin: 0;
    color: var(--color-error);
    font-size: 0.85rem;
  }
  /* A block wrapper so the primitives Button (inline-flex) spans the card width, matching the fields. */
  .login__submit {
    display: grid;
  }
  .login__submit :global(.eden-button) {
    inline-size: 100%;
  }
  .login__dev-wrap {
    display: grid;
    margin-top: var(--space-1, 4px);
  }
  .login__dev {
    display: flex;
    align-items: center;
    gap: var(--space-3, 12px);
    padding: var(--space-2, 8px) var(--space-3, 12px);
    border: 1px dashed var(--color-outline);
    border-radius: var(--eden-app-radius, 8px);
    background: none;
    color: inherit;
    cursor: pointer;
    text-align: start;
  }
  .login__dev:hover {
    border-color: var(--color-primary);
  }
  .login__dev:focus-visible {
    outline: 2px solid var(--color-primary);
    outline-offset: 2px;
  }
  .login__dev:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .login__dev-avatar {
    display: grid;
    place-items: center;
    width: 34px;
    height: 34px;
    border-radius: 999px;
    background: color-mix(in oklab, var(--color-primary) 24%, var(--color-surface));
    color: var(--color-on-surface);
    font-weight: 600;
    flex-shrink: 0;
  }
  .login__dev-identity {
    display: flex;
    flex-direction: column;
    line-height: 1.2;
    flex: 1;
    min-width: 0;
  }
  .login__dev-name {
    font-weight: 600;
    font-size: 0.9rem;
  }
  .login__dev-email {
    font-size: 0.78rem;
    color: var(--color-outline);
  }
  .login__dev-tag {
    font-size: 0.64rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--color-outline);
    border: 1px solid var(--color-outline);
    border-radius: 999px;
    padding: 1px 6px;
  }
</style>
