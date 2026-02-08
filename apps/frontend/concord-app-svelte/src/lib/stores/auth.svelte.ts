import { getContext, setContext } from 'svelte';
import { browser } from '$app/environment';
import { goto } from '$app/navigation';
import { apiFetch, setToken, clearToken, getToken } from '$lib/api';
import type { ApiResponse } from '$lib/types';
import type { User } from '$lib/types/models';

interface LoginResponse {
  token: string;
  user: {
    id: string;
    email: string;
    name: string;
    permissionSetId: string | null;
    permissionSetName: string | null;
  };
}

class AuthState {
  user = $state<User | null>(null);
  isLoading = $state(true);

  get isAuthenticated(): boolean {
    return !!this.user;
  }

  hasPermission(...perms: string[]): boolean {
    if (!this.user?.permissions) return false;
    return perms.every((p) => this.user!.permissions.includes(p));
  }

  async init(): Promise<void> {
    if (!browser) {
      this.isLoading = false;
      return;
    }

    const token = getToken();
    if (!token) {
      this.isLoading = false;
      return;
    }

    try {
      const res = await apiFetch<ApiResponse<User>>('/v2/auth/me');
      this.user = res.data;
    } catch {
      clearToken();
    } finally {
      this.isLoading = false;
    }
  }

  async login(googleCredential: string): Promise<void> {
    const loginData = await apiFetch<ApiResponse<LoginResponse>>('/v2/auth/login', {
      method: 'POST',
      body: JSON.stringify({ credential: googleCredential })
    });

    setToken(loginData.data.token);

    // Fetch full user profile with permissions
    const meData = await apiFetch<ApiResponse<User>>('/v2/auth/me');
    this.user = meData.data;
  }

  async loginWithCredentials(email: string, password: string): Promise<void> {
    // Use fetch directly (not apiFetch) because apiFetch's 401 interceptor
    // redirects to /login, which silently reloads the page instead of
    // showing the "invalid credentials" error to the user.
    const res = await fetch('/v2/auth/login/corecloud', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });

    const data = await res.json();

    if (!res.ok) {
      throw new Error(
        data.errors?.[0]?.message || data.error || 'Login failed'
      );
    }

    const loginData = data as ApiResponse<LoginResponse>;
    setToken(loginData.data.token);

    // Fetch full user profile with permissions
    const meData = await apiFetch<ApiResponse<User>>('/v2/auth/me');
    this.user = meData.data;
  }

  logout(): void {
    clearToken();
    this.user = null;
    if (browser) {
      goto('/login');
    }
  }
}

const AUTH_KEY = Symbol('auth');

export function createAuthContext(): AuthState {
  const auth = new AuthState();
  setContext(AUTH_KEY, auth);
  return auth;
}

export function getAuth(): AuthState {
  return getContext<AuthState>(AUTH_KEY);
}
