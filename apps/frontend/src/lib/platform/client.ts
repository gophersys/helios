// The platformgateway client — Eden's platform HTTP API (users + login), reached SAME-ORIGIN through
// the vite `/platform` proxy (vite.config.ts; override with EDEN_PLATFORM_TARGET, or a `?platform=`
// query for the E2E). It is a faithful, read-only mirror of platformgateway's wire shapes; the only
// surface this slice needs is the PUBLIC, pre-identity login bootstrap (GET /bootstrap/default-user),
// so a basic login lands on the seeded default user. No field here can carry a credential.

/** The default platform base: the same-origin vite proxy path that forwards to platformgateway. */
export const DEFAULT_PLATFORM_URL = '/platform';

/** resolvePlatformUrl picks the platform base URL: a `?platform=<url>` query override (used by the
 *  E2E to point at the free port it booted platformgateway on) else the same-origin proxy path. */
export function resolvePlatformUrl(): string {
  if (typeof window !== 'undefined') {
    const fromQuery = new URLSearchParams(window.location.search).get('platform');
    if (fromQuery) return fromQuery;
  }
  return DEFAULT_PLATFORM_URL;
}

/** PlatformOrganization is the tenant the signed-in user belongs to (platformgateway's
 *  MeOrganization). */
export interface PlatformOrganization {
  id: string;
  name: string;
}

/** PlatformUser is the wire projection of the signed-in user's PROFILE (platformgateway's /me +
 *  login bootstrap): the user record plus their IOTEA-style RBAC membership — the organization they
 *  belong to, their role ("member" | "admin"; admin bypasses checks), and their permission grants
 *  ("namespace:action", "*" = all). The login surface + the shell render this. No field is a secret.
 *  organization/role/permissions are optional so a pre-RBAC payload still types. */
export interface PlatformUser {
  id: string;
  email: string;
  name: string;
  isDefault: boolean;
  createdAt: string;
  updatedAt: string;
  organization?: PlatformOrganization;
  role?: string;
  permissions?: string[];
}

/** The uniform edenhttp response envelope ({ data, errors, kind }). The bootstrap route is enveloped,
 *  so the client unwraps `.data`. */
interface Envelope<T> {
  data: T;
  errors?: string[];
  kind?: string;
}

/** A typed platform error carrying the gateway's stable Kind token + operator-safe message. */
export class PlatformError extends Error {
  constructor(
    readonly kind: string,
    message: string,
  ) {
    super(message);
    this.name = 'PlatformError';
  }
}

/** The cookie the minted Eden session JWT is stored in. It is client-readable (the platform client
 *  reads it to attach the Bearer header to /v1 calls — the same shape IOTEA's readable access token
 *  uses); set on login, cleared on logout; SameSite=strict, 7-day. */
const TOKEN_COOKIE = 'eden_token';

function readToken(): string | null {
  if (typeof document === 'undefined') return null;
  const match = document.cookie.match(new RegExp(`(?:^|; )${TOKEN_COOKIE}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}
function writeToken(token: string): void {
  if (typeof document === 'undefined') return;
  document.cookie = `${TOKEN_COOKIE}=${encodeURIComponent(token)}; path=/; max-age=${7 * 24 * 60 * 60}; samesite=strict`;
}
function clearToken(): void {
  if (typeof document === 'undefined') return;
  document.cookie = `${TOKEN_COOKIE}=; path=/; max-age=0; samesite=strict`;
}

/** LoginResult is the POST /auth/login payload: the minted session JWT + the caller's profile. */
export interface LoginResult {
  token: string;
  profile: PlatformUser;
}

/** PlatformClient talks to platformgateway over REST. Construct with the resolved base URL (default:
 *  the same-origin proxy). The session token (when present) lives in the eden_token cookie; login sets
 *  it and the authenticated calls attach it as the Bearer. */
export class PlatformClient {
  constructor(private readonly base: string = resolvePlatformUrl()) {}

  /** login exchanges email + password for an Eden session JWT + the caller's profile (POST /auth/login,
   *  public/pre-identity). It stores the token (the cookie the client attaches as Bearer on /v1 calls)
   *  and returns the profile. A bad credential is a 401 PlatformError that never reveals which factor
   *  was wrong. The same mint path a Google/GitHub login lands on once OAuth is wired. */
  async login(email: string, password: string): Promise<LoginResult> {
    const response = await fetch(`${this.base}/auth/login`, {
      method: 'POST',
      headers: { 'content-type': 'application/json', accept: 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    if (!response.ok) {
      const body = (await response.json().catch(() => ({}))) as Partial<Envelope<unknown>>;
      throw new PlatformError(
        body.kind ?? `http-${response.status}`,
        body.errors?.[0] ?? `login failed (${response.status})`,
      );
    }
    const envelope = (await response.json()) as Envelope<LoginResult>;
    writeToken(envelope.data.token);
    return envelope.data;
  }

  /** me fetches the AUTHENTICATED caller's profile (GET /v1/me, Bearer). Returns null when there is no
   *  stored token (not signed in) or the token is stale (401 → cleared). The DB-driven authorize resolves
   *  the caller's grants server-side from their membership. */
  async me(): Promise<PlatformUser | null> {
    const token = readToken();
    if (!token) return null;
    const response = await fetch(`${this.base}/v1/me`, {
      headers: { accept: 'application/json', authorization: `Bearer ${token}` },
    });
    if (response.status === 401) {
      clearToken();
      return null;
    }
    if (!response.ok) {
      const body = (await response.json().catch(() => ({}))) as Partial<Envelope<unknown>>;
      throw new PlatformError(
        body.kind ?? `http-${response.status}`,
        body.errors?.[0] ?? `profile request failed (${response.status})`,
      );
    }
    const envelope = (await response.json()) as Envelope<PlatformUser>;
    return envelope.data;
  }

  /** signedIn reports whether a session token is stored. */
  signedIn(): boolean {
    return readToken() !== null;
  }

  /** logout clears the stored session token. */
  logout(): void {
    clearToken();
  }

  /** defaultUser fetches the seeded default user from the PUBLIC login bootstrap (no token — login is
   *  pre-identity). It unwraps the data envelope; a non-2xx is a typed PlatformError. */
  async defaultUser(): Promise<PlatformUser> {
    const response = await fetch(`${this.base}/bootstrap/default-user`, {
      headers: { accept: 'application/json' },
    });
    if (!response.ok) {
      const body = (await response.json().catch(() => ({}))) as Partial<Envelope<unknown>>;
      throw new PlatformError(
        body.kind ?? `http-${response.status}`,
        body.errors?.[0] ?? `default user request failed (${response.status})`,
      );
    }
    const envelope = (await response.json()) as Envelope<PlatformUser>;
    return envelope.data;
  }
}
