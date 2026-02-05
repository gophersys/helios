import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { GoogleOAuthProvider } from '@react-oauth/google';
import { ThemeProvider } from './theme-provider';
import { AuthProvider, useAuth } from './auth-provider';
import { Layout } from './components/layout';

// Lazy-loaded page components
const LoginPage = lazy(() => import('./pages/login').then(m => ({ default: m.LoginPage })));
const DashboardPage = lazy(() => import('./pages/dashboard').then(m => ({ default: m.DashboardPage })));
const PlaceholderPage = lazy(() => import('./pages/placeholder').then(m => ({ default: m.PlaceholderPage })));
const UsersPage = lazy(() => import('./pages/users').then(m => ({ default: m.UsersPage })));
const PermissionSetsPage = lazy(() => import('./pages/permission-sets').then(m => ({ default: m.PermissionSetsPage })));
const InventoryCatalogPage = lazy(() => import('./pages/inventory/inventory-catalog').then(m => ({ default: m.InventoryCatalogPage })));
const CodebasesPage = lazy(() => import('./pages/codebases/codebases-page').then(m => ({ default: m.CodebasesPage })));
const ProductsPage = lazy(() => import('./pages/products/products-page').then(m => ({ default: m.ProductsPage })));
const GuidesPage = lazy(() => import('./pages/guides/guides-page').then(m => ({ default: m.GuidesPage })));
const HistoryPage = lazy(() => import('./pages/history/history-page').then(m => ({ default: m.HistoryPage })));
const SystemPage = lazy(() => import('./pages/system/system-page').then(m => ({ default: m.SystemPage })));
const SystemOverview = lazy(() => import('./pages/system/overview').then(m => ({ default: m.SystemOverview })));
const NodesList = lazy(() => import('./pages/system/nodes-list').then(m => ({ default: m.NodesList })));
const NodeDetail = lazy(() => import('./pages/system/node-detail').then(m => ({ default: m.NodeDetail })));
const PodsList = lazy(() => import('./pages/system/pods-list').then(m => ({ default: m.PodsList })));
const PodDetail = lazy(() => import('./pages/system/pod-detail').then(m => ({ default: m.PodDetail })));
const DeploymentsList = lazy(() => import('./pages/system/deployments-list').then(m => ({ default: m.DeploymentsList })));
const DeploymentDetail = lazy(() => import('./pages/system/deployment-detail').then(m => ({ default: m.DeploymentDetail })));
const ServicesList = lazy(() => import('./pages/system/services-list').then(m => ({ default: m.ServicesList })));
const ServiceDetail = lazy(() => import('./pages/system/service-detail').then(m => ({ default: m.ServiceDetail })));
const JobsList = lazy(() => import('./pages/system/jobs-list').then(m => ({ default: m.JobsList })));
const JobDetail = lazy(() => import('./pages/system/job-detail').then(m => ({ default: m.JobDetail })));
const ConfigList = lazy(() => import('./pages/system/config-list').then(m => ({ default: m.ConfigList })));
const EventsList = lazy(() => import('./pages/system/events-list').then(m => ({ default: m.EventsList })));
const RbacPage = lazy(() => import('./pages/system/rbac').then(m => ({ default: m.RbacPage })));

function PageLoader() {
  return (
    <div className="flex h-64 items-center justify-center">
      <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
    </div>
  );
}

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
    <Suspense fallback={<PageLoader />}>
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
          {/* Planned feature routes - will be implemented in future sprints */}
          <Route path="tests" element={<PlaceholderPage />} />
          <Route path="deployments" element={<PlaceholderPage />} />
          <Route path="nodes" element={<PlaceholderPage />} />
          <Route path="results" element={<PlaceholderPage />} />
          <Route path="logs" element={<PlaceholderPage />} />
          <Route path="statistics" element={<PlaceholderPage />} />
          <Route path="users" element={<UsersPage />} />
          <Route path="permission-sets" element={<PermissionSetsPage />} />
          <Route path="inventory" element={<InventoryCatalogPage />} />
          <Route path="codebases" element={<CodebasesPage />} />
          <Route path="products" element={<ProductsPage />} />
          <Route path="guides" element={<GuidesPage />} />
          <Route path="history" element={<HistoryPage />} />
          <Route path="system" element={<SystemPage />}>
            <Route index element={<SystemOverview />} />
            <Route path="nodes" element={<NodesList />} />
            <Route path="nodes/:nodeName" element={<NodeDetail />} />
            <Route path="pods" element={<PodsList />} />
            <Route path="pods/:namespace/:name" element={<PodDetail />} />
            <Route path="deployments" element={<DeploymentsList />} />
            <Route path="deployments/:namespace/:name" element={<DeploymentDetail />} />
            <Route path="services" element={<ServicesList />} />
            <Route path="services/:namespace/:name" element={<ServiceDetail />} />
            <Route path="jobs" element={<JobsList />} />
            <Route path="jobs/:namespace/:name" element={<JobDetail />} />
            <Route path="config" element={<ConfigList />} />
            <Route path="rbac" element={<RbacPage />} />
            <Route path="events" element={<EventsList />} />
          </Route>
        </Route>
      </Routes>
    </Suspense>
  );
}

export function App() {
  const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID || '';
  if (!clientId) {
    console.warn('VITE_GOOGLE_CLIENT_ID is not set. Google login will not work.');
  }

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
