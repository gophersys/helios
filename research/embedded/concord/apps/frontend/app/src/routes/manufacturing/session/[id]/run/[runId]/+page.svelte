<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { beforeNavigate, goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { getAuth } from '$lib/stores/auth.svelte';
  import { createRunExecutionContext } from '$lib/components/execution/run-execution-context.svelte';
  import RunExecutionPage from '$lib/components/execution/run-execution-page.svelte';
  import type { TestRun } from '$lib/types/models';

  const auth = getAuth();

  // Capture initial route params at mount — this page is re-created by
  // SvelteKit when the ids change, so capturing once is correct.
  const initialSessionId = $page.params.id ?? '';
  const initialRunId = $page.params.runId ?? '';

  const ctx = createRunExecutionContext({
    runId: initialRunId,
    backPath: `/manufacturing/session/${initialSessionId}`,
    backLabel: 'Back to session',
    permission: 'manufacturing:view',
    getHardwareInfo: (run: TestRun) => ({
      productName: run.product?.name || '',
      boardRevision: (run as any).boardRevision?.version || '',
      firmwareVersion: (run as any).assetSet?.version || '',
      socLabels: (run as any).boardRevision?.socs || [],
    }),
  });

  function cleanup() {
    ctx.destroy();
  }

  onMount(() => {
    if (!auth.hasPermission('manufacturing:view')) {
      goto('/');
      return;
    }
    ctx.subscribe();
  });

  onDestroy(cleanup);
  beforeNavigate(cleanup);
</script>

<RunExecutionPage {ctx} />
