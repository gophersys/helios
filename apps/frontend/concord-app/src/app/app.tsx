import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { GoogleOAuthProvider } from '@react-oauth/google';
import { ThemeProvider } from './theme-provider';
import { AuthProvider, useAuth } from './auth-provider';
import { Layout } from './components/layout';
import { LoginPage } from './pages/login';
import { DashboardPage } from './pages/dashboard';
import { PlaceholderPage } from './pages/placeholder';
import { UsersPage } from './pages/users';
import { PermissionSetsPage } from './pages/permission-sets';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-surface-0">
        <div className="text-sm text-text-tertiary">Loading...</div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route path="tests" element={<PlaceholderPage />} />
        <Route path="deployments" element={<PlaceholderPage />} />
        <Route path="nodes" element={<PlaceholderPage />} />
        <Route path="results" element={<PlaceholderPage />} />
        <Route path="logs" element={<PlaceholderPage />} />
        <Route path="statistics" element={<PlaceholderPage />} />
        <Route path="users" element={<UsersPage />} />
        <Route path="permission-sets" element={<PermissionSetsPage />} />
      </Route>
    </Routes>
  );
}

export function App() {
  const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID || '';

  return (
    <ThemeProvider>
      <GoogleOAuthProvider clientId={clientId}>
        <AuthProvider>
          <BrowserRouter>
            <AppRoutes />
          </BrowserRouter>
        </AuthProvider>
      </GoogleOAuthProvider>
    </ThemeProvider>
  );
}

export default App;
