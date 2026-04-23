<script lang="ts">
  import { onMount } from 'svelte';
  import { fly, fade } from 'svelte/transition';
  import { Bell, Package, Bug, Megaphone, CheckCheck, Loader2 } from 'lucide-svelte';
  import {
    getNotifications,
    type UserNotification,
    type NotificationType,
  } from '$lib/stores/notifications.svelte';
  import { toasts, type ToastKind } from '$lib/stores/toast.svelte';
  import { getSystemSocket } from '$lib/services/websocket';

  let { collapsed = false, position = 'sidebar' }: { collapsed?: boolean; position?: 'sidebar' | 'topbar' } = $props();

  const notifs = getNotifications();

  let bellEl: HTMLDivElement | undefined = $state();

  // ── Lifecycle ────────────────────────────────────────────────

  onMount(() => {
    notifs.fetchUnreadCount();

    // Poll unread count every 60 seconds as fallback
    const interval = setInterval(() => notifs.fetchUnreadCount(), 60_000);

    // Wire up WebSocket listener for real-time notifications
    const socket = getSystemSocket();
    const handleNotification = (data: UserNotification) => {
      notifs.addRealtime(data);
      const kind = toastKindForType(data.type as NotificationType);
      toasts.show(data.title, kind, 5000);
    };

    if (socket) {
      socket.on('notification', handleNotification);
    }

    // Click-outside handler
    const handleClickOutside = (e: MouseEvent) => {
      if (notifs.panelOpen && bellEl && !bellEl.contains(e.target as Node)) {
        notifs.closePanel();
      }
    };
    document.addEventListener('mousedown', handleClickOutside);

    return () => {
      clearInterval(interval);
      if (socket) socket.off('notification', handleNotification);
      document.removeEventListener('mousedown', handleClickOutside);
    };
  });

  // ── Helpers ──────────────────────────────────────────────────

  function toastKindForType(type: NotificationType): ToastKind {
    switch (type) {
      case 'RELEASE_PUBLISHED':
      case 'BUG_RESOLVED':
        return 'success';
      default:
        return 'info';
    }
  }

  function getIcon(type: string) {
    switch (type) {
      case 'RELEASE_PUBLISHED':
        return Package;
      case 'BUG_ACKNOWLEDGED':
      case 'BUG_RESOLVED':
      case 'BUG_DISMISSED':
        return Bug;
      default:
        return Megaphone;
    }
  }

  function timeAgo(iso: string): string {
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60_000);
    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
  }

  function handleNotificationClick(n: UserNotification): void {
    if (!n.readAt) notifs.markRead(n.id);
  }

  const badgeLabel = $derived(notifs.unreadCount > 9 ? '9+' : String(notifs.unreadCount));
</script>

<div class="relative" bind:this={bellEl}>
  <!-- Bell button -->
  <button
    onclick={() => notifs.togglePanel()}
    title={collapsed ? 'Notifications' : undefined}
    aria-label="Notifications"
    class="group relative flex items-center justify-center rounded-lg p-2 transition-colors {position === 'topbar' ? 'h-9 w-9 bg-surface-1 border border-border text-text-secondary shadow-sm hover:bg-surface-2 hover:text-text-primary' : 'text-text-secondary hover:bg-sidebar-hover hover:text-text-primary'}"
  >
    <Bell size={20} strokeWidth={1.75} />

    {#if notifs.unreadCount > 0}
      <span
        class="absolute -top-0.5 -right-0.5 flex min-w-4 items-center justify-center rounded-full bg-error px-1 text-[10px] font-bold leading-none text-white"
        style="height: 16px;"
      >
        {badgeLabel}
      </span>
    {/if}
  </button>

  <!-- Dropdown panel -->
  {#if notifs.panelOpen}
    <div
      transition:fly={{ y: -4, duration: 150 }}
      class="absolute z-50 w-80 rounded-lg border border-border bg-surface-1 shadow-lg overflow-hidden {position === 'topbar' ? 'right-0 top-full mt-2' : 'left-0 bottom-full mb-2'}"
    >
      <!-- Header -->
      <div class="flex items-center justify-between border-b border-border px-4 py-3">
        <span class="text-sm font-semibold text-text-primary">Notifications</span>
        {#if notifs.unreadCount > 0}
          <button
            onclick={() => notifs.markAllRead()}
            class="flex items-center gap-1 text-2xs font-medium text-accent hover:text-accent-hover transition-colors"
          >
            <CheckCheck size={12} />
            Mark all read
          </button>
        {/if}
      </div>

      <!-- Notification list -->
      <div class="max-h-96 overflow-y-auto">
        {#if notifs.loading && notifs.notifications.length === 0}
          <div class="flex items-center justify-center py-8">
            <Loader2 size={18} class="animate-spin text-text-tertiary" />
          </div>
        {:else if notifs.notifications.length === 0}
          <div class="py-8 text-center">
            <Bell size={24} class="mx-auto mb-2 text-text-tertiary opacity-40" />
            <p class="text-sm text-text-tertiary">No notifications</p>
          </div>
        {:else}
          {#each notifs.notifications as n (n.id)}
            {@const Icon = getIcon(n.type)}
            <button
              onclick={() => handleNotificationClick(n)}
              class="relative flex w-full items-start gap-3 border-b border-border/50 px-4 py-3 text-left transition-colors hover:bg-surface-2 last:border-none"
              class:bg-surface-1={!n.readAt}
            >
              <!-- Unread indicator -->
              {#if !n.readAt}
                <span class="absolute left-1.5 top-1/2 h-2 w-2 -translate-y-1/2 rounded-full bg-accent"></span>
              {/if}

              <!-- Icon -->
              <div class="mt-0.5 shrink-0 text-text-tertiary">
                <Icon size={16} strokeWidth={1.75} />
              </div>

              <!-- Content -->
              <div class="min-w-0 flex-1">
                <p
                  class="truncate text-sm"
                  class:font-medium={!n.readAt}
                  class:text-text-primary={!n.readAt}
                  class:text-text-secondary={!!n.readAt}
                >
                  {n.title}
                </p>
                <p class="mt-0.5 line-clamp-2 text-2xs text-text-tertiary">{n.message}</p>
                <p class="mt-1 text-2xs text-text-tertiary opacity-70">{timeAgo(n.createdAt)}</p>
              </div>
            </button>
          {/each}
        {/if}
      </div>
    </div>
  {/if}
</div>
