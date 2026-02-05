import { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  FlaskConical,
  Container,
  Server,
  ClipboardCheck,
  ScrollText,
  BarChart3,
  Settings,
  Users,
  ShieldCheck,
  Cpu,
  Package,
  GitBranch,
  BookOpen,
  History,
  LogOut,
  PanelLeftClose,
  Monitor,
} from 'lucide-react';
import { useTheme } from '../theme-provider';
import { useAuth } from '../auth-provider';
import logoDark from '../../assets/corekinect-logo.png';
import logoLight from '../../assets/corekinect-logo-dark.png';
import ckDark from '../../assets/ck-logo.png';
import ckLight from '../../assets/ck-logo-dark.png';

type Mode = 'manufacturing' | 'validation';

const STORAGE_KEY = 'concord-mode';

function getInitialMode(): Mode {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === 'manufacturing' || stored === 'validation') return stored;
  return 'manufacturing';
}

const manufacturingNav = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/tests', icon: FlaskConical, label: 'Tests' },
  { to: '/deployments', icon: Container, label: 'Deployments' },
  { to: '/nodes', icon: Server, label: 'Nodes' },
  { to: '/results', icon: ClipboardCheck, label: 'Test Results' },
  { to: '/logs', icon: ScrollText, label: 'Logs' },
  { to: '/statistics', icon: BarChart3, label: 'Statistics' },
];

const validationNav = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/tests', icon: FlaskConical, label: 'Tests' },
  { to: '/deployments', icon: Container, label: 'Deployments' },
  { to: '/nodes', icon: Server, label: 'Nodes' },
  { to: '/results', icon: ClipboardCheck, label: 'Test Results' },
  { to: '/logs', icon: ScrollText, label: 'Logs' },
  { to: '/statistics', icon: BarChart3, label: 'Statistics' },
];

function ModeToggle({
  mode,
  onModeChange,
  collapsed,
}: {
  mode: Mode;
  onModeChange: (mode: Mode) => void;
  collapsed: boolean;
}) {
  return (
    <div
      className={[
        'flex rounded-lg bg-surface-2 p-0.5',
        collapsed ? 'mx-2 mt-3' : 'mx-4 mt-3',
      ].join(' ')}
    >
      <button
        onClick={() => onModeChange('manufacturing')}
        className={[
          'flex-1 rounded-md text-center text-2xs font-medium transition-all',
          collapsed ? 'px-1 py-1.5' : 'px-2 py-1.5',
          mode === 'manufacturing'
            ? 'bg-accent-muted text-accent shadow-sm'
            : 'text-text-tertiary hover:text-text-secondary',
        ].join(' ')}
      >
        {collapsed ? 'M' : 'Manufacturing'}
      </button>
      <button
        onClick={() => onModeChange('validation')}
        className={[
          'flex-1 rounded-md text-center text-2xs font-medium transition-all',
          collapsed ? 'px-1 py-1.5' : 'px-2 py-1.5',
          mode === 'validation'
            ? 'bg-accent-muted text-accent shadow-sm'
            : 'text-text-tertiary hover:text-text-secondary',
        ].join(' ')}
      >
        {collapsed ? 'V' : 'Validation'}
      </button>
    </div>
  );
}

function SidebarLink({
  to,
  icon: Icon,
  label,
  end,
  collapsed,
  onDoubleClick,
}: {
  to: string;
  icon: React.ComponentType<{ size: number; strokeWidth: number; className?: string }>;
  label: string;
  end?: boolean;
  collapsed: boolean;
  onDoubleClick: () => void;
}) {
  return (
    <NavLink
      to={to}
      end={end}
      title={collapsed ? label : undefined}
      onDoubleClick={onDoubleClick}
      className={({ isActive }) =>
        [
          'group relative flex items-center rounded-lg text-[13px] font-medium transition-all',
          collapsed ? 'justify-center px-0 py-2' : 'gap-3 px-3 py-2',
          isActive
            ? 'bg-sidebar-active text-accent'
            : 'text-text-secondary hover:bg-sidebar-hover hover:text-text-primary',
        ].join(' ')
      }
    >
      {({ isActive }) => (
        <>
          {isActive && (
            <div className="absolute left-0 top-1/2 h-4 w-0.5 -translate-y-1/2 rounded-r bg-accent" />
          )}
          <Icon size={18} strokeWidth={1.75} className="shrink-0" />
          {!collapsed && <span className="truncate">{label}</span>}
        </>
      )}
    </NavLink>
  );
}

export function Sidebar({
  collapsed,
  onToggle,
  onSettingsClick,
}: {
  collapsed: boolean;
  onToggle: () => void;
  onSettingsClick: () => void;
}) {
  const { theme } = useTheme();
  const { user, logout, hasPermission } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState<Mode>(getInitialMode);

  const handleModeChange = (newMode: Mode) => {
    setMode(newMode);
    localStorage.setItem(STORAGE_KEY, newMode);
  };

  const navItems = mode === 'manufacturing' ? manufacturingNav : validationNav;

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const isAdmin = hasPermission('Concord.Admin.Users.View') || hasPermission('Concord.Admin.Inventory.View') || hasPermission('Concord.Admin.Codebases.View') || hasPermission('Concord.Admin.Products.View') || hasPermission('Concord.Admin.History.View') || hasPermission('Concord.Admin.System.View');

  return (
    <aside
      className={[
        'fixed inset-y-0 left-0 z-30 flex flex-col border-r border-border bg-sidebar-bg transition-[width] duration-200 ease-in-out',
        collapsed ? 'w-16' : 'w-sidebar',
      ].join(' ')}
    >
      {/* Brand + collapse toggle */}
      <div
        className={[
          'flex h-14 items-center',
          collapsed ? 'justify-center px-2' : 'justify-between px-5',
        ].join(' ')}
      >
        {collapsed ? (
          <button
            onClick={onToggle}
            title="Expand sidebar"
            aria-label="Expand sidebar"
            className="flex items-center justify-center"
          >
            <img
              src={theme === 'dark' ? ckDark : ckLight}
              alt="CoreKinect"
              className="h-4"
            />
          </button>
        ) : (
          <>
            <div className="flex flex-col gap-1.5">
              <img
                src={theme === 'dark' ? logoDark : logoLight}
                alt="CoreKinect"
                className="h-3.5"
              />
              <span className="text-2xs font-medium tracking-widest uppercase text-text-tertiary">
                Concord
              </span>
            </div>
            <button
              onClick={onToggle}
              title="Collapse sidebar"
              aria-label="Collapse sidebar"
              className="flex h-7 w-7 items-center justify-center rounded-lg text-text-tertiary transition-colors hover:bg-sidebar-hover hover:text-text-primary"
            >
              <PanelLeftClose size={16} strokeWidth={1.75} />
            </button>
          </>
        )}
      </div>

      {/* Divider */}
      <div
        className={
          collapsed
            ? 'mx-2 border-t border-border'
            : 'mx-4 border-t border-border'
        }
      />

      {/* Mode toggle */}
      <ModeToggle mode={mode} onModeChange={handleModeChange} collapsed={collapsed} />

      {/* Navigation */}
      <nav
        className={[
          'flex-1 space-y-0.5 pt-4 pb-2',
          collapsed ? 'px-2' : 'px-3',
        ].join(' ')}
      >
        {navItems.map(({ to, icon, label }) => (
          <SidebarLink
            key={to}
            to={to}
            icon={icon}
            label={label}
            end={to === '/'}
            collapsed={collapsed}
            onDoubleClick={onToggle}
          />
        ))}

        {/* Admin section */}
        {isAdmin && (
          <div className="pt-4">
            <div
              className={[
                'border-t border-border',
                collapsed ? 'mx-0' : 'mx-1',
              ].join(' ')}
            />
            <div className="pt-4">
              {!collapsed && (
                <span className="mb-2 block px-3 text-2xs font-medium uppercase tracking-widest text-text-tertiary">
                  Admin
                </span>
              )}
              {hasPermission('Concord.Admin.System.View') && (
                <SidebarLink
                  to="/system"
                  icon={Monitor}
                  label="System"
                  collapsed={collapsed}
                  onDoubleClick={onToggle}
                />
              )}
              {hasPermission('Concord.Admin.Inventory.View') && (
                <SidebarLink
                  to="/inventory"
                  icon={Cpu}
                  label="Inventory"
                  collapsed={collapsed}
                  onDoubleClick={onToggle}
                />
              )}
              {hasPermission('Concord.Admin.Codebases.View') && (
                <SidebarLink
                  to="/codebases"
                  icon={GitBranch}
                  label="Codebases"
                  collapsed={collapsed}
                  onDoubleClick={onToggle}
                />
              )}
              {hasPermission('Concord.Admin.Products.View') && (
                <SidebarLink
                  to="/products"
                  icon={Package}
                  label="Products"
                  collapsed={collapsed}
                  onDoubleClick={onToggle}
                />
              )}
              {hasPermission('Concord.Admin.History.View') && (
                <SidebarLink
                  to="/history"
                  icon={History}
                  label="History"
                  collapsed={collapsed}
                  onDoubleClick={onToggle}
                />
              )}
              <SidebarLink
                to="/guides"
                icon={BookOpen}
                label="Guides"
                collapsed={collapsed}
                onDoubleClick={onToggle}
              />
              {hasPermission('Concord.Admin.Users.View') && (
                <SidebarLink
                  to="/users"
                  icon={Users}
                  label="Users"
                  collapsed={collapsed}
                  onDoubleClick={onToggle}
                />
              )}
              {hasPermission('Concord.Admin.Users.View') && (
                <SidebarLink
                  to="/permission-sets"
                  icon={ShieldCheck}
                  label="Permission Sets"
                  collapsed={collapsed}
                  onDoubleClick={onToggle}
                />
              )}
            </div>
          </div>
        )}
      </nav>

      {/* Bottom */}
      <div
        className={[
          'border-t border-border space-y-0.5',
          collapsed ? 'p-2' : 'p-3',
        ].join(' ')}
      >
        <button
          onClick={onSettingsClick}
          onDoubleClick={onToggle}
          title={collapsed ? 'Settings' : undefined}
          className={[
            'group relative flex w-full items-center rounded-lg text-[13px] font-medium transition-all',
            collapsed ? 'justify-center px-0 py-2' : 'gap-3 px-3 py-2',
            'text-text-secondary hover:bg-sidebar-hover hover:text-text-primary',
          ].join(' ')}
        >
          <Settings size={18} strokeWidth={1.75} className="shrink-0" />
          {!collapsed && <span className="truncate">Settings</span>}
        </button>

        {/* User info + logout */}
        {user && (
          <div
            className={[
              'mt-1 flex items-center rounded-lg',
              collapsed ? 'justify-center py-2' : 'gap-2 px-3 py-2',
            ].join(' ')}
          >
            <div
              className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent-muted text-2xs font-semibold text-accent"
              title={
                collapsed
                  ? `${user.name}${user.permissionSetName ? ` (${user.permissionSetName})` : ''}`
                  : undefined
              }
            >
              {user.name.charAt(0).toUpperCase()}
            </div>
            {!collapsed && (
              <>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-2xs font-medium text-text-primary">
                    {user.name}
                  </div>
                  <div className="truncate text-2xs text-text-tertiary">
                    {user.permissionSetName || user.email}
                  </div>
                </div>
                <button
                  onClick={handleLogout}
                  title="Sign out"
                  aria-label="Log out"
                  className="shrink-0 rounded p-1 text-text-tertiary transition-colors hover:bg-sidebar-hover hover:text-text-primary"
                >
                  <LogOut size={14} strokeWidth={1.75} />
                </button>
              </>
            )}
          </div>
        )}
      </div>
    </aside>
  );
}
