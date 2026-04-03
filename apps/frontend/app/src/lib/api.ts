import { browser } from '$app/environment';

const TOKEN_KEY = 'concord-token';
const VIEW_AS_KEY = 'concord-view-as-role';

export function getToken(): string | null {
  if (!browser) return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  if (!browser) return;
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  if (!browser) return;
  localStorage.removeItem(TOKEN_KEY);
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

  const res = await fetch(path, { ...options, headers });

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
    throw new Error(
      errorData.errors?.[0]?.message || errorData.error || `Request failed (${res.status})`
    );
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

  const res = await fetch(path, {
    method: 'POST',
    headers,
    body: formData
  });

  if (res.status === 401) {
    clearToken();
    if (browser) {
      window.location.href = '/login';
    }
    throw new Error('Session expired');
  }

  if (!res.ok) {
    const data = await res.json();
    throw new Error(
      data.error || data.errors?.[0]?.message || `Upload failed (${res.status})`
    );
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

  const res = await fetch(path, { method: 'GET', headers });

  if (res.status === 401) {
    clearToken();
    if (browser) {
      window.location.href = '/login';
    }
    throw new Error('Session expired');
  }

  if (!res.ok) {
    // Try to parse error message
    try {
      const data = await res.json();
      throw new Error(data.error || data.errors?.[0]?.message || `Download failed (${res.status})`);
    } catch {
      throw new Error(`Download failed (${res.status})`);
    }
  }

  // Get the blob and trigger download
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
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

  const res = await fetch(path, {
    method: 'POST',
    headers,
    body: formData
  });

  if (res.status === 401) {
    clearToken();
    if (browser) {
      window.location.href = '/login';
    }
    throw new Error('Session expired');
  }

  const data = await res.json();

  if (!res.ok) {
    throw new Error(
      data.error || data.errors?.[0]?.message || `Request failed (${res.status})`
    );
  }

  return data as T;
}
