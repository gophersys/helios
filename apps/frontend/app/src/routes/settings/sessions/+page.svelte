<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { CheckCircle2, Monitor, ShieldCheck, XCircle } from 'lucide-svelte';
  import { api } from '$lib/api';
  import type { ApiResponse } from '$lib/types';
  import EmptyState from '$lib/components/ui/empty-state.svelte';
  import ErrorAlert from '$lib/components/ui/error-alert.svelte';
  import LoadingState from '$lib/components/ui/loading-state.svelte';
  import PageHeader from '$lib/components/ui/page-header.svelte';

  // ── Types ───────────────────────────────────────────────────────────

  interface PendingSession {
    userCode: string;
    status: string;
    userAgent: string | null;
    createdAt: string;
    expiresAt: string;
  }

  // ── State ───────────────────────────────────────────────────────────

  // Approve mode: ?code=ABCD-EFGH (CLI sent the user here from the URL it printed)
  let codeFromUrl = $derived(($page.url.searchParams.get('code') || '').toUpperCase());

  let pending = $state<PendingSession | null>(null);
  let lookupLoading = $state(false);
  let lookupError = $state<string | null>(null);
  let approving = $state(false);
  let approved = $state(false);

  // Manual code-entry input (used when the user lands here without ?code=).
  let manualCode = $state('');

  // ── Approve mode ────────────────────────────────────────────────────

  async function lookupCode(code: string): Promise<void> {
    if (!code) return;
    lookupLoading = true;
    lookupError = null;
    pending = null;
    try {
      const res = await api.get<ApiResponse<PendingSession>>(
        `/v2/auth/session/verify?user_code=${encodeURIComponent(code)}`,
      );
      const data = res.data;
      if (data.status === 'PENDING') {
        pending = data;
      } else {
        lookupError = `That code is no longer valid (status: ${data.status.toLowerCase()}). Run \`corectl auth login\` again.`;
      }
    } catch (e) {
      lookupError = e instanceof Error ? e.message : 'Could not look up that code.';
    } finally {
      lookupLoading = false;
    }
  }

  async function approve(): Promise<void> {
    if (!pending) return;
    approving = true;
    lookupError = null;
    try {
      await api.post(`/v2/auth/session/approve`, { user_code: pending.userCode });
      approved = true;
    } catch (e) {
      lookupError = e instanceof Error ? e.message : 'Approval failed.';
    } finally {
      approving = false;
    }
  }

  function deny(): void {
    // Denying is just walking away — the session expires in <10 min.
    // We surface a clear "you can close this tab" message rather than
    // calling a /deny endpoint. The CLI poll will see ``expired``.
    pending = null;
    lookupError = 'Approval cancelled. The CLI will time out shortly.';
  }

  function submitManualCode(e: Event): void {
    e.preventDefault();
    const code = manualCode.trim().toUpperCase();
    if (code) {
      goto(`/settings/sessions?code=${encodeURIComponent(code)}`);
    }
  }

  // ── Lifecycle ───────────────────────────────────────────────────────

  $effect(() => {
    // Re-lookup whenever ``?code=`` changes (paste, manual submit, etc.).
    if (codeFromUrl) {
      lookupCode(codeFromUrl);
    } else {
      pending = null;
      approved = false;
      lookupError = null;
    }
  });

  // ── Helpers ────────────────────────────────────────────────────────

  function formatExpiry(iso: string): string {
    try {
      const d = new Date(iso);
      const mins = Math.max(0, Math.round((d.getTime() - Date.now()) / 60000));
      return mins > 0 ? `expires in ${mins} min` : 'expired';
    } catch {
      return iso;
    }
  }
</script>

<svelte:head>
  <title>Sessions — Settings — Concord</title>
</svelte:head>

<div class="animate-fade-in">
  <PageHeader
    title="Sessions"
    description="Approve or revoke CLI sessions tied to your account."
  />

  <div class="mt-6 space-y-6">
    {#if codeFromUrl && !approved}
      <!-- ── Approve mode ──────────────────────────────────────────── -->
      <section class="rounded-lg border border-border bg-surface-1 p-6">
        <div class="mb-4 flex items-center gap-2 text-sm font-semibold text-text-primary">
          <ShieldCheck size={16} class="text-accent" />
          <span>Authorize a new session</span>
        </div>

        {#if lookupLoading}
          <LoadingState message="Looking up code..." />
        {:else if lookupError}
          <ErrorAlert message={lookupError} />
          <div class="mt-4">
            <a href="/settings/sessions" class="text-sm text-text-secondary underline">
              Back to your sessions
            </a>
          </div>
        {:else if pending}
          <div class="space-y-4">
            <div class="rounded-lg border border-border bg-surface-0 p-4">
              <div class="flex items-center gap-2 text-2xs font-medium uppercase tracking-wider text-text-tertiary">
                <Monitor size={14} />
                <span>Code</span>
              </div>
              <div class="mt-1 font-mono text-lg font-semibold text-text-primary">{pending.userCode}</div>
              <div class="mt-2 text-xs text-text-secondary">
                {pending.userAgent || 'Unknown client'}
              </div>
              <div class="mt-1 text-2xs text-text-tertiary">{formatExpiry(pending.expiresAt)}</div>
            </div>

            <p class="text-sm text-text-secondary">
              Approving lets this CLI act as your account until the session is revoked
              or the refresh token expires (30 days).
            </p>

            <div class="flex gap-2">
              <button
                type="button"
                class="btn btn-md btn-primary"
                disabled={approving}
                onclick={approve}
              >
                {approving ? 'Approving...' : 'Approve'}
              </button>
              <button
                type="button"
                class="btn btn-md btn-ghost"
                disabled={approving}
                onclick={deny}
              >
                Deny
              </button>
            </div>
          </div>
        {/if}
      </section>
    {:else if approved}
      <!-- ── Approved confirmation ────────────────────────────────── -->
      <section class="rounded-lg border border-border bg-surface-1 p-6">
        <div class="flex items-center gap-2 text-success">
          <CheckCircle2 size={20} />
          <h2 class="text-sm font-semibold">Session approved</h2>
        </div>
        <p class="mt-2 text-sm text-text-secondary">
          You can close this tab — your CLI is authenticated.
        </p>
        <div class="mt-4">
          <a href="/settings/sessions" class="text-sm text-accent underline">
            View your sessions
          </a>
        </div>
      </section>
    {:else}
      <!-- ── List mode (no code in URL) ───────────────────────────── -->
      <section class="rounded-lg border border-border bg-surface-1 p-6">
        <h2 class="text-sm font-semibold text-text-primary">Approve a CLI session</h2>
        <p class="mt-1 text-sm text-text-secondary">
          When you run <code class="font-mono text-2xs">corectl auth login</code> the CLI prints
          a short code. Paste it here to approve the session.
        </p>

        <form class="mt-4 flex gap-2" onsubmit={submitManualCode}>
          <input
            type="text"
            bind:value={manualCode}
            placeholder="ABCD-EFGH"
            class="input input-md font-mono uppercase"
            maxlength="9"
            autocomplete="off"
            spellcheck="false"
          />
          <button type="submit" class="btn btn-md btn-primary" disabled={!manualCode.trim()}>
            Continue
          </button>
        </form>
      </section>

      <!-- Active sessions list — placeholder until the list endpoint lands.
           Listing requires an authed read on the user's own AuthSession +
           RefreshToken rows; the backend handler isn't built yet (tracked
           follow-up). For now, we surface the empty state explicitly so
           reviewers see the slot rather than wonder where it went. -->
      <section>
        <h2 class="mb-3 text-sm font-semibold text-text-primary">Your active sessions</h2>
        <EmptyState message="Active session listing ships in the next iteration." />
      </section>
    {/if}
  </div>
</div>
