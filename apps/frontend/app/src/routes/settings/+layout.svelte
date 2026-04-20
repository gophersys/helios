<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { Monitor } from 'lucide-svelte';
  import { getAuth } from '$lib/stores/auth.svelte';

  let { children } = $props();

  const auth = getAuth();

  // Settings is a single-section grouping for now — Sessions is the only
  // entry. Adding more later (e.g. Notifications, Profile) means appending
  // to this array; the sidebar renders dynamically.
  const sections = [
    { href: '/settings/sessions', label: 'Sessions', icon: Monitor },
  ];

  let activePath = $derived($page.url.pathname);

  onMount(() => {
    // The auth store sets ``isLoading`` while fetching /v2/auth/me on
    // boot. Wait for it to settle before deciding to redirect — flashing
    // /login during a hard refresh is jarring.
    if (auth.isLoading) return;
    if (!auth.isAuthenticated) {
      const next = encodeURIComponent($page.url.pathname + $page.url.search);
      goto(`/login?next=${next}`);
    }
  });

  $effect(() => {
    // Re-check after auth finishes loading (covers the SSR → hydrate flow).
    if (!auth.isLoading && !auth.isAuthenticated) {
      const next = encodeURIComponent($page.url.pathname + $page.url.search);
      goto(`/login?next=${next}`);
    }
  });
</script>

<div class="flex gap-6 p-6">
  <aside class="w-56 shrink-0">
    <div class="mb-4">
      <h2 class="text-sm font-semibold text-text-primary">Settings</h2>
      <p class="mt-1 text-xs text-text-secondary">Account &amp; sessions</p>
    </div>
    <nav class="space-y-1">
      {#each sections as section (section.href)}
        {@const Icon = section.icon}
        {@const active = activePath === section.href || activePath.startsWith(section.href + '/')}
        <a
          href={section.href}
          class="flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors
            {active
              ? 'bg-surface-2 text-text-primary'
              : 'text-text-secondary hover:bg-surface-2 hover:text-text-primary'}"
        >
          <Icon size={16} />
          <span>{section.label}</span>
        </a>
      {/each}
    </nav>
  </aside>

  <main class="flex-1 min-w-0">
    {@render children()}
  </main>
</div>
