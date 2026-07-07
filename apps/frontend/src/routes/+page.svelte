<script lang="ts">
  // The root load() redirects to /login (the front door — every entry authenticates first; see
  // +page.server.ts). This component never renders; it exists only because a route needs a page,
  // and the body is a courtesy fallback if a client ever lands here with JS disabled before the
  // redirect resolves.
</script>

<svelte:head>
  <title>Eden</title>
  <meta http-equiv="refresh" content="0; url=/login" />
</svelte:head>

<noscript><a href="/login">Go to login</a></noscript>
