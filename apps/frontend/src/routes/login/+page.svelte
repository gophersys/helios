<script lang="ts">
  // The LOGIN screen — Eden's front door. REAL authentication: email + password POSTs to
  // /auth/login, which mints an Eden session JWT (stored in a cookie) + returns the profile; the shell
  // then reads the authenticated identity. OAuth (Google/GitHub) lands on the SAME mint path once the
  // provider is wired — the buttons are present + structured here so that drop-in is trivial. A dev
  // "Continue as <default user>" shortcut signs in with the seeded default credentials for the demo.
  import { goto } from '$app/navigation';
  import { currentUser } from '$lib/platform/currentUser.svelte';
  import { PlatformClient, PlatformError, type PlatformUser } from '$lib/platform/client';

  const client = new PlatformClient();

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
      <span class="login__name">Eden</span>
    </div>
    <p class="login__tagline">The agentic engineering platform</p>

    <!-- OAuth — most people have Google/GitHub; the backend OAuth lands behind the SAME /auth mint
         path (find-or-create the user → mint the same JWT). Present + structured; enabled once wired. -->
    <div class="login__oauth">
      <button type="button" class="oauth" data-testid="login-google" disabled>
        <span class="oauth__glyph" aria-hidden="true">G</span> Continue with Google
      </button>
      <button type="button" class="oauth" data-testid="login-github" disabled>
        <span class="oauth__glyph" aria-hidden="true">⌥</span> Continue with GitHub
      </button>
      <span class="login__soon">Google &amp; GitHub sign-in — coming soon</span>
    </div>

    <div class="login__divider"><span>or</span></div>

    <label class="login__field">
      <span>Email</span>
      <input
        type="email"
        bind:value={email}
        data-testid="login-email"
        autocomplete="email"
        placeholder="you@example.com"
      />
    </label>
    <label class="login__field">
      <span>Password</span>
      <input
        type="password"
        bind:value={password}
        data-testid="login-password"
        autocomplete="current-password"
        placeholder="••••••••"
      />
    </label>

    {#if error}<p class="login__error" data-testid="login-error">{error}</p>{/if}

    <button
      type="submit"
      class="login__submit"
      data-testid="login-submit"
      disabled={submitting || !email.trim() || !password}
    >
      {submitting ? 'Signing in…' : 'Sign in'}
    </button>

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
    align-items: stretch;
    gap: var(--space-4, 16px);
    width: min(400px, 100%);
    padding: var(--space-7, 40px) var(--space-6, 32px);
    border: 1px solid color-mix(in oklab, var(--eden-app-fg, #fff) 10%, transparent);
    border-radius: var(--eden-app-radius, 16px);
    background: var(--eden-app-panel-bg, color-mix(in oklab, #fff 3%, #14161b));
    box-shadow: 0 24px 60px -28px rgba(0, 0, 0, 0.55);
  }
  .login__brand {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-2, 8px);
  }
  .login__mark {
    color: var(--eden-app-accent);
    font-size: 1.5rem;
  }
  .login__name {
    font-weight: 700;
    font-size: 1.6rem;
  }
  .login__tagline {
    margin: 0 0 var(--space-2, 8px);
    text-align: center;
    color: var(--eden-app-muted);
    font-size: 0.92rem;
  }
  .login__oauth {
    display: flex;
    flex-direction: column;
    gap: var(--space-2, 8px);
  }
  .oauth {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-2, 8px);
    padding: var(--space-3, 10px);
    border: 1px solid var(--eden-app-line);
    border-radius: var(--eden-app-radius, 8px);
    background: none;
    color: var(--eden-app-fg);
    font: inherit;
    font-weight: 600;
    cursor: pointer;
  }
  .oauth:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }
  .oauth__glyph {
    font-weight: 700;
    color: var(--eden-app-accent);
  }
  .login__soon {
    text-align: center;
    font-size: 0.74rem;
    color: var(--eden-app-muted);
  }
  .login__divider {
    display: flex;
    align-items: center;
    gap: var(--space-3, 12px);
    color: var(--eden-app-muted);
    font-size: 0.78rem;
  }
  .login__divider::before,
  .login__divider::after {
    content: '';
    flex: 1;
    height: 1px;
    background: var(--eden-app-line);
  }
  .login__field {
    display: flex;
    flex-direction: column;
    gap: 4px;
    font-size: 0.82rem;
    color: var(--eden-app-muted);
  }
  .login__field input {
    padding: var(--space-3, 10px);
    border: 1px solid var(--eden-app-line);
    border-radius: var(--eden-app-radius, 8px);
    background: var(--eden-app-bg);
    color: var(--eden-app-fg);
    font: inherit;
    font-size: 0.95rem;
  }
  .login__field input:focus {
    outline: 2px solid color-mix(in oklab, var(--eden-app-accent) 60%, transparent);
    outline-offset: 1px;
    border-color: var(--eden-app-accent);
  }
  .login__error {
    margin: 0;
    color: var(--color-error);
    font-size: 0.82rem;
  }
  .login__submit {
    padding: var(--space-3, 11px);
    border: 0;
    border-radius: var(--eden-app-radius, 8px);
    background: var(--eden-app-accent);
    color: var(--color-on-primary, #fff);
    font: inherit;
    font-weight: 700;
    cursor: pointer;
    transition: opacity 120ms ease;
  }
  .login__submit:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .login__dev-wrap {
    display: grid;
  }
  .login__dev {
    display: flex;
    align-items: center;
    gap: var(--space-3, 12px);
    padding: var(--space-2, 8px) var(--space-3, 12px);
    border: 1px dashed var(--eden-app-line);
    border-radius: var(--eden-app-radius, 8px);
    background: none;
    color: inherit;
    cursor: pointer;
    text-align: start;
  }
  .login__dev:hover {
    border-color: var(--eden-app-accent);
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
    background: color-mix(in oklab, var(--eden-app-accent) 24%, var(--eden-app-panel-bg));
    color: var(--eden-app-fg);
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
    font-size: 0.76rem;
    color: var(--eden-app-muted);
  }
  .login__dev-tag {
    font-size: 0.62rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--eden-app-muted);
    border: 1px solid var(--eden-app-line);
    border-radius: 999px;
    padding: 1px 6px;
  }
</style>
