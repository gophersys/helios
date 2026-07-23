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
  /* The login is a focus moment (P-D5): generous, centered, one brand moment. The screen styles
     against the SHADCN SKIN MAPPING (--background, --card, --border, --muted-foreground, --radius-*,
     --shadow-*, --ring) — all of which derive from the generated @eden/theme role tokens (see
     +layout.svelte), so the math pipeline feeds this skin. A faint top-lit radial washes the ground
     for depth without a literal gradient hue. */
  .login {
    display: grid;
    place-items: center;
    min-height: 100dvh;
    padding: var(--space-6, 32px);
    background:
      radial-gradient(120% 80% at 50% -10%, var(--accent-surface) 0%, transparent 55%),
      var(--background);
    color: var(--foreground);
  }
  /* The shadcn card: a barely-raised --card surface, a 1px subtle --border hairline, the refined
     elevation ramp, and the shadcn --radius-lg geometry (tighter than the old 16px mush). */
  .login__card {
    display: flex;
    flex-direction: column;
    align-items: stretch;
    gap: var(--space-4, 16px);
    width: min(384px, 100%);
    padding: var(--space-7, 40px) var(--space-6, 32px);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    background: var(--card);
    box-shadow: var(--shadow-lg);
  }
  .login__brand {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-2, 8px);
    margin-block-end: var(--space-1, 4px);
  }
  .login__mark {
    color: var(--primary);
    font-size: 1.5rem;
  }
  /* The brand name is the serif DISPLAY identity voice (P-D4) — the one identity moment on the screen. */
  .login__name {
    margin: 0;
    font-family: var(--font-display, var(--font-serif, serif));
    font-weight: 600;
    font-size: 1.95rem;
    letter-spacing: -0.02em;
    color: var(--foreground);
  }
  .login__tagline {
    margin: 0 0 var(--space-3, 12px);
    text-align: center;
    color: var(--muted-foreground);
    font-size: 0.9rem;
  }
  .login__fields {
    display: flex;
    flex-direction: column;
    gap: var(--space-4, 16px);
  }
  /* Label the fields with the shadcn form voice via the primitives Field's label (global reach:
     the Field renders its label outside this component's scope hash). */
  .login__fields :global(label) {
    font-size: 0.82rem;
    font-weight: 500;
    color: var(--foreground);
    letter-spacing: -0.005em;
  }
  /* Shadcn input geometry — a 1px --input edge, --radius-sm corners, muted placeholder, and a
     2px --ring focus halo. The primitives Input renders `.eden-input` globally, so reach it here. */
  .login__fields :global(.eden-input),
  .login__fields :global(input) {
    border-radius: var(--radius-sm);
    border: 1px solid var(--input);
    background: var(--background);
    transition:
      border-color var(--duration-short-2, 120ms) var(--ease-standard, ease),
      box-shadow var(--duration-short-2, 120ms) var(--ease-standard, ease);
  }
  .login__fields :global(.eden-input:focus-visible),
  .login__fields :global(input:focus-visible),
  .login__fields :global(input:focus) {
    outline: none;
    border-color: var(--ring);
    box-shadow: 0 0 0 3px color-mix(in oklab, var(--ring) 30%, transparent);
  }
  .login__error {
    margin: 0;
    color: var(--destructive);
    font-size: 0.85rem;
  }
  /* A block wrapper so the primitives Button (inline-flex) spans the card width, matching the fields.
     The submit gets the SHADCN button geometry: a solid --primary fill (never washed out), --radius
     corners, a font-weight bump, and the --shadow-sm lift — overriding the primitive's pill radius. */
  .login__submit {
    display: grid;
    margin-top: var(--space-1, 4px);
  }
  .login__submit :global(.eden-button) {
    inline-size: 100%;
    border-radius: var(--radius-md);
    background: var(--primary);
    border-color: var(--primary);
    color: var(--primary-foreground);
    font-weight: 600;
    box-shadow: var(--shadow-sm);
    transition:
      filter var(--duration-short-2, 120ms) var(--ease-standard, ease),
      box-shadow var(--duration-short-2, 120ms) var(--ease-standard, ease);
  }
  .login__submit :global(.eden-button:hover:not(:disabled)) {
    filter: brightness(1.08);
    box-shadow: var(--shadow-md);
  }
  .login__dev-wrap {
    display: grid;
    margin-top: var(--space-2, 8px);
    padding-top: var(--space-4, 16px);
    border-top: 1px solid var(--border);
  }
  /* The dev shortcut reads as a shadcn "secondary/ghost" selectable row — a --muted surface, a
     1px --border, --radius corners; hover raises the tint + ring. */
  .login__dev {
    display: flex;
    align-items: center;
    gap: var(--space-3, 12px);
    padding: var(--space-2, 8px) var(--space-3, 12px);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    background: var(--surface-muted);
    color: inherit;
    cursor: pointer;
    text-align: start;
    transition:
      border-color var(--duration-short-2, 120ms) var(--ease-standard, ease),
      background var(--duration-short-2, 120ms) var(--ease-standard, ease);
  }
  .login__dev:hover {
    border-color: var(--border-strong);
    background: var(--accent-surface);
  }
  .login__dev:focus-visible {
    outline: 2px solid var(--ring);
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
    background: color-mix(in oklab, var(--primary) 22%, var(--card));
    color: var(--foreground);
    font-weight: 600;
    flex-shrink: 0;
  }
  .login__dev-identity {
    display: flex;
    flex-direction: column;
    line-height: 1.25;
    flex: 1;
    min-width: 0;
  }
  .login__dev-name {
    font-weight: 600;
    font-size: 0.88rem;
  }
  .login__dev-email {
    font-size: 0.76rem;
    color: var(--muted-foreground);
  }
  .login__dev-tag {
    font-size: 0.62rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--muted-foreground);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    padding: 1px 6px;
  }
</style>
