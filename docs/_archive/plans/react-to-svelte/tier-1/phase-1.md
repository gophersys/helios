# Phase 1 — Project Scaffolding

## Objective

Create a new SvelteKit project with Tailwind CSS configured identically to the React app. Copy the design tokens and verify the styling system works.

---

## 1. Create SvelteKit Project

Create a new SvelteKit project in the same location as the React app. We'll work in a new directory first, then swap when complete.

```bash
cd apps/frontend
npx sv create concord-app-svelte
```

Select:
- Template: SvelteKit minimal
- Add TypeScript: Yes
- Add ESLint: Yes
- Add Prettier: Yes
- Add Tailwind CSS: Yes

---

## 2. Update `package.json`

```json
{
  "name": "concord-app",
  "version": "0.0.1",
  "private": true,
  "scripts": {
    "dev": "vite dev",
    "build": "vite build",
    "preview": "vite preview",
    "check": "svelte-kit sync && svelte-check --tsconfig ./tsconfig.json",
    "check:watch": "svelte-kit sync && svelte-check --tsconfig ./tsconfig.json --watch",
    "lint": "eslint .",
    "test": "vitest"
  },
  "devDependencies": {
    "@sveltejs/adapter-static": "^3.0.0",
    "@sveltejs/kit": "^2.0.0",
    "@sveltejs/vite-plugin-svelte": "^4.0.0",
    "@types/node": "^20.0.0",
    "autoprefixer": "^10.4.0",
    "eslint": "^9.0.0",
    "postcss": "^8.4.0",
    "prettier": "^3.0.0",
    "prettier-plugin-svelte": "^3.0.0",
    "svelte": "^5.0.0",
    "svelte-check": "^4.0.0",
    "tailwindcss": "^3.4.0",
    "typescript": "^5.0.0",
    "vite": "^6.0.0",
    "vitest": "^2.0.0"
  },
  "dependencies": {
    "@fontsource-variable/inter": "^5.2.8",
    "lucide-svelte": "^0.470.0",
    "socket.io-client": "^4.8.3"
  },
  "type": "module"
}
```

---

## 3. Configure Static Adapter

We're building an SPA, not SSR. Use the static adapter.

**`svelte.config.js`:**

```javascript
import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
  preprocess: vitePreprocess(),
  kit: {
    adapter: adapter({
      pages: 'dist',
      assets: 'dist',
      fallback: 'index.html', // SPA fallback
      precompress: false,
      strict: true
    }),
    alias: {
      '$lib': 'src/lib',
      '$components': 'src/lib/components'
    }
  }
};

export default config;
```

---

## 4. Copy Tailwind Config

Copy `tailwind.config.js` from the React app exactly:

```javascript
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{html,js,svelte,ts}'],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter Variable', 'Inter', 'system-ui', '-apple-system', 'sans-serif'],
      },
      colors: {
        surface: {
          0: 'var(--surface-0)',
          1: 'var(--surface-1)',
          2: 'var(--surface-2)',
          3: 'var(--surface-3)',
        },
        border: {
          DEFAULT: 'var(--border)',
          subtle: 'var(--border-subtle)',
        },
        text: {
          primary: 'var(--text-primary)',
          secondary: 'var(--text-secondary)',
          tertiary: 'var(--text-tertiary)',
        },
        accent: {
          DEFAULT: 'var(--accent)',
          hover: 'var(--accent-hover)',
          muted: 'var(--accent-muted)',
          subtle: 'var(--accent-subtle)',
        },
        sidebar: {
          bg: 'var(--sidebar-bg)',
          active: 'var(--sidebar-active-bg)',
          'active-border': 'var(--sidebar-active-border)',
          hover: 'var(--sidebar-hover-bg)',
        },
        success: {
          DEFAULT: 'var(--success)',
          muted: 'var(--success-muted)',
        },
        warning: {
          DEFAULT: 'var(--warning)',
          hover: 'var(--warning-hover)',
          muted: 'var(--warning-muted)',
        },
        error: {
          DEFAULT: 'var(--error)',
          hover: 'var(--error-hover)',
          muted: 'var(--error-muted)',
        },
        info: {
          DEFAULT: 'var(--info)',
          muted: 'var(--info-muted)',
        },
        overlay: 'var(--overlay)',
        'card-glow': 'var(--card-glow)',
      },
      spacing: {
        sidebar: '260px',
      },
      fontSize: {
        '2xs': ['0.6875rem', { lineHeight: '1rem' }],
      },
      boxShadow: {
        card: '0 1px 3px 0 rgba(0,0,0,0.06), 0 1px 2px -1px rgba(0,0,0,0.04)',
        'card-hover':
          '0 4px 16px 0 rgba(0,0,0,0.08), 0 2px 4px -1px rgba(0,0,0,0.05)',
        glow: '0 0 20px var(--card-glow)',
        'card-dark':
          '0 1px 4px 0 rgba(0,0,0,0.3), 0 0 0 1px rgba(255,255,255,0.03)',
        'card-dark-hover':
          '0 4px 16px 0 rgba(0,0,0,0.4), 0 0 0 1px rgba(255,255,255,0.05)',
      },
      transitionDuration: {
        DEFAULT: '150ms',
      },
      borderRadius: {
        DEFAULT: '8px',
      },
      keyframes: {
        'fade-in': {
          from: { opacity: '0', transform: 'translateY(4px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'overlay-in': {
          from: { opacity: '0' },
          to: { opacity: '1' },
        },
        'modal-in': {
          from: { opacity: '0', transform: 'scale(0.97)' },
          to: { opacity: '1', transform: 'scale(1)' },
        },
      },
      animation: {
        'fade-in': 'fade-in 0.3s ease-out',
        'overlay-in': 'overlay-in 150ms ease-out',
        'modal-in': 'modal-in 200ms ease-out',
      },
    },
  },
  plugins: [],
};
```

---

## 5. Copy Global Styles

Copy `styles.css` to `src/app.css` exactly (all CSS custom properties):

```css
@import '@fontsource-variable/inter';
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    /* Surfaces — subtle off-white bg, white cards */
    --surface-0: #f5f5f7;
    --surface-1: #ffffff;
    --surface-2: #f0f0f3;
    --surface-3: #e6e6eb;

    /* Borders */
    --border: #dcdce2;
    --border-subtle: #e8e8ed;

    /* Text — neutral */
    --text-primary: #1a1a1a;
    --text-secondary: #636370;
    --text-tertiary: #9494a0;

    /* Accent — coral-orange, from CoreKinect logo slash */
    --accent: #cf6a3e;
    --accent-hover: #be5e35;
    --accent-muted: rgba(207, 106, 62, 0.08);
    --accent-subtle: rgba(207, 106, 62, 0.14);

    /* Sidebar */
    --sidebar-bg: #f8f8fa;
    --sidebar-active-bg: rgba(207, 106, 62, 0.06);
    --sidebar-active-border: #cf6a3e;
    --sidebar-hover-bg: #ededf1;

    /* Status */
    --success: #3d8b4d;
    --success-muted: rgba(61, 139, 77, 0.08);
    --warning: #b8922f;
    --warning-hover: #a68329;
    --warning-muted: rgba(184, 146, 47, 0.08);
    --error: #b93a2a;
    --error-hover: #a33224;
    --error-muted: rgba(185, 58, 42, 0.08);
    --info: #4a729b;
    --info-muted: rgba(74, 114, 155, 0.08);

    /* Interactive */
    --focus-ring: rgba(207, 106, 62, 0.4);
    --overlay: rgba(20, 20, 20, 0.4);

    /* Card */
    --card-glow: rgba(207, 106, 62, 0.04);
  }

  .dark {
    /* Surfaces — softer grey darks with card contrast */
    --surface-0: #151518;
    --surface-1: #1e1e23;
    --surface-2: #27272e;
    --surface-3: #313139;

    /* Borders — visible separation */
    --border: #2f2f38;
    --border-subtle: #25252c;

    /* Text — lighter greys for readability */
    --text-primary: #ededf0;
    --text-secondary: #9898a3;
    --text-tertiary: #6a6a76;

    /* Accent — coral-orange, brighter for dark backgrounds */
    --accent: #e8845c;
    --accent-hover: #ee9570;
    --accent-muted: rgba(232, 132, 92, 0.1);
    --accent-subtle: rgba(232, 132, 92, 0.18);

    /* Sidebar */
    --sidebar-bg: #131316;
    --sidebar-active-bg: rgba(232, 132, 92, 0.08);
    --sidebar-active-border: #e8845c;
    --sidebar-hover-bg: #1c1c22;

    /* Status */
    --success: #5fa86a;
    --success-muted: rgba(95, 168, 106, 0.1);
    --warning: #d4a853;
    --warning-hover: #c09a48;
    --warning-muted: rgba(212, 168, 83, 0.1);
    --error: #d44c3c;
    --error-hover: #c04434;
    --error-muted: rgba(212, 76, 60, 0.1);
    --info: #6b8eb5;
    --info-muted: rgba(107, 142, 181, 0.1);

    /* Interactive */
    --focus-ring: rgba(232, 132, 92, 0.4);
    --overlay: rgba(5, 5, 5, 0.6);

    /* Card */
    --card-glow: rgba(232, 132, 92, 0.03);
  }

  * {
    border-color: var(--border);
  }

  body {
    @apply bg-surface-0 font-sans text-text-primary antialiased;
    font-feature-settings: 'cv02', 'cv03', 'cv04', 'cv11';
  }

  /* Scrollbar styling */
  ::-webkit-scrollbar {
    width: 6px;
    height: 6px;
  }

  ::-webkit-scrollbar-track {
    background: transparent;
  }

  ::-webkit-scrollbar-thumb {
    background: var(--border);
    border-radius: 3px;
  }

  ::-webkit-scrollbar-thumb:hover {
    background: var(--text-tertiary);
  }

  /* Selection */
  ::selection {
    background: var(--accent-subtle);
    color: var(--text-primary);
  }

  /* Focus visible */
  :focus-visible {
    outline: 2px solid var(--focus-ring);
    outline-offset: 2px;
  }
}
```

---

## 6. Create `app.html`

```html
<!doctype html>
<html lang="en" class="dark">
  <head>
    <meta charset="utf-8" />
    <link rel="icon" href="%sveltekit.assets%/favicon.ico" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Concord</title>
    %sveltekit.head%
  </head>
  <body data-sveltekit-preload-data="hover">
    <div style="display: contents">%sveltekit.body%</div>
  </body>
</html>
```

---

## 7. Copy Static Assets

Copy the logo assets from React:
```
static/
  assets/
    corekinect-logo.png
    corekinect-logo-dark.png
    ck-logo.png
    ck-logo-dark.png
    favicon.ico
```

---

## 8. Create Minimal Route

Create a minimal route to verify styling works.

**`src/routes/+layout.svelte`:**

```svelte
<script>
  import '../app.css';
  let { children } = $props();
</script>

{@render children()}
```

**`src/routes/+page.svelte`:**

```svelte
<div class="flex min-h-screen items-center justify-center bg-surface-0">
  <div class="rounded-xl border border-border bg-surface-1 p-8 shadow-card">
    <h1 class="mb-2 text-xl font-semibold text-text-primary">Concord</h1>
    <p class="text-sm text-text-secondary">
      SvelteKit migration in progress...
    </p>
    <button class="mt-4 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover">
      Test Button
    </button>
  </div>
</div>
```

---

## Verification

1. `npm install` completes without errors
2. `npm run dev` starts the dev server
3. Navigate to `http://localhost:5173`
4. Verify:
   - Dark theme is applied (dark background)
   - Card has correct styling (rounded corners, border, shadow)
   - Button has coral-orange accent color
   - Hover state works on button
   - Inter font is loaded
5. Toggle theme by changing `class="dark"` to `class="light"` in `app.html` — verify light theme colors apply

---

## Files Created

| File | Description |
|------|-------------|
| `package.json` | Project dependencies |
| `svelte.config.js` | SvelteKit config with static adapter |
| `vite.config.ts` | Vite config (auto-generated) |
| `tailwind.config.js` | Tailwind with design tokens |
| `postcss.config.js` | PostCSS config (auto-generated) |
| `tsconfig.json` | TypeScript config |
| `src/app.html` | HTML template |
| `src/app.css` | Global styles with CSS variables |
| `src/routes/+layout.svelte` | Root layout |
| `src/routes/+page.svelte` | Test page |
| `static/assets/*` | Logo images |

---

## Next Phase

Phase 2 will port the API client and TypeScript types.
