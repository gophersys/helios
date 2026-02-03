import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from 'react';
import { api, setToken, clearToken, getToken } from './api';

export interface User {
  id: string;
  email: string;
  name: string;
  permissionSetId: string | null;
  permissionSetName: string | null;
  permissions: string[];
}

interface AuthContextValue {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (googleCredential: string) => Promise<void>;
  logout: () => void;
  hasPermission: (...perms: string[]) => boolean;
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  isAuthenticated: false,
  isLoading: true,
  login: async () => {},
  logout: () => {},
  hasPermission: () => false,
});

export function useAuth() {
  return useContext(AuthContext);
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // On mount, verify any saved token
  useEffect(() => {
    const token = getToken();
    if (!token) {
      setIsLoading(false);
      return;
    }

    api<{ user: User }>('/v2/auth/me')
      .then((data) => setUser(data.user))
      .catch(() => clearToken())
      .finally(() => setIsLoading(false));
  }, []);

  const login = useCallback(async (googleCredential: string) => {
    const loginData = await api<{
      token: string;
      user: { id: string; email: string; name: string; permissionSetId: string | null; permissionSetName: string | null };
    }>('/v2/auth/login', {
      method: 'POST',
      body: JSON.stringify({ credential: googleCredential }),
    });

    setToken(loginData.token);

    // Fetch full user profile with permissions
    const meData = await api<{ user: User }>('/v2/auth/me');
    setUser(meData.user);
  }, []);

  const logout = useCallback(() => {
    clearToken();
    setUser(null);
  }, []);

  const hasPermission = useCallback(
    (...perms: string[]) => {
      if (!user?.permissions) return false;
      return perms.every((p) => user.permissions.includes(p));
    },
    [user],
  );

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isLoading,
        login,
        logout,
        hasPermission,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
