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

/** PlatformUser is the wire projection of a persisted user (platformgateway's UserView). The login
 *  surface and the dashboard render the default user from this. No field is a secret. */
export interface PlatformUser {
  id: string;
  email: string;
  name: string;
  isDefault: boolean;
  createdAt: string;
  updatedAt: string;
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

/** PlatformClient talks to platformgateway over REST. Construct with the resolved base URL (default:
 *  the same-origin proxy). It is stateless — a thin typed wrapper over fetch. */
export class PlatformClient {
  constructor(private readonly base: string = resolvePlatformUrl()) {}

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
