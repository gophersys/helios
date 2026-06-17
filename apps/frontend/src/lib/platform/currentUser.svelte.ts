// CurrentUser is the app-level identity the login establishes and the dashboard reads — a small,
// REUSABLE Svelte 5 rune store (libs → demos: any surface that needs "who is signed in" consumes
// this). The login screen loads it (from the platformgateway login bootstrap) and redirects; the
// dashboard renders it (and loads it lazily if a deep-link skipped the login). It holds no
// credential — only the public default-user projection.

import { PlatformClient, type PlatformUser } from './client';

/** CurrentUser holds the signed-in user + the in-flight/error state of loading it. A single shared
 *  instance (below) is the app's identity; the login sets it, the dashboard reads it. */
export class CurrentUser {
  /** The signed-in user, or null before login / when the platform is unreachable. */
  user = $state<PlatformUser | null>(null);
  /** True while a load is in flight (the login button shows progress). */
  loading = $state<boolean>(false);
  /** The last load error (operator-safe), or null. */
  error = $state<string | null>(null);

  private readonly client: PlatformClient;

  constructor(client: PlatformClient = new PlatformClient()) {
    this.client = client;
  }

  /** displayName is the name to show (the user's name, or the neutral "You" before/without login —
   *  preserving the dashboard's prior self-reference when the platform identity is unavailable). */
  get displayName(): string {
    return this.user?.name ?? 'You';
  }

  /** load fetches the default user (the basic login's target) and records it. It never throws — a
   *  failure (e.g. the platform API is not running in a given environment) leaves `user` null and
   *  sets `error`, so the dashboard degrades gracefully rather than crashing. Returns the user or null. */
  async load(): Promise<PlatformUser | null> {
    this.loading = true;
    this.error = null;
    try {
      this.user = await this.client.defaultUser();
      return this.user;
    } catch (cause) {
      this.error = cause instanceof Error ? cause.message : String(cause);
      return null;
    } finally {
      this.loading = false;
    }
  }
}

/** currentUser is the shared app identity the login and the dashboard both use (one home). */
export const currentUser = new CurrentUser();
