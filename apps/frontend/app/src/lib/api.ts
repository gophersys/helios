import { browser } from '$app/environment';
import { trackAction } from '$lib/stores/error-reporter.svelte';

const TOKEN_KEY = 'concord-token';
const VIEW_AS_KEY = 'concord-view-as-role';

export function getToken(): string | null {
  if (!browser) return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  if (!browser) return;
  localStorage.setItem(TOKEN_KEY, token);
  setAuthCookie(token);
}

export function clearToken(): void {
  if (!browser) return;
  localStorage.removeItem(TOKEN_KEY);
  clearAuthCookie();
}

/**
 * Set a JWT cookie on the parent domain so the docs subdomain can read it.
 * This enables auth and role-based filtering on docs.{host}.
 */
function setAuthCookie(token: string): void {
  const domain = getParentDomain();
  const secure = window.location.protocol === 'https:' ? '; Secure' : '';
  document.cookie = `concord-auth=${token}; Domain=${domain}; Path=/; SameSite=Lax; Max-Age=86400${secure}`;
}

function clearAuthCookie(): void {
  const domain = getParentDomain();
  document.cookie = `concord-auth=; Domain=${domain}; Path=/; Max-Age=0`;
}

/**
 * Extract the parent domain for cookie sharing.
 * staging.concord.local → .concord.local
 * concord.local → .concord.local
 * localhost → localhost (no dot prefix)
 */
function getParentDomain(): string {
  const hostname = window.location.hostname;
  if (hostname === 'localhost' || hostname === '127.0.0.1') return hostname;
  const parts = hostname.split('.');
  if (parts.length <= 2) return '.' + hostname;
  return '.' + parts.slice(-2).join('.');
}

export async function apiFetch<T = unknown>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>)
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const viewAs = browser ? localStorage.getItem(VIEW_AS_KEY) : null;
  if (viewAs) {
    headers['X-View-As-Role'] = viewAs;
  }

  const method = (options.method as string) || 'GET';
  trackAction(`api ${method} ${path}`);

  const startTime = Date.now();
  const res = await fetch(path, { ...options, headers });
  const durationMs = Date.now() - startTime;

  if (res.status === 401) {
    clearToken();
    if (browser) {
      window.location.href = '/login';
    }
    throw new Error('Session expired');
  }

  let data: unknown;
  try {
    data = await res.json();
  } catch {
    if (!res.ok) {
      throw new Error(`Request failed (${res.status})`);
    }
    throw new Error('Invalid JSON response from server');
  }

  if (!res.ok) {
    const errorData = data as { errors?: { message?: string }[]; error?: string };
    const errorMessage =
      errorData.errors?.[0]?.message || errorData.error || `Request failed (${res.status})`;

    trackAction(`api ${method} ${path} → ${res.status} (${durationMs}ms)`);

    // Report 500+ always, 4xx on mutations (POST/PUT/PATCH/DELETE) as they indicate code bugs
    const isMutation = method !== 'GET';
    if (res.status >= 500 || (isMutation && res.status >= 400)) {
      const { reportApiError } = await import('$lib/stores/error-reporter.svelte');
      reportApiError({
        status: res.status,
        url: path,
        method,
        message: errorMessage,
        requestBody: typeof options.body === 'string' ? options.body?.slice(0, 500) : undefined,
        responseBody: JSON.stringify(data).slice(0, 500),
        requestDurationMs: durationMs,
      });
    }

    throw new Error(errorMessage);
  }

  return data as T;
}

export async function apiUploadRaw(
  path: string,
  formData: FormData
): Promise<Response> {
  const token = getToken();

  const headers: Record<string, string> = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  trackAction(`upload POST ${path}`);

  const startTime = Date.now();
  const res = await fetch(path, {
    method: 'POST',
    headers,
    body: formData
  });
  const durationMs = Date.now() - startTime;

  if (res.status === 401) {
    clearToken();
    if (browser) {
      window.location.href = '/login';
    }
    throw new Error('Session expired');
  }

  if (!res.ok) {
    const data = await res.json();
    const errorMessage =
      data.error || data.errors?.[0]?.message || `Upload failed (${res.status})`;

    trackAction(`upload POST ${path} → ${res.status} (${durationMs}ms)`);

    if (res.status >= 500) {
      const { reportApiError } = await import('$lib/stores/error-reporter.svelte');
      reportApiError({
        status: res.status,
        url: path,
        method: 'POST',
        message: errorMessage,
        responseBody: JSON.stringify(data).slice(0, 500),
        requestDurationMs: durationMs,
      });
    }

    throw new Error(errorMessage);
  }

  return res;
}

// Convenience wrapper object with HTTP method helpers
export const api = {
  async get<T = unknown>(path: string): Promise<T> {
    return apiFetch<T>(path, { method: 'GET' });
  },

  async post<T = unknown>(path: string, body?: unknown): Promise<T> {
    return apiFetch<T>(path, {
      method: 'POST',
      body: body ? JSON.stringify(body) : undefined
    });
  },

  async put<T = unknown>(path: string, body?: unknown): Promise<T> {
    return apiFetch<T>(path, {
      method: 'PUT',
      body: body ? JSON.stringify(body) : undefined
    });
  },

  async patch<T = unknown>(path: string, body?: unknown): Promise<T> {
    return apiFetch<T>(path, {
      method: 'PATCH',
      body: body ? JSON.stringify(body) : undefined
    });
  },

  async delete<T = unknown>(path: string): Promise<T> {
    return apiFetch<T>(path, { method: 'DELETE' });
  }
};

/**
 * Download a file from an authenticated endpoint.
 * Triggers browser download with the given filename.
 */
export async function apiDownload(path: string, filename: string): Promise<void> {
  const token = getToken();

  const headers: Record<string, string> = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  trackAction(`download GET ${path}`);

  const startTime = Date.now();
  const res = await fetch(path, { method: 'GET', headers });
  const durationMs = Date.now() - startTime;

  if (res.status === 401) {
    clearToken();
    if (browser) {
      window.location.href = '/login';
    }
    throw new Error('Session expired');
  }

  if (!res.ok) {
    let errorMessage = `Download failed (${res.status})`;
    let responseBody: string | undefined;
    try {
      const data = await res.json();
      errorMessage = data.error || data.errors?.[0]?.message || errorMessage;
      responseBody = JSON.stringify(data).slice(0, 500);
    } catch {
      // Response wasn't JSON — use the generic message
    }

    trackAction(`download GET ${path} → ${res.status} (${durationMs}ms)`);

    if (res.status >= 500) {
      const { reportApiError } = await import('$lib/stores/error-reporter.svelte');
      reportApiError({
        status: res.status,
        url: path,
        method: 'GET',
        message: errorMessage,
        responseBody,
        requestDurationMs: durationMs,
      });
    }

    throw new Error(errorMessage);
  }

  // Prefer server-provided filename from Content-Disposition, fall back to caller
  const disposition = res.headers.get('Content-Disposition');
  const serverFilename = disposition?.match(/filename="?([^";\n]+)"?/)?.[1];
  const effectiveFilename = serverFilename || filename;

  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = effectiveFilename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export async function apiUpload<T = unknown>(
  path: string,
  formData: FormData
): Promise<T> {
  const token = getToken();

  const headers: Record<string, string> = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  // Do NOT set Content-Type — browser sets it with boundary for multipart
  trackAction(`upload POST ${path}`);

  const startTime = Date.now();
  const res = await fetch(path, {
    method: 'POST',
    headers,
    body: formData
  });
  const durationMs = Date.now() - startTime;

  if (res.status === 401) {
    clearToken();
    if (browser) {
      window.location.href = '/login';
    }
    throw new Error('Session expired');
  }

  const data = await res.json();

  if (!res.ok) {
    const errorMessage =
      data.error || data.errors?.[0]?.message || `Request failed (${res.status})`;

    trackAction(`upload POST ${path} → ${res.status} (${durationMs}ms)`);

    if (res.status >= 500) {
      const { reportApiError } = await import('$lib/stores/error-reporter.svelte');
      reportApiError({
        status: res.status,
        url: path,
        method: 'POST',
        message: errorMessage,
        responseBody: JSON.stringify(data).slice(0, 500),
        requestDurationMs: durationMs,
      });
    }

    throw new Error(errorMessage);
  }

  return data as T;
}
