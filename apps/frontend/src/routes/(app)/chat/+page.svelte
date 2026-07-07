<script lang="ts">
  // /chat — the Build view for UNSCOPED / global use, now a THIN page INSIDE the one (app) shell
  // (doc 17 §5, "the one-shell merge"). It is no longer a parallel app with its own chrome: the
  // SideNav, the global ⌘K palette, and the shell header all come from the (app) layout; this page
  // only resolves the deep-link query (?new / ?session / ?harness) and renders the reusable
  // <BuildWorkspace>. The URL stays /chat (the group does not change the path), honoring the hard
  // e2e contract (chat-slice / permission-flow / create-product / setup-wizard's onfinish all target
  // /chat). It keeps the PRE-SAGA inline-attach path — after "Build it" the conversation streams
  // right here (the e2e asserts the transcript on this page), so no onLaunched handoff is wired.
  import { page } from '$app/state';
  import BuildWorkspace from '$lib/buildview/BuildWorkspace.svelte';
  import type { ProductHarness } from '$lib/gateway/types';

  // Resolve the deep-link intent from the query once, at mount. Reading page.url.searchParams keeps
  // it reactive-safe; BuildWorkspace consumes the intent one-shot.
  const deepLink = {
    new: page.url.searchParams.get('new') === '1',
    sessionId: page.url.searchParams.get('session'),
    harness: (page.url.searchParams.get('harness') as ProductHarness | null) ?? null,
  };
</script>

<svelte:head><title>Eden — Build</title></svelte:head>

<BuildWorkspace {deepLink} />
