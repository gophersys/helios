/**
 * Notification state management.
 *
 * Singleton class backed by Svelte 5 runes. Fetches notifications
 * from the API and receives real-time pushes via a dedicated
 * Socket.IO /notifications namespace.
 *
 * Mounted via `getNotifications()` — no context required.
 */

import { browser } from '$app/environment';
import { api } from '$lib/api';
import type { ApiResponse } from '$lib/types';

export interface UserNotification {
  id: string;
  type: string;
  title: string;
  message: string;
  userId: string | null;
  releaseId: string | null;
  errorReportId: string | null;
  readAt: string | null;
  createdAt: string;
}

export type NotificationType =
  // Platform
  | 'PLATFORM_RELEASE_PUBLISHED'
  | 'PLATFORM_DEPLOYMENT_COMPLETE'
  | 'PLATFORM_DEPLOYMENT_FAILED'
  // Validation
  | 'VALIDATION_RUN_COMPLETE'
  | 'VALIDATION_RUN_FAILED'
  // Manufacturing
  | 'MANUFACTURING_SESSION_COMPLETE'
  | 'MANUFACTURING_SESSION_FAILED'
  // Build
  | 'BUILD_COMPLETE'
  | 'BUILD_FAILED'
  // Bug
  | 'BUG_ACKNOWLEDGED'
  | 'BUG_RESOLVED'
  | 'BUG_DISMISSED'
  // System
  | 'SYSTEM_ANNOUNCEMENT'
  | 'SYSTEM_MAINTENANCE'
  // Legacy
  | 'RELEASE_PUBLISHED';

export interface NotificationTypeGroup {
  label: string;
  types: { key: string; label: string; description: string }[];
}

class NotificationState {
  notifications = $state<UserNotification[]>([]);
  unreadCount = $state(0);
  loading = $state(false);
  panelOpen = $state(false);

  async fetchUnreadCount(): Promise<void> {
    if (!browser) return;
    try {
      const res = await api.get<ApiResponse<{ count: number }>>('/v2/notifications/unread-count');
      this.unreadCount = res.data.count;
    } catch {
      // Silently fail — notifications are non-critical
    }
  }

  async fetchNotifications(): Promise<void> {
    if (this.loading) return;
    this.loading = true;
    try {
      const res = await api.get<
        ApiResponse<{ data: UserNotification[]; pagination: Record<string, unknown> }>
      >('/v2/notifications?limit=20');
      this.notifications = res.data.data;
    } catch {
      // Silently fail
    } finally {
      this.loading = false;
    }
  }

  async markRead(id: string): Promise<void> {
    try {
      await api.patch(`/v2/notifications/${id}/read`, {});
      const n = this.notifications.find((n) => n.id === id);
      if (n && !n.readAt) {
        n.readAt = new Date().toISOString();
        this.unreadCount = Math.max(0, this.unreadCount - 1);
      }
    } catch {
      // Silently fail
    }
  }

  async markAllRead(): Promise<void> {
    try {
      await api.post('/v2/notifications/read-all', {});
      this.notifications.forEach((n) => {
        if (!n.readAt) n.readAt = new Date().toISOString();
      });
      this.unreadCount = 0;
    } catch {
      // Silently fail
    }
  }

  togglePanel(): void {
    this.panelOpen = !this.panelOpen;
    if (this.panelOpen) this.fetchNotifications();
  }

  closePanel(): void {
    this.panelOpen = false;
  }

  addRealtime(notification: UserNotification): void {
    this.notifications = [notification, ...this.notifications].slice(0, 20);
    if (!notification.readAt) this.unreadCount++;
  }
}

let instance: NotificationState | null = null;

export function getNotifications(): NotificationState {
  if (!instance) instance = new NotificationState();
  return instance;
}
