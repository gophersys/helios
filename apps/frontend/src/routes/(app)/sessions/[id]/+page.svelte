<script lang="ts">
  // /sessions/[id] — the GLOBAL (unscoped) Build view for one session (doc 17 §5). When a session
  // is opened that does not map to a project, this is where its conversation streams — the in-shell
  // equivalent of the old /chat?session= handoff, but addressed by the session itself. It simply
  // hands the session id (and its recorded harness label) to the reusable <BuildWorkspace>, which
  // attaches + streams it inside the one shell chrome.
  import { page } from '$app/state';
  import type { ProductHarness } from '$lib/gateway/types';
  import BuildWorkspace from '$lib/buildview/BuildWorkspace.svelte';

  const sessionId = $derived(page.params.id ?? null);
  const harness = $derived((page.url.searchParams.get('harness') as ProductHarness | null) ?? null);
</script>

<svelte:head><title>Eden — Session</title></svelte:head>

<BuildWorkspace deepLink={{ sessionId, harness }} />
