# Tier 1 — Foundation & Auth

## Goal

Stand up the SvelteKit project with identical styling to the React app. Implement authentication, theming, layout, sidebar, and core UI components. By the end of Tier 1, a user can log in and see the authenticated shell with working navigation and theme toggle.

---

## Architecture

### Project Structure (after Tier 1)

```
apps/frontend/concord-app/
├── package.json
├── svelte.config.js
├── vite.config.ts
├── tailwind.config.js              # Copied from React, unchanged
├── postcss.config.js
├── tsconfig.json
├── src/
│   ├── app.html                    # HTML template
│   ├── app.css                     # Global styles (copy of styles.css)
│   ├── lib/
│   │   ├── api.ts                  # API client
│   │   ├── types.ts                # Shared types
│   │   ├── types/
│   │   │   └── models.ts           # Model interfaces
│   │   ├── stores/
│   │   │   ├── auth.svelte.ts      # Auth state (runes)
│   │   │   └── theme.svelte.ts     # Theme state (runes)
│   │   └── components/
│   │       ├── layout.svelte
│   │       ├── sidebar.svelte
│   │       └── ui/
│   │           ├── back-button.svelte
│   │           ├── confirm-delete-dialog.svelte
│   │           ├── empty-state.svelte
│   │           ├── error-alert.svelte
│   │           ├── loading-state.svelte
│   │           ├── page-header.svelte
│   │           ├── select.svelte
│   │           ├── status-badge.svelte
│   │           └── theme-toggle.svelte
│   ├── routes/
│   │   ├── +layout.svelte          # Root layout (auth check, theme, layout)
│   │   ├── +layout.ts              # Root layout load (auth state)
│   │   ├── +page.svelte            # Dashboard placeholder
│   │   └── login/
│   │       └── +page.svelte        # Login page
│   └── hooks.server.ts             # Server hooks (auth validation)
└── static/
    └── assets/
        ├── corekinect-logo.png
        ├── corekinect-logo-dark.png
        ├── ck-logo.png
        └── ck-logo-dark.png
```

---

## Components

| Component | React Source | Svelte Target | Notes |
|-----------|--------------|---------------|-------|
| API Client | `api.ts` | `lib/api.ts` | Nearly identical, same functions |
| Types | `types.ts` + `types/models.ts` | `lib/types.ts` + `lib/types/models.ts` | Copy directly |
| Auth Store | `auth-provider.tsx` | `lib/stores/auth.svelte.ts` | Context → runes-based store |
| Theme Store | `theme-provider.tsx` | `lib/stores/theme.svelte.ts` | Context → runes-based store |
| Layout | `components/layout.tsx` | `lib/components/layout.svelte` | Direct port |
| Sidebar | `components/sidebar.tsx` | `lib/components/sidebar.svelte` | NavLink → `<a>` with `$page` |
| Login Page | `pages/login.tsx` | `routes/login/+page.svelte` | Google OAuth flow |
| Back Button | `components/ui/back-button.tsx` | `lib/components/ui/back-button.svelte` | Simple port |
| Confirm Delete | `components/ui/confirm-delete-dialog.tsx` | `lib/components/ui/confirm-delete-dialog.svelte` | Portal → `<dialog>` |
| Empty State | `components/ui/empty-state.tsx` | `lib/components/ui/empty-state.svelte` | Simple port |
| Error Alert | `components/ui/error-alert.tsx` | `lib/components/ui/error-alert.svelte` | Simple port |
| Loading State | `components/ui/loading-state.tsx` | `lib/components/ui/loading-state.svelte` | Simple port |
| Page Header | `components/ui/page-header.tsx` | `lib/components/ui/page-header.svelte` | Simple port |
| Select | `components/ui/select.tsx` | `lib/components/ui/select.svelte` | Simple port |
| Status Badge | `components/ui/status-badge.tsx` | `lib/components/ui/status-badge.svelte` | Simple port |
| Theme Toggle | `components/ui/theme-toggle.tsx` | `lib/components/ui/theme-toggle.svelte` | Simple port |

---

## Key Implementation Details

### Auth Store (Runes)

```typescript
// lib/stores/auth.svelte.ts
import { getContext, setContext } from 'svelte';

export interface User {
  id: string;
  email: string;
  name: string;
  permissionSetId: string | null;
  permissionSetName: string | null;
  permissions: string[];
}

class AuthState {
  user = $state<User | null>(null);
  isLoading = $state(true);

  get isAuthenticated() {
    return !!this.user;
  }

  hasPermission(...perms: string[]) {
    if (!this.user?.permissions) return false;
    return perms.every(p => this.user!.permissions.includes(p));
  }

  async login(googleCredential: string) {
    // ... login logic
  }

  logout() {
    // ... logout logic
  }
}

const AUTH_KEY = Symbol('auth');

export function setAuthContext() {
  return setContext(AUTH_KEY, new AuthState());
}

export function getAuth() {
  return getContext<AuthState>(AUTH_KEY);
}
```

### Theme Store (Runes)

```typescript
// lib/stores/theme.svelte.ts
import { getContext, setContext } from 'svelte';

type Theme = 'light' | 'dark';

class ThemeState {
  theme = $state<Theme>('dark');

  constructor() {
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem('concord-theme') as Theme | null;
      this.theme = stored ?? (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    }
  }

  toggle() {
    this.theme = this.theme === 'dark' ? 'light' : 'dark';
    if (typeof window !== 'undefined') {
      localStorage.setItem('concord-theme', this.theme);
      document.documentElement.classList.remove('light', 'dark');
      document.documentElement.classList.add(this.theme);
    }
  }
}

const THEME_KEY = Symbol('theme');

export function setThemeContext() {
  return setContext(THEME_KEY, new ThemeState());
}

export function getTheme() {
  return getContext<ThemeState>(THEME_KEY);
}
```

### SvelteKit Routing

The `+layout.svelte` at the root handles:
1. Auth check (redirect to `/login` if not authenticated)
2. Theme context setup
3. Rendering the sidebar + main content

```svelte
<!-- routes/+layout.svelte -->
<script>
  import { setAuthContext } from '$lib/stores/auth.svelte';
  import { setThemeContext } from '$lib/stores/theme.svelte';
  import Layout from '$lib/components/layout.svelte';

  const auth = setAuthContext();
  const theme = setThemeContext();

  let { children } = $props();
</script>

{#if auth.isLoading}
  <div class="flex min-h-screen items-center justify-center bg-surface-0">
    <div class="text-sm text-text-tertiary">Loading...</div>
  </div>
{:else if !auth.isAuthenticated}
  {@render children()}
{:else}
  <Layout>
    {@render children()}
  </Layout>
{/if}
```

### Google OAuth

For Svelte, we implement OAuth manually instead of using `@react-oauth/google`:

1. **Login page** renders a "Sign in with Google" button
2. Button redirects to Google OAuth consent URL
3. Google redirects back to `/auth/callback` with `code` param
4. Server-side route exchanges code for tokens
5. We call our backend `/v2/auth/login` with the Google token
6. Store the returned JWT in a cookie (not localStorage for SSR)

Alternative: Use the Google Sign-In JavaScript library directly.

---

## Phase Checklist

- [ ] Phase 1 — Project scaffolding (SvelteKit, Tailwind, tokens)
- [ ] Phase 2 — API client and types
- [ ] Phase 3 — Auth store and login page
- [ ] Phase 4 — Theme store and layout
- [ ] Phase 5 — Sidebar and navigation
- [ ] Phase 6 — UI components (status-badge, error-alert, etc.)

---

## Verification

After Tier 1:
1. `npm run dev` starts without errors
2. Login page renders with Google button
3. After login, dashboard shell renders with sidebar
4. Navigation links work (even if pages are placeholder)
5. Theme toggle switches between light/dark
6. Sidebar collapses/expands
7. Visual comparison to React app shows identical styling
