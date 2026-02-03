import { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { Sidebar } from './sidebar';
import { SettingsModal } from './settings/settings-modal';

export function Layout() {
  const [collapsed, setCollapsed] = useState(() => {
    return localStorage.getItem('concord-sidebar') === 'collapsed';
  });
  const [settingsOpen, setSettingsOpen] = useState(false);

  const handleToggle = () => {
    setCollapsed((prev) => {
      const next = !prev;
      localStorage.setItem('concord-sidebar', next ? 'collapsed' : 'expanded');
      return next;
    });
  };

  return (
    <div className="flex min-h-screen">
      <Sidebar
        collapsed={collapsed}
        onToggle={handleToggle}
        onSettingsClick={() => setSettingsOpen(true)}
      />
      <main
        className="flex-1 transition-[margin-left] duration-200 ease-in-out"
        style={{ marginLeft: collapsed ? 64 : 260 }}
      >
        <div className="mx-auto max-w-6xl px-8 py-8">
          <Outlet />
        </div>
      </main>
      {settingsOpen && <SettingsModal onClose={() => setSettingsOpen(false)} />}
    </div>
  );
}
