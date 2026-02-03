import { useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { GoogleLogin, CredentialResponse } from '@react-oauth/google';
import { useAuth } from '../auth-provider';
import { useTheme } from '../theme-provider';
import logoDark from '../../assets/corekinect-logo.png';
import logoLight from '../../assets/corekinect-logo-dark.png';

export function LoginPage() {
  const { login, isAuthenticated, isLoading } = useAuth();
  const { theme } = useTheme();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-surface-0">
        <div className="text-sm text-text-tertiary">Loading...</div>
      </div>
    );
  }

  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  const handleSuccess = async (response: CredentialResponse) => {
    setError(null);
    try {
      await login(response.credential!);
      navigate('/');
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : 'Login failed';
      setError(message);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-surface-0">
      <div className="w-full max-w-sm px-4">
        {/* Logo */}
        <div className="mb-8 flex flex-col items-center">
          <img
            src={theme === 'dark' ? logoDark : logoLight}
            alt="CoreKinect"
            className="mb-3 h-6"
          />
          <h1 className="text-lg font-semibold tracking-widest uppercase text-text-primary">
            Concord
          </h1>
        </div>

        {/* Card */}
        <div className="rounded-xl border border-border bg-surface-1 p-6">
          <h2 className="mb-6 text-center text-sm font-medium text-text-primary">
            Sign in to continue
          </h2>

          <div className="flex justify-center">
            <GoogleLogin
              onSuccess={handleSuccess}
              onError={() => setError('Google sign-in failed. Try again.')}
              theme={theme === 'dark' ? 'filled_black' : 'outline'}
              size="large"
              shape="rectangular"
              width={280}
            />
          </div>

          {error && (
            <div className="mt-4 rounded-lg bg-error-muted px-3 py-2 text-center text-sm text-error">
              {error}
            </div>
          )}
        </div>

        <p className="mt-4 text-center text-2xs text-text-tertiary">
          Only pre-registered accounts can sign in.
        </p>
      </div>
    </div>
  );
}
