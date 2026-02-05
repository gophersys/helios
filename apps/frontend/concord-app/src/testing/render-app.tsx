import { render, type RenderResult } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { AuthContext } from '../app/auth-provider';
import { authenticatedAuth } from './mock-auth';

interface RenderAppOptions {
  auth?: ReturnType<typeof authenticatedAuth>;
  route?: string;
}

/**
 * Render a component wrapped with AuthContext and MemoryRouter.
 */
export function renderApp(
  ui: React.ReactElement,
  options: RenderAppOptions = {}
): RenderResult {
  const { auth = authenticatedAuth(), route = '/' } = options;

  return render(
    <AuthContext.Provider value={auth}>
      <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
    </AuthContext.Provider>
  );
}
