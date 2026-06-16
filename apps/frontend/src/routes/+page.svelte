<script lang="ts">
  // The root load() redirects to /projects (the home), so this component never renders. It exists
  // only because a route needs a page; the body is a courtesy fallback if a client ever lands here
  // with JS disabled before the redirect resolves.
</script>

<svelte:head>
  <title>Eden — Projects</title>
  <meta http-equiv="refresh" content="0; url=/projects" />
</svelte:head>

<noscript><a href="/projects">Go to Projects</a></noscript>
