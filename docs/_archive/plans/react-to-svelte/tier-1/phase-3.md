# Phase 3 — Auth Store and Login Page

## Objective

Implement the authentication system using Svelte 5 runes. Port the login page with Google OAuth.

---

## 1. Create `src/lib/stores/auth.svelte.ts`

Uses Svelte 5 runes for reactive state. The class pattern with `$state` provides a clean API.

```typescript
import { getContext, setContext } from 'svelte';
import { browser } from '$app/environment';
import { goto } from '$app/navigation';
import { api, setToken, clearToken, getToken } from '$lib/api';
import type { ApiResponse } from '$lib/types';

export interface User {
  id: string;
  email: string;
  name: string;
  permissionSetId: string | null;
  permissionSetName: string | null;
  permissions: string[];
}

interface LoginResponse {
  token: string;
  user: {
    id: string;
    email: string;
    name: string;
    permissionSetId: string | null;
    permissionSetName: string | null;
  };
}

class AuthState {
  user = $state<User | null>(null);
  isLoading = $state(true);

  get isAuthenticated(): boolean {
    return !!this.user;
  }

  hasPermission(...perms: string[]): boolean {
    if (!this.user?.permissions) return false;
    return perms.every((p) => this.user!.permissions.includes(p));
  }

  async init(): Promise<void> {
    if (!browser) {
      this.isLoading = false;
      return;
    }

    const token = getToken();
    if (!token) {
      this.isLoading = false;
      return;
    }

    try {
      const res = await api<ApiResponse<User>>('/v2/auth/me');
      this.user = res.data;
    } catch {
      clearToken();
    } finally {
      this.isLoading = false;
    }
  }

  async login(googleCredential: string): Promise<void> {
    const loginData = await api<ApiResponse<LoginResponse>>('/v2/auth/login', {
      method: 'POST',
      body: JSON.stringify({ credential: googleCredential })
    });

    setToken(loginData.data.token);

    // Fetch full user profile with permissions
    const meData = await api<ApiResponse<User>>('/v2/auth/me');
    this.user = meData.data;
  }

  logout(): void {
    clearToken();
    this.user = null;
    if (browser) {
      goto('/login');
    }
  }
}

const AUTH_KEY = Symbol('auth');

export function createAuthContext(): AuthState {
  const auth = new AuthState();
  setContext(AUTH_KEY, auth);
  return auth;
}

export function getAuth(): AuthState {
  return getContext<AuthState>(AUTH_KEY);
}
```

---

## 2. Create Login Page

**`src/routes/login/+page.svelte`:**

```svelte
<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { getAuth } from '$lib/stores/auth.svelte';

  const auth = getAuth();

  let error = $state<string | null>(null);
  let loading = $state(false);

  // Google OAuth configuration
  const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || '';

  onMount(() => {
    if (auth.isAuthenticated) {
      goto('/');
      return;
    }

    if (!GOOGLE_CLIENT_ID) {
      error = 'Google OAuth is not configured';
      return;
    }

    // Load Google Identity Services
    const script = document.createElement('script');
    script.src = 'https://accounts.google.com/gsi/client';
    script.async = true;
    script.defer = true;
    script.onload = initializeGoogle;
    document.head.appendChild(script);

    return () => {
      // Cleanup: remove the script on unmount
      script.remove();
    };
  });

  function initializeGoogle() {
    if (!window.google) return;

    window.google.accounts.id.initialize({
      client_id: GOOGLE_CLIENT_ID,
      callback: handleCredentialResponse,
      auto_select: false,
      cancel_on_tap_outside: true
    });

    window.google.accounts.id.renderButton(
      document.getElementById('google-signin-btn')!,
      {
        type: 'standard',
        theme: 'outline',
        size: 'large',
        text: 'signin_with',
        shape: 'rectangular',
        logo_alignment: 'left',
        width: 280
      }
    );
  }

  async function handleCredentialResponse(response: { credential: string }) {
    loading = true;
    error = null;

    try {
      await auth.login(response.credential);
      goto('/');
    } catch (err) {
      error = err instanceof Error ? err.message : 'Login failed';
    } finally {
      loading = false;
    }
  }
</script>

<svelte:head>
  <title>Login — Concord</title>
</svelte:head>

<div class="flex min-h-screen items-center justify-center bg-surface-0 px-4">
  <div class="w-full max-w-sm">
    <div class="mb-8 text-center">
      <img
        src="/assets/corekinect-logo.png"
        alt="CoreKinect"
        class="mx-auto mb-3 h-6 dark:hidden"
      />
      <img
        src="/assets/corekinect-logo-dark.png"
        alt="CoreKinect"
        class="mx-auto mb-3 hidden h-6 dark:block"
      />
      <h1 class="text-xl font-semibold text-text-primary">Concord</h1>
      <p class="mt-1 text-sm text-text-secondary">
        Sign in to continue
      </p>
    </div>

    <div class="rounded-xl border border-border bg-surface-1 p-6 shadow-card">
      {#if error}
        <div class="mb-4 rounded-lg bg-error-muted px-3 py-2 text-sm text-error">
          {error}
        </div>
      {/if}

      {#if loading}
        <div class="flex items-center justify-center py-4">
          <div class="h-5 w-5 animate-spin rounded-full border-2 border-accent border-t-transparent"></div>
          <span class="ml-2 text-sm text-text-secondary">Signing in...</span>
        </div>
      {:else}
        <div id="google-signin-btn" class="flex justify-center"></div>
      {/if}
    </div>

    <p class="mt-6 text-center text-2xs text-text-tertiary">
      Manufacturing Operations Platform
    </p>
  </div>
</div>

<style>
  /* Ensure Google button is centered and styled consistently */
  :global(#google-signin-btn > div) {
    margin: 0 auto;
  }
</style>
```

---

## 3. Add Google Types

Create `src/app.d.ts` to add Google Identity Services types:

```typescript
/// <reference types="@sveltejs/kit" />

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: {
            client_id: string;
            callback: (response: { credential: string }) => void;
            auto_select?: boolean;
            cancel_on_tap_outside?: boolean;
          }) => void;
          renderButton: (
            element: HTMLElement,
            options: {
              type?: 'standard' | 'icon';
              theme?: 'outline' | 'filled_blue' | 'filled_black';
              size?: 'large' | 'medium' | 'small';
              text?: 'signin_with' | 'signup_with' | 'continue_with' | 'signin';
              shape?: 'rectangular' | 'pill' | 'circle' | 'square';
              logo_alignment?: 'left' | 'center';
              width?: number;
            }
          ) => void;
          prompt: () => void;
        };
      };
    };
  }
}

export {};
```

---

## 4. Update Root Layout

**`src/routes/+layout.svelte`:**

```svelte
<script lang="ts">
  import '../app.css';
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { createAuthContext } from '$lib/stores/auth.svelte';

  let { children } = $props();

  // Create auth context at the root
  const auth = createAuthContext();

  // Initialize auth on mount
  onMount(async () => {
    await auth.init();
  });

  // Redirect logic based on auth state
  $effect(() => {
    if (auth.isLoading) return;

    const isLoginPage = $page.url.pathname === '/login';

    if (!auth.isAuthenticated && !isLoginPage) {
      goto('/login');
    } else if (auth.isAuthenticated && isLoginPage) {
      goto('/');
    }
  });
</script>

{#if auth.isLoading}
  <div class="flex min-h-screen items-center justify-center bg-surface-0">
    <div class="text-sm text-text-tertiary">Loading...</div>
  </div>
{:else}
  {@render children()}
{/if}
```

---

## 5. Update Home Page (Placeholder)

**`src/routes/+page.svelte`:**

```svelte
<script lang="ts">
  import { getAuth } from '$lib/stores/auth.svelte';

  const auth = getAuth();
</script>

<div class="flex min-h-screen items-center justify-center bg-surface-0">
  <div class="rounded-xl border border-border bg-surface-1 p-8 shadow-card">
    <h1 class="mb-2 text-xl font-semibold text-text-primary">
      Welcome, {auth.user?.name ?? 'User'}
    </h1>
    <p class="mb-4 text-sm text-text-secondary">
      Logged in as {auth.user?.email}
    </p>
    <button
      onclick={() => auth.logout()}
      class="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover"
    >
      Sign out
    </button>
  </div>
</div>
```

---

## 6. Environment Variables

Create `.env` file:

```
VITE_GOOGLE_CLIENT_ID=your-google-client-id-here
```

---

## Verification

1. `npm run dev` starts without errors
2. Navigate to `http://localhost:5173`
3. Should redirect to `/login`
4. Google Sign-In button renders
5. Click sign in → authenticate → redirects to home page
6. User name and email display correctly
7. Sign out button works, redirects back to login
8. Refresh page while authenticated → stays authenticated
9. Clear localStorage → redirects to login

---

## Files Created/Modified

| File | Action | Description |
|------|--------|-------------|
| `src/lib/stores/auth.svelte.ts` | Create | Auth state with runes |
| `src/routes/login/+page.svelte` | Create | Login page |
| `src/app.d.ts` | Create | Google types |
| `src/routes/+layout.svelte` | Modify | Add auth context and init |
| `src/routes/+page.svelte` | Modify | Show user info |
| `.env` | Create | Environment variables |

---

## Next Phase

Phase 4 will implement the theme store and main layout component.
