// CurrentUser is the app-level AUTHENTICATED SESSION — a small, REUSABLE Svelte 5 rune store (libs →
// demos: any surface that needs "who is signed in" consumes this). The login screen establishes it
// (POST /auth/login → a stored token + the profile); the shell/dashboard render it and re-establish it
// from the stored token on reload (restore). It holds the profile (user + org + role + permissions),
// never a credential — the token lives in the platform client's cookie, not here.

import { PlatformClient, type PlatformUser } from './client';

/** CurrentUser holds the signed-in user's profile + the in-flight/error state. A single shared instance
 *  (below) is the app's identity; login sets it, the shell reads it (and restores it from the token). */
export class CurrentUser {
  /** The signed-in user's profile, or null when signed out / the platform is unreachable. */
  user = $state<PlatformUser | null>(null);
  /** True while a login/restore is in flight (the login button shows progress). */
  loading = $state<boolean>(false);
  /** The last error (operator-safe), or null. */
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

  /** signedIn reports whether a session token is stored. */
  get signedIn(): boolean {
    return this.client.signedIn();
  }

  /** login authenticates email+password (POST /auth/login), stores the session token, and records the
   *  profile. Returns the profile on success; THROWS a PlatformError on a bad credential (the login
   *  screen catches it and shows the message — never revealing which factor was wrong). This is the
   *  same mint path a Google/GitHub login lands on once OAuth is wired. */
  async login(email: string, password: string): Promise<PlatformUser> {
    this.loading = true;
    this.error = null;
    try {
      const result = await this.client.login(email, password);
      this.user = result.profile;
      return result.profile;
    } finally {
      this.loading = false;
    }
  }

  /** restore re-establishes the session from the stored token (GET /v1/me) — for a page reload or a
   *  deep-link into the shell. It never throws: no/stale token leaves `user` null (signed out → the
   *  neutral fallback), and an unreachable platform is non-fatal. Returns the profile or null. */
  async restore(): Promise<PlatformUser | null> {
    this.loading = true;
    this.error = null;
    try {
      this.user = await this.client.me();
      return this.user;
    } catch (cause) {
      this.error = cause instanceof Error ? cause.message : String(cause);
      return null;
    } finally {
      this.loading = false;
    }
  }

  /** logout clears the stored session token + the signed-in user. */
  logout(): void {
    this.client.logout();
    this.user = null;
  }
}

/** currentUser is the shared app identity the login and the shell both use (one home). */
export const currentUser = new CurrentUser();
